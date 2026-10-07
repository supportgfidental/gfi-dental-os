import asyncio
import json
from sqlalchemy.orm import Session
from app.models.models import ClinicalAudit, Patient, TreatmentPlan
from app.services.llm import generate_json_response

class ClinicalAuditAgent:
    """
    Chair-Side Clinical Audit & Compliance Guardrail Agent (Risk Moat)
    """
    async def run_safety_check(self, db: Session, clinic_id: int, treatment_plan_id: int):
        plan = db.query(TreatmentPlan).filter(TreatmentPlan.id == treatment_plan_id, TreatmentPlan.clinic_id == clinic_id).first()
        if not plan:
            return None
            
        patient = db.query(Patient).filter(Patient.id == plan.patient_id).first()
        
        # Parse patient medical history
        med_hist_raw = patient.medical_history if patient.medical_history else "{}"
        
        # Query LLM Gateway for intelligent safety checking
        system_prompt = (
            "You are an elite Clinical Audit Guardrail AI agent for a dental SaaS. "
            "Evaluate the following proposed treatment against the patient's medical profile for contraindications. "
            "Return a strict JSON object with fields: "
            "- 'safety_status': 'CLEAR' or 'WARNING' "
            "- 'contraindication_detected': true/false "
            "- 'clinical_note': string detailing any allergy risks (e.g. penicillin vs antibiotic prescriptions)"
        )
        user_prompt = f"Patient Name: {patient.name}\nMedical Profile/Allergies: {med_hist_raw}\nProposed Action: {plan.procedure_name} for Diagnosis: {plan.diagnosis}"
        
        llm_response = await generate_json_response(system_prompt, user_prompt)
        
        if llm_response.get("simulated"):
            allergies = []
            try:
                med_hist = json.loads(med_hist_raw)
                allergies = med_hist.get("allergies", [])
            except Exception:
                pass
            flagged = False
            notes = f"[SIMULATED] '{plan.procedure_name}' safe to proceed."
            if "penicillin" in [a.lower() for a in allergies] and "antibiotic" in plan.procedure_name.lower():
                flagged = True
                notes = "[SIMULATED] DANGER: Patient has penicillin allergy. Prescribe alternative antibiotics."
        else:
            flagged = llm_response.get("contraindication_detected", False)
            if llm_response.get("safety_status") == "WARNING":
                flagged = True
            notes = llm_response.get("clinical_note", f"Procedure {plan.procedure_name} evaluated.")
            
        audit = ClinicalAudit(
            clinic_id=clinic_id,
            patient_id=patient.id,
            procedure_name=plan.procedure_name,
            safety_status="Flagged" if flagged else "Passed",
            audit_notes=notes
        )
        db.add(audit)
        db.commit()
        db.refresh(audit)
        return audit
