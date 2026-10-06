import logging
import json
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.v1.deps import verify_active_dentist
from app.core.database import get_db
from app.models.models import Clinic, ECAHAuditLog, Patient, User, VerificationStatus
from app.services.ai_service import GeminiServiceError
from app.services.ecah_service import execute_ecah_agents
from app.services.idempotency import (
    mark_idempotency_complete,
    mark_idempotency_failed,
    request_digest,
    reserve_idempotency,
)

router = APIRouter(prefix="/api/v1/ecah", tags=["ECAH Workflow Engine"])
logger = logging.getLogger(__name__)


class ECAHClinicParameters(BaseModel):
    region: str | None = Field(default=None, max_length=120)
    insurance_tariff_context: str | None = Field(default=None, max_length=4000)
    compliance_rules: str | None = Field(default=None, max_length=4000)


class ECAHWorkflowRequest(BaseModel):
    operation_type: Literal["ECAH_FULL_SWEEP"]
    patient_id: int | None = Field(default=None, gt=0)
    patient_context: str = Field(min_length=1, max_length=4000)
    clinic_parameters: ECAHClinicParameters = Field(default_factory=ECAHClinicParameters)


class ECAHAgentResult(BaseModel):
    agent_type: Literal["emergency", "consult", "audit", "handover"]
    status: Literal["completed", "timeout", "error"]
    execution_time_ms: int = Field(ge=0)
    output: dict[str, object] | None
    error: str | None


class ECAHWorkflowResponse(BaseModel):
    clinic_id: int
    operation_type: Literal["ECAH_FULL_SWEEP"]
    status: Literal["completed", "partial"]
    execution_time_ms: int = Field(ge=0)
    agents: list[ECAHAgentResult]


@router.post("/execute-workflow", response_model=ECAHWorkflowResponse)
async def execute_workflow(
    request: ECAHWorkflowRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=36, max_length=36),
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_active_dentist),
):
    clinic = db.query(Clinic).filter(
        Clinic.id == current_user.clinic_id,
        Clinic.verification_status == VerificationStatus.VERIFIED,
        Clinic.subscription_status == "active",
    ).first()
    if clinic is None:
        raise HTTPException(status_code=403, detail="Verified active clinic required")

    patient_context: dict[str, object] = {"reported_context": request.patient_context}
    if request.patient_id is not None:
        patient = db.query(Patient).filter(
            Patient.id == request.patient_id,
            Patient.clinic_id == current_user.clinic_id,
        ).first()
        if patient is None:
            raise HTTPException(status_code=404, detail="Patient not found")
        patient_context["patient_record"] = {
            "age": patient.age,
            "gender": patient.gender,
            "medical_history": patient.medical_history,
        }

    idempotency_record = reserve_idempotency(
        db,
        clinic_id=clinic.id,
        operation="ecah-full-sweep",
        key=idempotency_key,
        digest=request_digest(request),
    )

    context: dict[str, object] = {
        "clinic": {
            "name": clinic.name,
            "operating_hours": clinic.operating_hours,
            "scheduling_context": clinic.scheduling_context,
        },
        "clinic_parameters": request.clinic_parameters.model_dump(),
        "patient_context": patient_context,
        "operation_type": request.operation_type,
    }

    try:
        agent_results, total_execution_ms = await execute_ecah_agents(clinic.id, context)
    except GeminiServiceError as exc:
        mark_idempotency_failed(db, idempotency_record)
        logger.exception("ECAH engine could not start for clinic %s", clinic.id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ECAH Gemini service is unavailable",
        ) from exc

    audit_rows = []
    for agent in agent_results:
        output = agent.get("output")
        output_fields = sorted(output.keys()) if isinstance(output, dict) else []
        summary = json.dumps({
            "status": agent["status"],
            "output_fields": output_fields,
            "error": agent["error"],
        })
        audit_rows.append(ECAHAuditLog(
            clinic_id=clinic.id,
            agent_type=str(agent["agent_type"]),
            execution_time_ms=int(agent["execution_time_ms"]),
            payload_summary=summary,
        ))

    try:
        db.add_all(audit_rows)
        mark_idempotency_complete(idempotency_record)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        mark_idempotency_failed(db, idempotency_record)
        logger.exception("Failed to save ECAH audit rows for clinic %s", clinic.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to persist ECAH audit results",
        ) from exc

    status_value = "completed" if all(agent["status"] == "completed" for agent in agent_results) else "partial"
    return ECAHWorkflowResponse(
        clinic_id=clinic.id,
        operation_type=request.operation_type,
        status=status_value,
        execution_time_ms=total_execution_ms,
        agents=agent_results,
    )