import logging
import traceback
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.api.v1.deps import verify_active_dentist
from app.core.database import get_db
from app.models.models import TreatmentPlan, Patient, User
from app.schemas.schemas import TreatmentPlanCreate, TreatmentPlanResponse
from app.services.idempotency import mark_idempotency_complete, mark_idempotency_failed, request_digest, reserve_idempotency

logger = logging.getLogger("gfi.treatments")

router = APIRouter()

@router.post("/", response_model=TreatmentPlanResponse, status_code=status.HTTP_201_CREATED)
def create_treatment_plan(
    plan: TreatmentPlanCreate,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=36, max_length=36),
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_active_dentist),
):
    try:
        reservation = reserve_idempotency(
            db,
            clinic_id=current_user.clinic_id,
            operation="create-treatment-plan",
            key=idempotency_key,
            digest=request_digest(plan),
        )
        patient = (
            db.query(Patient)
            .filter(
                Patient.id == plan.patient_id,
                Patient.clinic_id == current_user.clinic_id,
            )
            .first()
        )
        if not patient:
            mark_idempotency_failed(db, reservation)
            raise HTTPException(status_code=404, detail="Patient not found")
        
        db_plan = TreatmentPlan(**plan.model_dump(), clinic_id=current_user.clinic_id)
        db.add(db_plan)
        try:
            db.flush()
            mark_idempotency_complete(reservation)
            db.commit()
            db.refresh(db_plan)
        except Exception as inner_e:
            db.rollback()
            mark_idempotency_failed(db, reservation)
            raise inner_e
            
        return db_plan
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create treatment plan: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "status": "Error",
                "message": "Failed to create treatment plan",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )