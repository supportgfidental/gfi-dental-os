import base64
import hashlib
import json
import logging
import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Literal
from uuid import UUID, uuid4

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.v1.deps import verify_active_dentist
from app.core.database import get_db
from app.models.models import (
    Appointment,
    BranchNode,
    BranchSyncAuditLog,
    Clinic,
    InventoryItem,
    TreatmentPlan,
    User,
    VerificationStatus,
)
from app.services.security_audit import record_security_event

router = APIRouter(prefix="/api/v1/fleet", tags=["Fleet Offline Sync"])
logger = logging.getLogger(__name__)
MAX_BATCH_TRANSACTIONS = 100
MAX_CLOCK_SKEW = timedelta(minutes=5)


class BranchRegistrationRequest(BaseModel):
    location_name: str = Field(min_length=1, max_length=200)
    public_key: str = Field(min_length=40, max_length=100)


class BranchRegistrationResponse(BaseModel):
    branch_id: UUID
    device_fingerprint: str
    location_name: str


class BranchNodeResponse(BaseModel):
    branch_id: UUID
    location_name: str
    device_fingerprint: str
    last_sync_timestamp: datetime | None
    is_active: bool


class FleetSyncTransaction(BaseModel):
    transaction_id: UUID
    entity_type: Literal["appointment", "treatment", "inventory"]
    record_id: str = Field(min_length=1, max_length=100)
    client_updated_at: datetime
    changes: dict[str, object] = Field(min_length=1, max_length=20)

    @field_validator("client_updated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("client_updated_at must include a timezone")
        return value.astimezone(timezone.utc)


class FleetSyncBatchRequest(BaseModel):
    batch_id: UUID
    branch_id: UUID
    transactions: list[FleetSyncTransaction] = Field(min_length=1, max_length=MAX_BATCH_TRANSACTIONS)

    @field_validator("transactions")
    @classmethod
    def unique_batch_transactions(cls, transactions: list[FleetSyncTransaction]) -> list[FleetSyncTransaction]:
        ids = [transaction.transaction_id for transaction in transactions]
        if len(ids) != len(set(ids)):
            raise ValueError("transaction_id values must be unique within a batch")
        return transactions


class FleetSignedEnvelope(BaseModel):
    signed_payload: str = Field(min_length=2, max_length=512_000)
    signature: str = Field(min_length=80, max_length=120)


class FleetSyncResult(BaseModel):
    transaction_id: UUID
    entity_type: str
    record_id: str
    status: Literal["applied", "conflict_server_wins", "conflict_record_missing", "rejected"]
    server_updated_at: datetime | None = None
    detail: str | None = None


class FleetSyncBatchResponse(BaseModel):
    batch_id: UUID
    branch_id: UUID
    sync_status: Literal["success", "partial", "conflict"]
    applied_count: int
    conflict_count: int
    results: list[FleetSyncResult]
    last_sync_timestamp: datetime


@router.get("/branches", response_model=list[BranchNodeResponse])
def list_branches(
    current_user: User = Depends(verify_active_dentist),
    db: Session = Depends(get_db),
):
    branches = db.query(BranchNode).filter(
        BranchNode.clinic_id == current_user.clinic_id,
    ).order_by(BranchNode.location_name.asc()).all()
    return [
        BranchNodeResponse(
            branch_id=UUID(branch.branch_id),
            location_name=branch.location_name,
            device_fingerprint=branch.device_fingerprint,
            last_sync_timestamp=branch.last_sync_timestamp.replace(tzinfo=timezone.utc)
            if branch.last_sync_timestamp and branch.last_sync_timestamp.tzinfo is None
            else branch.last_sync_timestamp,
            is_active=branch.is_active,
        )
        for branch in branches
    ]


def _utc_naive(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).replace(tzinfo=None)
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _verify_signature(branch: BranchNode, signed_payload: str, signature: str) -> bytes:
    try:
        public_key_bytes = base64.b64decode(branch.signing_public_key, validate=True)
        signature_bytes = base64.b64decode(signature, validate=True)
        public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        payload = signed_payload.encode("utf-8")
        public_key.verify(signature_bytes, payload)
        return payload
    except (ValueError, InvalidSignature) as exc:
        raise HTTPException(status_code=401, detail="Invalid fleet batch signature") from exc


def _apply_changes(entity: object, transaction: FleetSyncTransaction, now: datetime) -> None:
    values = transaction.changes
    if transaction.entity_type == "appointment":
        if not transaction.record_id.isdecimal():
            raise ValueError("Appointment record_id must be a server appointment ID")
        allowed = {"appointment_time", "doctor_name", "status", "notes"}
        if values.keys() - allowed:
            raise ValueError("Appointment update contains unsupported fields")
        if "appointment_time" in values:
            value = values["appointment_time"]
            if not isinstance(value, str):
                raise ValueError("appointment_time must be an ISO datetime")
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError("appointment_time must include a timezone")
            entity.appointment_time = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        if "doctor_name" in values:
            if not isinstance(values["doctor_name"], str) or not values["doctor_name"].strip():
                raise ValueError("doctor_name must be a non-empty string")
            entity.doctor_name = values["doctor_name"].strip()[:200]
        if "status" in values:
            allowed_statuses = {"Scheduled", "Confirmed", "Cancelled", "Completed", "No-show"}
            if values["status"] not in allowed_statuses:
                raise ValueError("Unsupported appointment status")
            entity.status = values["status"]
        if "notes" in values:
            if values["notes"] is not None and not isinstance(values["notes"], str):
                raise ValueError("notes must be a string or null")
            entity.notes = values["notes"][:4000] if isinstance(values["notes"], str) else None
    elif transaction.entity_type == "treatment":
        if not transaction.record_id.isdecimal():
            raise ValueError("Treatment record_id must be a server treatment ID")
        allowed = {"diagnosis", "procedure_name", "cost", "status"}
        if values.keys() - allowed:
            raise ValueError("Treatment update contains unsupported fields")
        for field_name, max_length in (("diagnosis", 2000), ("procedure_name", 200)):
            if field_name in values:
                value = values[field_name]
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"{field_name} must be a non-empty string")
                setattr(entity, field_name, value.strip()[:max_length])
        if "cost" in values:
            value = values["cost"]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError("cost must be a finite non-negative number")
            entity.cost = float(value)
        if "status" in values:
            if not isinstance(values["status"], str) or not values["status"].strip():
                raise ValueError("status must be a non-empty string")
            entity.status = values["status"].strip()[:80]
    else:
        if not transaction.record_id.strip() or len(transaction.record_id) > 100:
            raise ValueError("Inventory record_id must be a SKU")
        if values.keys() != {"quantity_delta"}:
            raise ValueError("Inventory updates must contain only quantity_delta")
        raw_delta = values["quantity_delta"]
        if isinstance(raw_delta, bool):
            raise ValueError("quantity_delta must be numeric")
        try:
            delta = Decimal(str(raw_delta))
        except InvalidOperation as exc:
            raise ValueError("quantity_delta must be numeric") from exc
        if not delta.is_finite() or delta == 0 or abs(delta) > Decimal("999999999.999"):
            raise ValueError("quantity_delta must be finite, non-zero, and within range")
        updated_quantity = Decimal(entity.quantity) + delta
        if updated_quantity < 0:
            raise ValueError("Inventory update would make quantity negative")
        entity.quantity = updated_quantity

    entity.updated_at = now


def _find_entity(db: Session, clinic_id: int, transaction: FleetSyncTransaction):
    if transaction.entity_type == "appointment" and transaction.record_id.isdecimal():
        return db.query(Appointment).filter(
            Appointment.id == int(transaction.record_id),
            Appointment.clinic_id == clinic_id,
        ).with_for_update().first()
    if transaction.entity_type == "treatment" and transaction.record_id.isdecimal():
        return db.query(TreatmentPlan).filter(
            TreatmentPlan.id == int(transaction.record_id),
            TreatmentPlan.clinic_id == clinic_id,
        ).with_for_update().first()
    if transaction.entity_type == "inventory":
        return db.query(InventoryItem).filter(
            InventoryItem.sku == transaction.record_id,
            InventoryItem.clinic_id == clinic_id,
        ).with_for_update().first()
    return None


@router.post("/branches/register", response_model=BranchRegistrationResponse)
def register_branch(
    request: BranchRegistrationRequest,
    current_user: User = Depends(verify_active_dentist),
    db: Session = Depends(get_db),
):
    try:
        public_key_bytes = base64.b64decode(request.public_key, validate=True)
        if len(public_key_bytes) != 32:
            raise ValueError("Ed25519 public keys must be 32 bytes")
        Ed25519PublicKey.from_public_bytes(public_key_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid Ed25519 public key") from exc

    fingerprint = hashlib.sha256(public_key_bytes).hexdigest()
    branch = db.query(BranchNode).filter(
        BranchNode.clinic_id == current_user.clinic_id,
        BranchNode.device_fingerprint == fingerprint,
    ).first()
    if branch:
        if branch.signing_public_key != request.public_key:
            raise HTTPException(status_code=409, detail="Branch key registration conflicts")
        if not branch.is_active:
            raise HTTPException(status_code=403, detail="Branch is disabled")
        return BranchRegistrationResponse(
            branch_id=UUID(branch.branch_id),
            device_fingerprint=branch.device_fingerprint,
            location_name=branch.location_name,
        )

    branch = BranchNode(
        branch_id=str(uuid4()),
        clinic_id=current_user.clinic_id,
        location_name=request.location_name.strip(),
        device_fingerprint=fingerprint,
        signing_public_key=request.public_key,
        is_active=True,
    )
    db.add(branch)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Device is already registered to this clinic") from exc
    return BranchRegistrationResponse(
        branch_id=UUID(branch.branch_id),
        device_fingerprint=branch.device_fingerprint,
        location_name=branch.location_name,
    )


@router.post("/sync-batch", response_model=FleetSyncBatchResponse)
def sync_batch(
    envelope: FleetSignedEnvelope,
    request: Request,
    current_user: User = Depends(verify_active_dentist),
    db: Session = Depends(get_db),
):
    try:
        batch = FleetSyncBatchRequest.model_validate_json(envelope.signed_payload)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Signed fleet payload is invalid") from exc

    branch = db.query(BranchNode).filter(
        BranchNode.branch_id == str(batch.branch_id),
        BranchNode.clinic_id == current_user.clinic_id,
        BranchNode.is_active.is_(True),
    ).first()
    if branch is None:
        raise HTTPException(status_code=404, detail="Registered active branch not found")

    try:
        canonical_payload = _verify_signature(branch, envelope.signed_payload, envelope.signature)
    except HTTPException:
        record_security_event(db, request, "FLEET_SYNC_SIGNATURE_INVALID", current_user)
        raise
    payload_hash = hashlib.sha256(canonical_payload).hexdigest()
    previous_batch = db.query(BranchSyncAuditLog).filter(
        BranchSyncAuditLog.branch_id == branch.branch_id,
        BranchSyncAuditLog.batch_id == str(batch.batch_id),
    ).first()
    if previous_batch:
        if previous_batch.payload_sha256 != payload_hash:
            raise HTTPException(status_code=409, detail="Batch ID was already used for different signed content")
        try:
            saved_result = json.loads(previous_batch.result_summary)
            return FleetSyncBatchResponse.model_validate(saved_result)
        except Exception as exc:
            logger.exception("Stored sync result is invalid for batch %s", batch.batch_id)
            raise HTTPException(status_code=500, detail="Unable to replay prior sync result") from exc

    now_aware = datetime.now(timezone.utc)
    now = now_aware.replace(tzinfo=None)
    results: list[FleetSyncResult] = []
    applied_count = 0
    conflict_count = 0

    for transaction in batch.transactions:
        client_timestamp = transaction.client_updated_at
        if client_timestamp > now_aware + MAX_CLOCK_SKEW:
            conflict_count += 1
            results.append(FleetSyncResult(
                transaction_id=transaction.transaction_id,
                entity_type=transaction.entity_type,
                record_id=transaction.record_id,
                status="rejected",
                detail="Client timestamp is too far in the future",
            ))
            continue

        entity = _find_entity(db, current_user.clinic_id, transaction)
        if entity is None:
            conflict_count += 1
            results.append(FleetSyncResult(
                transaction_id=transaction.transaction_id,
                entity_type=transaction.entity_type,
                record_id=transaction.record_id,
                status="conflict_record_missing",
                detail="Record does not exist in this clinic",
            ))
            continue

        server_timestamp = _utc_naive(entity.updated_at)
        if server_timestamp is not None and client_timestamp.replace(tzinfo=None) <= server_timestamp:
            conflict_count += 1
            results.append(FleetSyncResult(
                transaction_id=transaction.transaction_id,
                entity_type=transaction.entity_type,
                record_id=transaction.record_id,
                status="conflict_server_wins",
                server_updated_at=server_timestamp.replace(tzinfo=timezone.utc),
                detail="Server version is newer or equal; local changes were not applied",
            ))
            continue

        try:
            with db.begin_nested():
                _apply_changes(entity, transaction, now)
                db.flush()
            applied_count += 1
            results.append(FleetSyncResult(
                transaction_id=transaction.transaction_id,
                entity_type=transaction.entity_type,
                record_id=transaction.record_id,
                status="applied",
                server_updated_at=now.replace(tzinfo=timezone.utc),
            ))
        except (ValueError, TypeError, InvalidOperation) as exc:
            conflict_count += 1
            results.append(FleetSyncResult(
                transaction_id=transaction.transaction_id,
                entity_type=transaction.entity_type,
                record_id=transaction.record_id,
                status="rejected",
                detail=str(exc),
            ))

    sync_status = "success" if conflict_count == 0 else "conflict" if applied_count == 0 else "partial"
    branch.last_sync_timestamp = now
    response = FleetSyncBatchResponse(
        batch_id=batch.batch_id,
        branch_id=batch.branch_id,
        sync_status=sync_status,
        applied_count=applied_count,
        conflict_count=conflict_count,
        results=results,
        last_sync_timestamp=now.replace(tzinfo=timezone.utc),
    )
    audit = BranchSyncAuditLog(
        clinic_id=current_user.clinic_id,
        branch_id=branch.branch_id,
        batch_id=str(batch.batch_id),
        sync_status=sync_status,
        transaction_count=len(batch.transactions),
        applied_count=applied_count,
        conflict_count=conflict_count,
        payload_sha256=payload_hash,
        result_summary=json.dumps(response.model_dump(mode="json"), sort_keys=True, separators=(",", ":")),
    )
    db.add(audit)
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Fleet batch commit failed for clinic %s", current_user.clinic_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Fleet sync batch could not be committed",
        ) from exc
    return response