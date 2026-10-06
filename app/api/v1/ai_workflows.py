import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.deps import verify_active_dentist
from app.core.database import get_db
from app.models.models import Appointment, TreatmentPlan, User
from app.services.ai_service import GeminiServiceError, process_clinical_workflow

router = APIRouter(prefix="/ai", tags=["AI Workflows"])
logger = logging.getLogger(__name__)


class AIWorkflowRequest(BaseModel):
    workflow: Literal["appointment_triage", "treatment_summary"]
    record_id: int = Field(gt=0)


class AIWorkflowResponse(BaseModel):
    clinic_id: int
    workflow: str
    result: str


@router.post("/workflows", response_model=AIWorkflowResponse)
async def run_ai_workflow(
    request: AIWorkflowRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_active_dentist),
):
    clinic_id = current_user.clinic_id
    if request.workflow == "appointment_triage":
        record = db.query(Appointment).filter(
            Appointment.id == request.record_id,
            Appointment.clinic_id == clinic_id,
        ).first()
        if record is None:
            raise HTTPException(status_code=404, detail="Appointment not found")
        clinical_data = {
            "appointment_id": record.id,
            "patient_id": record.patient_id,
            "doctor_name": record.doctor_name,
            "appointment_time": record.appointment_time,
            "status": record.status,
            "notes": record.notes,
        }
    else:
        record = db.query(TreatmentPlan).filter(
            TreatmentPlan.id == request.record_id,
            TreatmentPlan.clinic_id == clinic_id,
        ).first()
        if record is None:
            raise HTTPException(status_code=404, detail="Treatment plan not found")
        clinical_data = {
            "treatment_plan_id": record.id,
            "patient_id": record.patient_id,
            "diagnosis": record.diagnosis,
            "procedure_name": record.procedure_name,
            "cost": record.cost,
            "status": record.status,
        }

    try:
        result = await process_clinical_workflow(
            clinic_id=clinic_id,
            workflow=request.workflow,
            clinical_data=clinical_data,
        )
    except GeminiServiceError as exc:
        logger.exception("Gemini workflow failed for clinic %s", clinic_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI workflow is unavailable; verify Gemini configuration and retry.",
        ) from exc

    return AIWorkflowResponse(clinic_id=clinic_id, workflow=request.workflow, result=result)