from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional

# --- User Schemas ---
class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=8, max_length=128)
    clinic_name: Optional[str] = None
    dental_license_number: str = Field(
        min_length=4,
        max_length=32,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9/-]{3,31}$",
    )
    issuing_council: str = Field(min_length=2, max_length=120)
    clinic_mobile: Optional[str] = Field(
        default=None,
        pattern=r"^\+[1-9]\d{7,14}$",
    )
    clinic_operating_hours: Optional[str] = Field(default=None, max_length=2000)
    clinic_scheduling_context: Optional[str] = Field(default=None, max_length=4000)

class UserResponse(BaseModel):
    id: int
    clinic_id: int
    email: EmailStr
    full_name: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None
    clinic_id: Optional[int] = None

# --- Patient Schemas ---
class PatientCreate(BaseModel):
    name: str
    age: int
    gender: str
    phone: str
    medical_history: Optional[str] = None

class PatientResponse(BaseModel):
    id: int
    clinic_id: int
    name: str
    age: int
    gender: str
    phone: str
    medical_history: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

# --- Appointment Schemas ---
class AppointmentCreate(BaseModel):
    patient_id: int
    doctor_name: str
    appointment_time: datetime
    notes: Optional[str] = None

class AppointmentResponse(BaseModel):
    id: int
    clinic_id: int
    patient_id: int
    doctor_name: str
    appointment_time: datetime
    status: str
    notes: Optional[str] = None

    class Config:
        from_attributes = True

# --- Treatment Plan Schemas ---
class TreatmentPlanCreate(BaseModel):
    patient_id: int
    diagnosis: str
    procedure_name: str
    cost: float

class TreatmentPlanResponse(BaseModel):
    id: int
    clinic_id: int
    patient_id: int
    diagnosis: str
    procedure_name: str
    cost: float
    status: str

    class Config:
        from_attributes = True