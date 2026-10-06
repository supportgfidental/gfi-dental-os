from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.api.v1.deps import verify_active_dentist
from app.core.database import get_db
from app.models.models import Patient, User
from app.schemas.schemas import PatientCreate, PatientResponse
from app.services.idempotency import mark_idempotency_complete, mark_idempotency_failed, request_digest, reserve_idempotency

router = APIRouter(
    prefix="/patients",
    tags=["Patients"],
)

@router.post("/", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
def create_patient(
    patient: PatientCreate,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=36, max_length=36),
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_active_dentist),
):
    reservation = reserve_idempotency(
        db,
        clinic_id=current_user.clinic_id,
        operation="create-patient",
        key=idempotency_key,
        digest=request_digest(patient),
    )
    existing_patient = (
        db.query(Patient)
        .filter(Patient.phone == patient.phone, Patient.clinic_id == current_user.clinic_id)
        .first()
    )
    if existing_patient:
        mark_idempotency_failed(db, reservation)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A patient with this phone number already exists."
        )
    
    db_patient = Patient(**patient.model_dump(), clinic_id=current_user.clinic_id)
    db.add(db_patient)
    try:
        db.flush()
        mark_idempotency_complete(reservation)
        db.commit()
        db.refresh(db_patient)
    except Exception:
        db.rollback()
        mark_idempotency_failed(db, reservation)
        raise
    return db_patient

@router.get("/", response_model=List[PatientResponse])
def get_patients(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_active_dentist),
):
    patients = (
        db.query(Patient)
        .filter(Patient.clinic_id == current_user.clinic_id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return patients

@router.get("/{patient_id}", response_model=PatientResponse)
def get_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_active_dentist),
):
    patient = (
        db.query(Patient)
        .filter(Patient.id == patient_id, Patient.clinic_id == current_user.clinic_id)
        .first()
    )
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found."
        )
    return patient