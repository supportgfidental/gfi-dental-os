import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.models import IdempotencyRecord

logger = logging.getLogger(__name__)
STALE_PROCESSING_AFTER = timedelta(minutes=10)


def request_digest(payload: Any) -> str:
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump(mode="json")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def reserve_idempotency(
    db: Session,
    *,
    clinic_id: int,
    operation: str,
    key: str,
    digest: str,
) -> IdempotencyRecord:
    now = datetime.utcnow()
    record = (
        db.query(IdempotencyRecord)
        .filter(
            IdempotencyRecord.clinic_id == clinic_id,
            IdempotencyRecord.operation == operation,
            IdempotencyRecord.idempotency_key == key,
        )
        .with_for_update()
        .first()
    )
    if record:
        if record.request_sha256 != digest:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency key was already used with a different request",
            )
        if record.state == "COMPLETED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This operation was already completed; it was not executed again",
            )
        if record.state == "PROCESSING" and now - record.updated_at < STALE_PROCESSING_AFTER:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An operation with this idempotency key is already in progress",
            )
        record.state = "PROCESSING"
        record.updated_at = now
    else:
        record = IdempotencyRecord(
            clinic_id=clinic_id,
            operation=operation,
            idempotency_key=key,
            request_sha256=digest,
            state="PROCESSING",
            created_at=now,
            updated_at=now,
        )
        db.add(record)

    try:
        db.commit()
        db.refresh(record)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A concurrent request already claimed this idempotency key",
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("Unable to reserve idempotency key for operation %s", operation)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Idempotency service is temporarily unavailable",
        ) from exc
    return record


def mark_idempotency_complete(record: IdempotencyRecord) -> None:
    record.state = "COMPLETED"
    record.updated_at = datetime.utcnow()


def mark_idempotency_failed(db: Session, record: IdempotencyRecord) -> None:
    try:
        db.rollback()
        db.add(record)
        record.state = "FAILED"
        record.updated_at = datetime.utcnow()
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Unable to release failed idempotency reservation")