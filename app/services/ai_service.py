import json
import os
from typing import Any

from google import genai
from google.genai import types


class GeminiServiceError(RuntimeError):
    """Raised when the Gemini service cannot process a clinical workflow."""


def create_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise GeminiServiceError("GEMINI_API_KEY is not configured")
    try:
        return genai.Client(api_key=api_key)
    except Exception as exc:
        raise GeminiServiceError("Gemini client could not be initialized") from exc


async def process_clinical_workflow(
    clinic_id: int,
    workflow: str,
    clinical_data: dict[str, Any],
) -> str:
    from app.services.resilience import call_gemini_resilient

    """Process already clinic-scoped clinical data with Gemini."""
    client = create_gemini_client()
    prompt = (
        f"Clinic context: {clinic_id}\n"
        f"Workflow: {workflow}\n"
        "Clinical data:\n"
        f"{json.dumps(clinical_data, default=str)}"
    )

    try:
        response, _ = await call_gemini_resilient(
            clinic_id=clinic_id,
            gateway="clinical-workflow",
            operation=lambda: client.aio.models.generate_content(
                model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=(
                        "You are a clinical operations assistant for one dental clinic. "
                        "Provide concise operational guidance, not a diagnosis."
                    ),
                ),
            ),
        )
    except Exception as exc:
        raise GeminiServiceError("Gemini workflow failed") from exc
    finally:
        await client.aio.aclose()

    result = response.text
    if not result:
        raise GeminiServiceError("Gemini returned an empty response")
    return result


async def process_inbound_call(
    clinic_id: int,
    clinic_name: str,
    spoken_utterance: str,
    operating_hours: str | None = None,
    scheduling_context: str | None = None,
) -> dict[str, str | None]:
    from app.services.resilience import call_gemini_resilient

    """Create a receptionist response without claiming external actions were completed."""
    client = create_gemini_client()
    prompt = (
        f"You are the call receptionist for {clinic_name}.\n"
        f"Operating hours: {operating_hours or 'Not provided'}\n"
        f"Scheduling context: {scheduling_context or 'No live availability provided'}\n"
        f"Caller transcript: {spoken_utterance}\n"
        "Return only a JSON object with keys voice_response, intent, slot_suggestion. "
        "intent must be one of BOOKING, EMERGENCY, INQUIRY, CANCELLATION. "
        "Do not diagnose, claim an appointment was booked, or claim a message was sent. "
        "slot_suggestion must be null unless specific availability was provided in context. "
        "Keep voice_response concise and empathetic."
    )

    try:
        result, _ = await call_gemini_resilient(
            clinic_id=clinic_id,
            gateway="telephony-triage",
            operation=lambda: client.aio.models.generate_content(
                model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
                contents=prompt,
            ),
        )
    except Exception as exc:
        raise GeminiServiceError("Gemini call triage failed") from exc
    finally:
        await client.aio.aclose()

    try:
        payload = json.loads((result.text or "").strip())
        action = payload["intent"]
        voice_response = payload["voice_response"]
        slot_suggestion = payload.get("slot_suggestion")
        if action not in {"BOOKING", "EMERGENCY", "INQUIRY", "CANCELLATION"}:
            raise ValueError("Unknown intent")
        if not isinstance(voice_response, str) or not voice_response.strip():
            raise ValueError("Missing voice response")
        if slot_suggestion is not None and not isinstance(slot_suggestion, str):
            raise ValueError("Invalid slot suggestion")
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise GeminiServiceError("Gemini returned an invalid call response") from exc

    return {
        "voice_response": voice_response.strip(),
        "intent": action,
        "slot_suggestion": slot_suggestion,
    }