import asyncio
import json
import datetime
from sqlalchemy.orm import Session
from app.models.models import RecallCampaign, Patient, TreatmentPlan
from app.services.llm import generate_json_response

class RetentionAgent:
    """
    Predictive Patient Retention & Reactivation Agent (LTV Moat)
    """
    async def scan_and_trigger_recalls(self, db: Session, clinic_id: int):
        six_months_ago = datetime.datetime.utcnow() - datetime.timedelta(days=180)
        
        treatments = db.query(TreatmentPlan).filter(
            TreatmentPlan.clinic_id == clinic_id,
        ).all()
        
        campaigns_created = []
        for t in treatments:
            patient = db.query(Patient).filter(Patient.id == t.patient_id).first()
            if not patient:
                continue
                
            system_prompt = (
                "You are an expert dental patient retention agent. Analyze the patient's last treatment and demographic info. "
                "Determine if they are due for a recall/follow-up (e.g. 6-month cleaning, post-op check). "
                "Return JSON ONLY with keys: 'needs_recall' (boolean), 'reason' (string), and 'draft_message' (string of personalized SMS)."
            )
            user_prompt = f"Patient Name: {patient.name}\nLast Treatment: {t.procedure_name}\nDate: {t.updated_at.isoformat()}"
            
            llm_response = await generate_json_response(system_prompt, user_prompt)
            
            if llm_response.get("simulated"):
                needs_recall = True
                reason = "[SIMULATED] 6-month periodic cleaning due."
                msg = f"[SIMULATED] Hi {patient.name}, it's time for your follow-up after your {t.procedure_name}!"
            else:
                needs_recall = llm_response.get("needs_recall", False)
                reason = llm_response.get("reason", "Follow-up due.")
                msg = llm_response.get("draft_message", f"Hi {patient.name}, time for your checkup!")
                
            if needs_recall:
                campaign = RecallCampaign(
                    clinic_id=clinic_id,
                    patient_id=patient.id,
                    trigger_reason=reason,
                    status="Drafted"
                )
                db.add(campaign)
                campaigns_created.append(campaign)
                
        db.commit()
        for c in campaigns_created:
            db.refresh(c)
            
        return campaigns_created
