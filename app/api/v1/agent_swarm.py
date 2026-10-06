import logging
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.v1.deps import verify_active_dentist
from app.core.agent_supervisor import (
    AgentSupervisorError,
    AgentExecutionResult,
    AgentAttemptTrace,
    create_supervisor,
)
from app.core.database import get_db
from app.models.models import AgentExecutionTraceLog, Clinic, Patient, User, VerificationStatus
from app.services.idempotency import (
    mark_idempotency_complete,
    mark_idempotency_failed,
    request_digest,
    reserve_idempotency,
)

router = APIRouter(prefix="/api/v1/swarm", tags=["Agent Swarm"])
logger = logging.getLogger(__name__)


class SwarmClinicParameters(BaseModel):
    region: str | None = Field(default=None, max_length=120)
    insurance_tariff_context: str | None = Field(default=None, max_length=4000)
    compliance_rules: str | None = Field(default=None, max_length=4000)


class ComprehensiveCaseRequest(BaseModel):
    patient_id: int | None = Field(default=None, gt=0)
    patient_context: str = Field(min_length=1, max_length=6000)
    clinic_parameters: SwarmClinicParameters = Field(default_factory=SwarmClinicParameters)


class ComprehensiveCaseResponse(BaseModel):
    execution_id: str
    clinic_id: int
    status: Literal["SUCCESS", "PARTIAL", "FAILED"]
    execution_latency_ms: int = Field(ge=0)
    agents: list[AgentExecutionResult]
    execution_trace: list[AgentAttemptTrace]


@router.post("/execute-comprehensive-case", response_model=ComprehensiveCaseResponse)
async def execute_comprehensive_case(
    request: ComprehensiveCaseRequest,
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

    case_context: dict[str, Any] = {
        "reported_patient_context": request.patient_context,
        "clinic_parameters": request.clinic_parameters.model_dump(),
        "clinic": {
            "name": clinic.name,
            "operating_hours": clinic.operating_hours,
            "scheduling_context": clinic.scheduling_context,
        },
    }
    if request.patient_id is not None:
        patient = db.query(Patient).filter(
            Patient.id == request.patient_id,
            Patient.clinic_id == current_user.clinic_id,
        ).first()
        if patient is None:
            raise HTTPException(status_code=404, detail="Patient not found")
        case_context["patient_record"] = {
            "age": patient.age,
            "gender": patient.gender,
            "medical_history": patient.medical_history,
        }

    idempotency_record = reserve_idempotency(
        db,
        clinic_id=clinic.id,
        operation="comprehensive-swarm",
        key=idempotency_key,
        digest=request_digest(request),
    )

    execution_id = str(uuid4())
    try:
        supervisor, context_store = create_supervisor()
    except AgentSupervisorError as exc:
        mark_idempotency_failed(db, idempotency_record)
        logger.error("Swarm is unavailable for clinic %s: %s", clinic.id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Swarm service is not configured",
        ) from exc

    try:
        result = await supervisor.execute(
            clinic_id=clinic.id,
            execution_id=execution_id,
            clinical_context=case_context,
        )
    except Exception as exc:
        mark_idempotency_failed(db, idempotency_record)
        logger.exception("Swarm execution failed for clinic %s", clinic.id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Swarm execution is temporarily unavailable",
        ) from exc
    finally:
        try:
            await context_store.close()
        except Exception:
            logger.exception("Failed to close Redis connection for execution %s", execution_id)

    trace_rows = [
        AgentExecutionTraceLog(
            clinic_id=clinic.id,
            execution_id=result.execution_id,
            agent_name=trace.agent_name,
            execution_latency_ms=trace.execution_latency_ms,
            token_consumption=trace.token_consumption,
            status=trace.status,
            attempt_number=trace.attempt_number,
        )
        for trace in result.trace
    ]
    db.add_all(trace_rows)
    try:
        mark_idempotency_complete(idempotency_record)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        mark_idempotency_failed(db, idempotency_record)
        logger.exception("Failed to persist swarm traces for clinic %s", clinic.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to persist swarm execution trace",
        ) from exc

    return ComprehensiveCaseResponse(
        execution_id=result.execution_id,
        clinic_id=result.clinic_id,
        status=result.status,
        execution_latency_ms=result.execution_latency_ms,
        agents=result.agents,
        execution_trace=result.trace,
    )