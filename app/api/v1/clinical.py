from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.core.database import get_db
from app.models.models import Patient
from app.services.llm import generate_json_response

router = APIRouter(prefix="/clinical", tags=["Clinical"])

class ToothAuditRequest(BaseModel):
    patient_id: int
    tooth_number: int
    proposed_condition: str

@router.post("/audit-tooth")
async def audit_tooth_action(payload: ToothAuditRequest, db: Session = Depends(get_db)):
    # 1. Fetch real patient from SQLite database
    patient = db.query(Patient).filter(Patient.id == payload.patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found in database")

    # 2. Construct prompt incorporating real database records
    prompt = f"""
    You are an elite Clinical Audit Guardrail AI agent for GFI Dental OS.
    Evaluate the proposed dental treatment against the patient's actual database medical profile.

    Patient Name: {patient.name}
    Known Allergies: {patient.allergies}
    Medical History: {patient.medical_history}
    Surgical Notes: {patient.surgical_notes}
    Proposed Action: Apply {payload.proposed_condition} on Tooth #{payload.tooth_number}

    Return a strict JSON object with:
    - "safety_status": "CLEAR" or "WARNING"
    - "contraindication_detected": true or false
    - "clinical_note": string explaining any allergy or medical risks
    """

    try:
        # 3. Query local FreeLLMAPI gateway via unified client
        # In our llm client, generate_json_response takes system_prompt and user_prompt
        # We'll split the prompt for strict adherence to our unified client interface
        system_prompt = "You are an elite Clinical Audit Guardrail AI agent for GFI Dental OS. Return a strict JSON object."
        user_prompt = prompt
        
        audit_report = await generate_json_response(system_prompt, user_prompt)
        
        # Ensure fallback doesn't crash the payload mapping
        if audit_report.get("simulated"):
            is_warning = "penicillin" in str(patient.allergies).lower() and "antibiotic" in payload.proposed_condition.lower()
            audit_report = {
                "safety_status": "WARNING" if is_warning else "CLEAR",
                "contraindication_detected": is_warning,
                "clinical_note": "[SIMULATED] High risk detected due to allergy profile." if is_warning else "[SIMULATED] No contraindications detected."
            }
            
        return {
            "status": "success",
            "patient": patient.name,
            "checked_allergies": patient.allergies,
            "audit": audit_report
        }
    except Exception as e:
        return {
            "status": "fallback",
            "safety_status": "WARNING",
            "clinical_note": f"Local LLM unreachable, default safety check active: {str(e)}"
        }
