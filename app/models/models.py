from enum import Enum
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Text, UniqueConstraint, Enum as SQLAlchemyEnum, Numeric, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class VerificationStatus(str, Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    REVOKED = "REVOKED"


class Clinic(Base):
    __tablename__ = "clinics"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    registered_mobile = Column(String, unique=True, index=True, nullable=True)
    license_number = Column(String, unique=True, index=True, nullable=True)
    issuing_council = Column(String, nullable=True)
    verification_status = Column(
        SQLAlchemyEnum(VerificationStatus, native_enum=False, length=16),
        nullable=False,
        default=VerificationStatus.PENDING,
    )
    operating_hours = Column(Text, nullable=True)
    scheduling_context = Column(Text, nullable=True)
    subscription_status = Column(String, default="active", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="clinic")
    patients = relationship("Patient", back_populates="clinic")
    appointments = relationship("Appointment", back_populates="clinic")
    treatments = relationship("TreatmentPlan", back_populates="clinic")
    telephony_calls = relationship("TelephonyCall", back_populates="clinic")
    ecah_audit_logs = relationship("ECAHAuditLog", back_populates="clinic")
    claims_audit_logs = relationship("ClaimsAuditLog", back_populates="clinic")
    agent_execution_traces = relationship("AgentExecutionTraceLog", back_populates="clinic")
    idempotency_records = relationship("IdempotencyRecord", back_populates="clinic")
    branch_nodes = relationship("BranchNode", back_populates="clinic")
    inventory_items = relationship("InventoryItem", back_populates="clinic")

    @property
    def is_verified(self) -> bool:
        return self.verification_status == VerificationStatus.VERIFIED

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="receptionist")
    license_number = Column(String, unique=True, index=True, nullable=True)
    issuing_council = Column(String, nullable=True)
    verification_status = Column(
        SQLAlchemyEnum(VerificationStatus, native_enum=False, length=16),
        nullable=False,
        default=VerificationStatus.PENDING,
    )
    license_certificate_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    clinic = relationship("Clinic", back_populates="users")

    @property
    def is_verified(self) -> bool:
        return self.verification_status == VerificationStatus.VERIFIED

class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    age = Column(Integer, nullable=False)
    gender = Column(String, nullable=False)
    phone = Column(String, index=True, nullable=False)
    medical_history = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    appointments = relationship("Appointment", back_populates="patient", cascade="all, delete-orphan")
    treatments = relationship("TreatmentPlan", back_populates="patient", cascade="all, delete-orphan")
    clinic = relationship("Clinic", back_populates="patients")

    __table_args__ = (UniqueConstraint("clinic_id", "phone", name="uq_patient_clinic_phone"),)

class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    doctor_name = Column(String, nullable=False)
    appointment_time = Column(DateTime, nullable=False)
    status = Column(String, default="Scheduled")
    notes = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    patient = relationship("Patient", back_populates="appointments")
    clinic = relationship("Clinic", back_populates="appointments")

class TreatmentPlan(Base):
    __tablename__ = "treatment_plans"

    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    diagnosis = Column(String, nullable=False)
    procedure_name = Column(String, nullable=False)
    cost = Column(Float, nullable=False)
    status = Column(String, default="Proposed")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    patient = relationship("Patient", back_populates="treatments")
    clinic = relationship("Clinic", back_populates="treatments")


class TelephonyCall(Base):
    __tablename__ = "telephony_calls"

    id = Column(String, primary_key=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False, index=True)
    status = Column(String, nullable=False, default="processing")
    intent = Column(String, nullable=True)
    processing_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    clinic = relationship("Clinic", back_populates="telephony_calls")


class SecurityAuditLog(Base):
    __tablename__ = "security_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=True, index=True)
    event_type = Column(String, nullable=False, index=True)
    ip_address = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class ECAHAuditLog(Base):
    __tablename__ = "ecah_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False, index=True)
    agent_type = Column(String, nullable=False, index=True)
    execution_time_ms = Column(Integer, nullable=False)
    payload_summary = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    clinic = relationship("Clinic", back_populates="ecah_audit_logs")


class ClaimsAuditLog(Base):
    __tablename__ = "claims_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False, index=True)
    claim_status = Column(String, nullable=False, index=True)
    payout_amount = Column(Numeric(12, 2), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    clinic = relationship("Clinic", back_populates="claims_audit_logs")


class LicenseReviewAuditLog(Base):
    __tablename__ = "license_review_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False, index=True)
    reviewer_id = Column(String(120), nullable=False)
    previous_status = Column(String(64), nullable=False)
    new_status = Column(String(64), nullable=False)
    review_reason = Column(Text, nullable=False)
    ip_address = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class BranchNode(Base):
    __tablename__ = "branch_nodes"

    branch_id = Column(String(36), primary_key=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False, index=True)
    location_name = Column(String(200), nullable=False)
    device_fingerprint = Column(String(128), nullable=False)
    signing_public_key = Column(Text, nullable=False)
    last_sync_timestamp = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    clinic = relationship("Clinic", back_populates="branch_nodes")

    __table_args__ = (
        UniqueConstraint("clinic_id", "device_fingerprint", name="uq_branch_clinic_fingerprint"),
    )


class BranchSyncAuditLog(Base):
    __tablename__ = "branch_sync_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False, index=True)
    branch_id = Column(String(36), ForeignKey("branch_nodes.branch_id"), nullable=False, index=True)
    batch_id = Column(String(36), nullable=False)
    sync_status = Column(String(24), nullable=False)
    transaction_count = Column(Integer, nullable=False)
    applied_count = Column(Integer, nullable=False)
    conflict_count = Column(Integer, nullable=False)
    payload_sha256 = Column(String(64), nullable=False)
    result_summary = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    __table_args__ = (
        UniqueConstraint("branch_id", "batch_id", name="uq_branch_sync_batch"),
    )


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False, index=True)
    sku = Column(String(100), nullable=False)
    name = Column(String(200), nullable=False)
    quantity = Column(Numeric(12, 3), nullable=False)
    unit = Column(String(40), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    clinic = relationship("Clinic", back_populates="inventory_items")

    __table_args__ = (UniqueConstraint("clinic_id", "sku", name="uq_inventory_clinic_sku"),)


class AgentExecutionTraceLog(Base):
    __tablename__ = "agent_execution_trace_logs"

    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False, index=True)
    execution_id = Column(String(36), nullable=False, index=True)
    agent_name = Column(String(80), nullable=False, index=True)
    execution_latency_ms = Column(Integer, nullable=False)
    token_consumption = Column(Integer, nullable=False, default=0)
    status = Column(String(16), nullable=False)
    attempt_number = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    clinic = relationship("Clinic", back_populates="agent_execution_traces")


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"

    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False, index=True)
    operation = Column(String(100), nullable=False)
    idempotency_key = Column(String(36), nullable=False)
    request_sha256 = Column(String(64), nullable=False)
    state = Column(String(16), nullable=False, default="PROCESSING", index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    clinic = relationship("Clinic", back_populates="idempotency_records")

    __table_args__ = (
        UniqueConstraint("clinic_id", "operation", "idempotency_key", name="uq_idempotency_clinic_operation_key"),
    )
class InsuranceClaim(Base):
    __tablename__ = "insurance_claims"
    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    treatment_plan_id = Column(Integer, ForeignKey("treatment_plans.id"), nullable=False)
    status = Column(String, default="Generated")
    packet_data = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class RecallCampaign(Base):
    __tablename__ = "recall_campaigns"
    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    trigger_reason = Column(String, nullable=False)
    message_content = Column(Text, nullable=False)
    status = Column(String, default="Pending")
    created_at = Column(DateTime, default=datetime.utcnow)

class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False, index=True)
    supplier_name = Column(String, nullable=False)
    items_json = Column(Text, nullable=False)
    total_cost = Column(Numeric(12, 2), nullable=False)
    status = Column(String, default="Draft")
    created_at = Column(DateTime, default=datetime.utcnow)

class ClinicalAudit(Base):
    __tablename__ = "clinical_audits"
    id = Column(Integer, primary_key=True, index=True)
    clinic_id = Column(Integer, ForeignKey("clinics.id"), nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    procedure_name = Column(String, nullable=False)
    safety_status = Column(String, nullable=False)
    audit_notes = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
