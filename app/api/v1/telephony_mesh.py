import hmac
import logging
import os
from time import perf_counter
from uuid import uuid4

from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.v1.deps import verify_active_dentist
from app.core.database import get_db
from app.models.models import Clinic, TelephonyCall, User, VerificationStatus
from app.services.ai_service import GeminiServiceError, process_inbound_call
from app.services.idempotency import (
    mark_idempotency_complete,
    mark_idempotency_failed,
    request_digest,
    reserve_idempotency,
)

router = APIRouter(prefix="/api/v1/telephony", tags=["Clinic Telephony"])
logger = logging.getLogger(__name__)


class TelephonyWebhookRequest(BaseModel):
    destination_number: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    caller_hash: str = Field(pattern=r"^[A-Fa-f0-9]{64}$")
    spoken_utterance: str = Field(min_length=1, max_length=2000)


class TelephonyWebhookResponse(BaseModel):
    status: str
    clinic_id: int
    call_id: str
    latency_ms: int
    telephony_payload: dict[str, object]


class TelephonyCallLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    intent: str | None
    processing_ms: int | None
    created_at: datetime


@router.get("/calls", response_model=list[TelephonyCallLogResponse])
def get_telephony_calls(
    limit: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_active_dentist),
):
    return (
        db.query(TelephonyCall)
        .filter(TelephonyCall.clinic_id == current_user.clinic_id)
        .order_by(TelephonyCall.created_at.desc())
        .limit(limit)
        .all()
    )


@router.post("/inbound-call-handler", response_model=TelephonyWebhookResponse)
async def handle_inbound_call(
    data: TelephonyWebhookRequest,
    db: Session = Depends(get_db),
    webhook_secret: str | None = Header(default=None, alias="X-Telephony-Webhook-Secret"),
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=36, max_length=36),
):
    configured_secret = os.getenv("TELEPHONY_WEBHOOK_SECRET")
    if not configured_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telephony webhook is not configured",
        )
    if webhook_secret is None or not hmac.compare_digest(webhook_secret, configured_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid telephony webhook credentials",
        )

    clinic = (
        db.query(Clinic)
        .filter(
            Clinic.registered_mobile == data.destination_number,
            Clinic.subscription_status == "active",
            Clinic.verification_status == VerificationStatus.VERIFIED,
        )
        .first()
    )
    if clinic is None:
        raise HTTPException(status_code=404, detail="Active clinic number not found")

    idempotency_record = reserve_idempotency(
        db,
        clinic_id=clinic.id,
        operation="telephony-inbound-call",
        key=idempotency_key,
        digest=request_digest(data),
    )

    call_event = TelephonyCall(id=str(uuid4()), clinic_id=clinic.id, status="processing")
    db.add(call_event)
    db.commit()

    started_at = perf_counter()
    try:
        response = await process_inbound_call(
            clinic_id=clinic.id,
            clinic_name=clinic.name,
            spoken_utterance=data.spoken_utterance,
            operating_hours=clinic.operating_hours,
            scheduling_context=clinic.scheduling_context,
        )
    except GeminiServiceError as exc:
        call_event.status = "failed"
        call_event.processing_ms = round((perf_counter() - started_at) * 1000)
        db.commit()
        mark_idempotency_failed(db, idempotency_record)
        logger.exception("Inbound-call AI processing failed for clinic %s", clinic.id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI call processing is temporarily unavailable",
        ) from exc

    latency_ms = round((perf_counter() - started_at) * 1000)
    call_event.status = "processed"
    call_event.intent = response["intent"]
    call_event.processing_ms = latency_ms
    mark_idempotency_complete(idempotency_record)
    db.commit()
    return TelephonyWebhookResponse(
        status="success",
        clinic_id=clinic.id,
        call_id=call_event.id,
        latency_ms=latency_ms,
        telephony_payload={
            "synthesize_speech": response["voice_response"],
            "intent_suggestion": response["intent"],
            "slot_suggestion": response["slot_suggestion"],
            "hangup": False,
        },
    )