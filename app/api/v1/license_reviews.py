import hmac
import logging
import mimetypes
import os
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import license_certificate_directory, validate_dental_license_format
from app.models.models import Clinic, LicenseReviewAuditLog, User, VerificationStatus
from app.services.security_audit import record_security_event

router = APIRouter(prefix="/api/v1/admin/license-reviews", tags=["License Review"])
logger = logging.getLogger(__name__)


def verify_license_reviewer(
    request: Request,
    db: Session = Depends(get_db),
    reviewer_key: str | None = Header(default=None, alias="X-License-Reviewer-Key"),
) -> str:
    configured_key = os.getenv("LICENSE_REVIEWER_API_KEY")
    reviewer_id = os.getenv("LICENSE_REVIEWER_ID")
    if not configured_key or not reviewer_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="License review service is not configured",
        )
    if reviewer_key is None or not hmac.compare_digest(reviewer_key, configured_key):
        record_security_event(db, request, "LICENSE_REVIEWER_AUTH_FAILED")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid reviewer credentials",
        )
    return reviewer_id


class LicenseReviewQueueEntry(BaseModel):
    user_id: int
    clinic_id: int
    email: str
    full_name: str
    clinic_name: str
    license_number: str
    issuing_council: str
    user_status: VerificationStatus
    clinic_status: VerificationStatus
    certificate_available: bool


class LicenseReviewDecision(BaseModel):
    decision: Literal["VERIFIED", "REJECTED", "REVOKED"]
    review_reason: str = Field(min_length=5, max_length=2000)


class LicenseReviewDecisionResponse(BaseModel):
    audit_id: int
    user_id: int
    clinic_id: int
    decision: VerificationStatus
    reviewed_at: str


@router.get("/pending", response_model=list[LicenseReviewQueueEntry])
def get_pending_license_reviews(
    reviewer_id: str = Depends(verify_license_reviewer),
    db: Session = Depends(get_db),
):
    pending_users = (
        db.query(User, Clinic)
        .join(Clinic, Clinic.id == User.clinic_id)
        .filter(User.verification_status == VerificationStatus.PENDING)
        .order_by(User.created_at.asc())
        .all()
    )
    certificate_root = license_certificate_directory()
    entries = []
    for user, clinic in pending_users:
        certificate_available = False
        if user.license_certificate_path:
            try:
                cert_path = Path(user.license_certificate_path).resolve()
                cert_path.relative_to(certificate_root)
                certificate_available = cert_path.is_file()
            except (OSError, ValueError):
                certificate_available = False
        entries.append(LicenseReviewQueueEntry(
            user_id=user.id,
            clinic_id=clinic.id,
            email=user.email,
            full_name=user.full_name,
            clinic_name=clinic.name,
            license_number=user.license_number or "",
            issuing_council=user.issuing_council or "",
            user_status=user.verification_status,
            clinic_status=clinic.verification_status,
            certificate_available=certificate_available,
        ))
    return entries


@router.get("/verified", response_model=list[LicenseReviewQueueEntry])
def get_verified_license_accounts(
    reviewer_id: str = Depends(verify_license_reviewer),
    db: Session = Depends(get_db),
):
    verified_users = (
        db.query(User, Clinic)
        .join(Clinic, Clinic.id == User.clinic_id)
        .filter(User.verification_status == VerificationStatus.VERIFIED)
        .order_by(User.created_at.asc())
        .all()
    )
    certificate_root = license_certificate_directory()
    entries = []
    for user, clinic in verified_users:
        certificate_available = False
        if user.license_certificate_path:
            try:
                cert_path = Path(user.license_certificate_path).resolve()
                cert_path.relative_to(certificate_root)
                certificate_available = cert_path.is_file()
            except (OSError, ValueError):
                certificate_available = False
        entries.append(LicenseReviewQueueEntry(
            user_id=user.id,
            clinic_id=clinic.id,
            email=user.email,
            full_name=user.full_name,
            clinic_name=clinic.name,
            license_number=user.license_number or "",
            issuing_council=user.issuing_council or "",
            user_status=user.verification_status,
            clinic_status=clinic.verification_status,
            certificate_available=certificate_available,
        ))
    return entries


@router.get("/audit")
def get_license_review_audit(
    limit: int = Query(default=50, ge=1, le=200),
    reviewer_id: str = Depends(verify_license_reviewer),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(LicenseReviewAuditLog)
        .order_by(LicenseReviewAuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": row.id,
            "user_id": row.user_id,
            "clinic_id": row.clinic_id,
            "reviewer_id": row.reviewer_id,
            "previous_status": row.previous_status,
            "new_status": row.new_status,
            "review_reason": row.review_reason,
            "ip_address": row.ip_address,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.get("/{user_id}/certificate")
def download_license_certificate(
    user_id: int,
    request: Request,
    reviewer_id: str = Depends(verify_license_reviewer),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.license_certificate_path:
        raise HTTPException(status_code=404, detail="License certificate not found")
    certificate_root = license_certificate_directory()
    try:
        certificate_path = Path(user.license_certificate_path).resolve()
        certificate_path.relative_to(certificate_root)
    except (OSError, ValueError):
        logger.error("Certificate path escaped configured storage for user %s", user_id)
        raise HTTPException(status_code=404, detail="License certificate not found")
    if not certificate_path.is_file():
        raise HTTPException(status_code=404, detail="License certificate not found")

    record_security_event(db, request, "LICENSE_CERTIFICATE_VIEWED", user)
    media_type = mimetypes.guess_type(certificate_path.name)[0] or "application/octet-stream"
    return FileResponse(
        path=certificate_path,
        media_type=media_type,
        filename=f"license-certificate-{user_id}{certificate_path.suffix}",
    )


@router.post("/{user_id}/decision", response_model=LicenseReviewDecisionResponse)
def decide_license_review(
    user_id: int,
    decision: LicenseReviewDecision,
    request: Request,
    reviewer_id: str = Depends(verify_license_reviewer),
    db: Session = Depends(get_db),
):
    if len(decision.review_reason.strip()) < 5:
        raise HTTPException(status_code=422, detail="Review reason must contain at least five non-space characters")

    user = db.query(User).filter(User.id == user_id).with_for_update().first()
    if user is None:
        raise HTTPException(status_code=404, detail="Account not found")
    clinic = db.query(Clinic).filter(Clinic.id == user.clinic_id).with_for_update().first()
    if clinic is None:
        raise HTTPException(status_code=404, detail="Clinic not found")

    new_status = VerificationStatus(decision.decision)
    if new_status == VerificationStatus.VERIFIED:
        valid_user_license = (
            user.license_number
            and user.issuing_council
            and validate_dental_license_format(user.license_number, user.issuing_council)
        )
        valid_clinic_license = (
            clinic.license_number
            and clinic.issuing_council
            and validate_dental_license_format(clinic.license_number, clinic.issuing_council)
        )
        if (
            not valid_user_license
            or not valid_clinic_license
            or user.license_number != clinic.license_number
            or user.issuing_council != clinic.issuing_council
            or not user.license_certificate_path
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Valid user and clinic license details plus a certificate are required for approval",
            )
        certificate_root = license_certificate_directory()
        try:
            cert_path = Path(user.license_certificate_path).resolve()
            cert_path.relative_to(certificate_root)
        except (OSError, ValueError):
            raise HTTPException(status_code=409, detail="License certificate is unavailable")
        if not cert_path.is_file():
            raise HTTPException(status_code=409, detail="License certificate is unavailable")

    old_state = f"user={user.verification_status.value};clinic={clinic.verification_status.value}"
    user.verification_status = new_status
    clinic.verification_status = new_status
    audit_entry = LicenseReviewAuditLog(
        user_id=user.id,
        clinic_id=clinic.id,
        reviewer_id=reviewer_id,
        previous_status=old_state,
        new_status=f"user={new_status.value};clinic={new_status.value}",
        review_reason=decision.review_reason.strip(),
        ip_address=request.client.host if request.client else "unknown",
    )
    db.add(audit_entry)
    try:
        db.commit()
        db.refresh(audit_entry)
    except Exception as exc:
        db.rollback()
        logger.exception("Failed to persist license review for user %s", user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to save license review decision",
        ) from exc

    return LicenseReviewDecisionResponse(
        audit_id=audit_entry.id,
        user_id=user.id,
        clinic_id=clinic.id,
        decision=new_status,
        reviewed_at=audit_entry.created_at.isoformat(),
    )