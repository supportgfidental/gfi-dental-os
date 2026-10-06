import asyncio
import logging
import os
import re
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

from google.genai import types
from pydantic import BaseModel, Field

from app.services.ai_service import GeminiServiceError, create_gemini_client
from app.services.resilience import call_gemini_resilient

logger = logging.getLogger(__name__)
CDT_CODE_PATTERN = re.compile(r"^D\d{4}$")


class ClaimsAssessment(BaseModel):
    claim_validity_status: Literal["APPROVED", "PENDING_DOCS", "REJECTED_POLICY_MISMATCH"]
    confidence_score: int = Field(ge=0, le=100)
    compliance_notes: list[str] = Field(max_length=30)
    billable_codes: list[str] = Field(max_length=20)


async def audit_claim(
    clinic_id: int,
    patient_treatment_description: str,
    procedure_codes: list[str],
    insurance_provider_rules: str,
    regional_tariffs: dict[str, Decimal],
) -> dict[str, object]:
    client = create_gemini_client()
    prompt = f"""
Review a proposed dental insurance claim. This is advisory pre-submission review, not an insurer decision.
Use only the supplied treatment description, CDT codes, provider rules, and tariff values.
Do not invent coverage criteria, documentation, or tariff amounts. If documentation is missing or
policy is unclear, use PENDING_DOCS. Use REJECTED_POLICY_MISMATCH only for an explicit conflict
with the supplied rules. Only include supplied CDT codes in billable_codes.

Return JSON with claim_validity_status (APPROVED, PENDING_DOCS, REJECTED_POLICY_MISMATCH),
confidence_score (integer 0-100), compliance_notes (array of strings), and billable_codes (array).

Treatment description: {patient_treatment_description}
CDT codes: {procedure_codes}
Insurance provider rules: {insurance_provider_rules}
Regional tariff amounts: {regional_tariffs}
"""
    try:
        try:
            timeout_seconds = min(max(float(os.getenv("CLAIMS_AI_TIMEOUT_SECONDS", "12")), 1.0), 30.0)
        except ValueError:
            timeout_seconds = 12.0
        response, _ = await call_gemini_resilient(
            clinic_id=clinic_id,
            gateway="claims-audit",
            timeout_seconds=timeout_seconds,
            max_attempts=2,
            operation=lambda: client.aio.models.generate_content(
                    model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
                    contents=prompt,
                    config=types.GenerateContentConfig(response_mime_type="application/json"),
            ),
        )
    except Exception as exc:
        raise GeminiServiceError("Claims audit model request failed") from exc
    finally:
        try:
            await client.aio.aclose()
        except Exception:
            logger.exception("Failed to close Gemini client after claims audit")

    try:
        assessment = ClaimsAssessment.model_validate_json(response.text or "")
    except Exception as exc:
        raise GeminiServiceError("Claims audit returned an invalid structured response") from exc

    requested_codes = set(procedure_codes)
    approved_codes = sorted(set(assessment.billable_codes) & requested_codes)
    notes = list(assessment.compliance_notes)
    excluded_codes = sorted(set(assessment.billable_codes) - requested_codes)
    if excluded_codes:
        notes.append("Model returned unsubmitted procedure codes; they were excluded from payout calculation.")

    missing_tariffs = sorted(requested_codes - regional_tariffs.keys())
    if missing_tariffs:
        notes.append(f"No regional tariff supplied for: {', '.join(missing_tariffs)}; excluded from projection.")

    if assessment.claim_validity_status == "REJECTED_POLICY_MISMATCH":
        estimated_payout = Decimal("0.00")
    else:
        estimated_payout = sum(
            (regional_tariffs[code] for code in approved_codes if code in regional_tariffs),
            start=Decimal("0.00"),
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return {
        "claim_validity_status": assessment.claim_validity_status,
        "confidence_score": assessment.confidence_score,
        "compliance_notes": notes,
        "billable_codes": approved_codes,
        "estimated_payout": estimated_payout,
    }