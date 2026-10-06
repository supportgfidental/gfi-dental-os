import logging

from fastapi import Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.models import SecurityAuditLog, User

logger = logging.getLogger(__name__)


def record_security_event(
    db: Session,
    request: Request,
    event_type: str,
    user: User | None = None,
) -> None:
    client = request.client
    db.add(
        SecurityAuditLog(
            user_id=user.id if user else None,
            clinic_id=user.clinic_id if user else None,
            event_type=event_type,
            ip_address=client.host if client else "unknown",
        )
    )
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Failed to persist security audit event %s", event_type)