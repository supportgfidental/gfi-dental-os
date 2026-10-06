import logging
import re
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.v1.deps import verify_active_dentist
from app.core.database import get_db
from app.models.models import ClaimsAuditLog, Patient, User
from app.services.ai_service import GeminiServiceError
from app.services.claims_service import audit_claim
from app.services.idempotency import (
    mark_idempotency_complete,
    mark_idempotency_failed,
    request_digest,
    reserve_idempotency,
)

router = APIRouter(prefix="/api/v1/claims", tags=["Claims Clearinghouse"])
logger = logging.getLogger(__name__)
CDT_CODE_PATTERN = re.compile(r"^D\d{4}$")


class ClaimsAuditRequest(BaseModel):
    patient_id: int | None = Field(default=None, gt=0)
    patient_treatment_description: str = Field(min_length=1, max_length=6000)
    procedure_codes: list[str] = Field(min_length=1, max_length=20)
    insurance_provider_rules: str = Field(min_length=1, max_length=6000)
    regional_tariffs: dict[str, Decimal] = Field(min_length=1, max_length=20)

    @field_validator("procedure_codes")
    @classmethod
    def validate_procedure_codes(cls, codes: list[str]) -> list[str]:
        normalized_codes = [code.strip().upper() for code in codes]
        if len(set(normalized_codes)) != len(normalized_codes):
            raise ValueError("Procedure codes must be unique")
        if any(not CDT_CODE_PATTERN.fullmatch(code) for code in normalized_codes):
            raise ValueError("Procedure codes must use CDT format, for example D0120")
        return normalized_codes

    @field_validator("regional_tariffs")
    @classmethod
    def validate_tariffs(cls, tariffs: dict[str, Decimal]) -> dict[str, Decimal]:
        normalized: dict[str, Decimal] = {}
        for code, amount in tariffs.items():
            normalized_code = code.strip().upper()
            if not CDT_CODE_PATTERN.fullmatch(normalized_code):
                raise ValueError("Tariff keys must be CDT codes")
            if (
                not amount.is_finite()
                or amount < 0
                or amount > Decimal("99999999.99")
                or amount.as_tuple().exponent < -2
            ):
                raise ValueError("Tariffs must be non-negative valid currency amounts")
            if normalized_code in normalized:
                raise ValueError("Tariff codes must be unique")
            normalized[normalized_code] = amount
        return normalized


class ClaimsAuditResponse(BaseModel):
    audit_id: int
    claim_validity_status: Literal["APPROVED", "PENDING_DOCS", "REJECTED_POLICY_MISMATCH"]
    confidence_score: int = Field(ge=0, le=100)
    compliance_notes: list[str]
    billable_codes: list[str]
    estimated_payout: Decimal
    payout_is_estimate: Literal[True] = True


@router.post("/audit-and-submit", response_model=ClaimsAuditResponse)
async def audit_and_submit_claim(
    request: ClaimsAuditRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=36, max_length=36),
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_active_dentist),
):
    if request.patient_id is not None:
        patient = db.query(Patient).filter(
            Patient.id == request.patient_id,
            Patient.clinic_id == current_user.clinic_id,
        ).first()
        if patient is None:
            raise HTTPException(status_code=404, detail="Patient not found")

    idempotency_record = reserve_idempotency(
        db,
        clinic_id=current_user.clinic_id,
        operation="claims-audit",
        key=idempotency_key,
        digest=request_digest(request),
    )

    try:
        audit_result = await audit_claim(
            clinic_id=current_user.clinic_id,
            patient_treatment_description=request.patient_treatment_description,
            procedure_codes=request.procedure_codes,
            insurance_provider_rules=request.insurance_provider_rules,
            regional_tariffs=request.regional_tariffs,
        )
    except GeminiServiceError as exc:
        mark_idempotency_failed(db, idempotency_record)
        logger.exception("Claims audit failed for clinic %s", current_user.clinic_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Claims audit service is temporarily unavailable",
        ) from exc

    audit_log = ClaimsAuditLog(
        clinic_id=current_user.clinic_id,
        claim_status=str(audit_result["claim_validity_status"]),
        payout_amount=audit_result["estimated_payout"],
    )
    try:
        db.add(audit_log)
        mark_idempotency_complete(idempotency_record)
        db.commit()
        db.refresh(audit_log)
    except SQLAlchemyError as exc:
        db.rollback()
        mark_idempotency_failed(db, idempotency_record)
        logger.exception("Failed to persist claims audit for clinic %s", current_user.clinic_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to save claims audit result",
        ) from exc

    return ClaimsAuditResponse(audit_id=audit_log.id, **audit_result)