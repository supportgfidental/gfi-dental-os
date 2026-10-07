import asyncio
import json
import uuid
from sqlalchemy.orm import Session
from app.models.models import InsuranceClaim, TreatmentPlan, Patient
from app.services.llm import generate_json_response

class InsurancePreAuthAgent:
    """
    Autonomous Insurance & Pre-Authorization Agent (Revenue Moat)
    """
    async def process_treatment_plan(self, db: Session, clinic_id: int, treatment_plan_id: int):
        plan = db.query(TreatmentPlan).filter(TreatmentPlan.id == treatment_plan_id, TreatmentPlan.clinic_id == clinic_id).first()
        if not plan:
            return None
            
        patient = db.query(Patient).filter(Patient.id == plan.patient_id).first()
        
        system_prompt = (
            "You are an automated dental insurance clearinghouse agent. Your job is to format a treatment plan "
            "into a standardized ADA Dental Claim packet. Generate the necessary billing codes based on the procedure. "
            "Return JSON ONLY with keys: 'ada_codes' (list of strings), 'estimated_coverage' (float), and 'justification' (string)."
        )
        user_prompt = f"Diagnosis: {plan.diagnosis}\nProcedure: {plan.procedure_name}\nCost: ${plan.cost}"
        
        llm_response = await generate_json_response(system_prompt, user_prompt)
        
        if llm_response.get("simulated"):
            packet = {
                "ada_codes": ["D3330" if "Root Canal" in plan.procedure_name else "D2391"],
                "estimated_coverage": float(plan.cost) * 0.8,
                "justification": "[SIMULATED] Covered under standard restorative benefits."
            }
        else:
            packet = {
                "ada_codes": llm_response.get("ada_codes", []),
                "estimated_coverage": llm_response.get("estimated_coverage", 0.0),
                "justification": llm_response.get("justification", "")
            }
        
        packet["transaction_id"] = str(uuid.uuid4())
        packet["submission_timestamp"] = asyncio.get_event_loop().time()
        
        claim = InsuranceClaim(
            clinic_id=clinic_id,
            patient_id=patient.id,
            treatment_plan_id=plan.id,
            status="Submitted",
            packet_data=json.dumps(packet)
        )
        db.add(claim)
        db.commit()
        db.refresh(claim)
        
        plan.status = "Pre-Auth Submitted"
        db.commit()
        
        return claim
