from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.api.v1.deps import verify_active_dentist
from app.core.database import get_db
from app.models.models import Appointment, Patient, User
from app.schemas.schemas import AppointmentCreate, AppointmentResponse
from app.services.idempotency import mark_idempotency_complete, mark_idempotency_failed, request_digest, reserve_idempotency

router = APIRouter(
    prefix="/appointments",
    tags=["Appointments"],
)

@router.post("/", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
def create_appointment(
    appointment: AppointmentCreate,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=36, max_length=36),
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_active_dentist),
):
    reservation = reserve_idempotency(
        db,
        clinic_id=current_user.clinic_id,
        operation="create-appointment",
        key=idempotency_key,
        digest=request_digest(appointment),
    )
    patient = (
        db.query(Patient)
        .filter(
            Patient.id == appointment.patient_id,
            Patient.clinic_id == current_user.clinic_id,
        )
        .first()
    )
    if not patient:
        mark_idempotency_failed(db, reservation)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found. Cannot schedule appointment for a non-existent patient."
        )
    
    db_appointment = Appointment(
        **appointment.model_dump(),
        clinic_id=current_user.clinic_id,
    )
    db.add(db_appointment)
    try:
        db.flush()
        mark_idempotency_complete(reservation)
        db.commit()
        db.refresh(db_appointment)
    except Exception:
        db.rollback()
        mark_idempotency_failed(db, reservation)
        raise
    return db_appointment

@router.get("/", response_model=List[AppointmentResponse])
def get_appointments(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_active_dentist),
):
    appointments = (
        db.query(Appointment)
        .filter(Appointment.clinic_id == current_user.clinic_id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return appointments