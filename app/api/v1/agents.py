"""
Agents API Router — Production-grade with structured error handling and logging.

All 4 monopoly agent endpoints: Insurance Pre-Auth, Patient Retention,
Inventory Auto-Pilot, and Chair-Side Safety Audit.
"""
import logging
import traceback
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.agents.insurance_agent import InsurancePreAuthAgent
from app.agents.retention_agent import RetentionAgent
from app.agents.inventory_agent import InventoryAgent
from app.agents.audit_agent import ClinicalAuditAgent

logger = logging.getLogger("gfi.agents")

router = APIRouter(prefix="/agents", tags=["Agents"])

# Singleton instances
insurance_agent = InsurancePreAuthAgent()
retention_agent = RetentionAgent()
inventory_agent = InventoryAgent()
audit_agent = ClinicalAuditAgent()


def _error_payload(agent_name: str, exc: Exception) -> dict:
    """Build a structured JSON error payload for any agent failure."""
    return {
        "status": "Error",
        "agent": agent_name,
        "error": str(exc),
        "error_type": type(exc).__name__,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trace": traceback.format_exc().split("\n")[-4:],
    }


@router.post("/insurance/process/{clinic_id}/{treatment_plan_id}")
async def trigger_insurance_agent(
    clinic_id: int, treatment_plan_id: int, db: Session = Depends(get_db)
):
    """Trigger the Autonomous Insurance & Pre-Authorization Agent."""
    try:
        result = await insurance_agent.process_treatment_plan(db, clinic_id, treatment_plan_id)
        if not result:
            raise HTTPException(status_code=404, detail="Treatment plan not found for this clinic.")
        return {
            "status": "Completed",
            "agent": "InsurancePreAuth",
            "claim_id": result.id,
            "packet": result.packet_data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Insurance agent failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=_error_payload("InsurancePreAuth", exc))


@router.post("/retention/scan/{clinic_id}")
async def trigger_retention_agent(clinic_id: int, db: Session = Depends(get_db)):
    """Trigger the Predictive Patient Retention & Reactivation Agent."""
    try:
        results = await retention_agent.scan_and_trigger_recalls(db, clinic_id)
        return {
            "status": "Completed",
            "agent": "PatientRetention",
            "campaigns_created": len(results),
            "details": [{"id": c.id, "reason": c.trigger_reason} for c in results],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        logger.error("Retention agent failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=_error_payload("PatientRetention", exc))


@router.post("/inventory/monitor/{clinic_id}")
async def trigger_inventory_agent(clinic_id: int, db: Session = Depends(get_db)):
    """Trigger the Inventory & Supply Chain Auto-Pilot Agent."""
    try:
        result = await inventory_agent.monitor_and_order(db, clinic_id)
        if not result:
            return {
                "status": "Skipped",
                "agent": "InventoryAutoPilot",
                "message": "All inventory levels are above safety thresholds.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        return {
            "status": "Completed",
            "agent": "InventoryAutoPilot",
            "po_id": result.id,
            "supplier": result.supplier_name,
            "total_cost": float(result.total_cost),
            "items": result.items_json,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        logger.error("Inventory agent failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=_error_payload("InventoryAutoPilot", exc))


@router.post("/audit/check/{clinic_id}/{treatment_plan_id}")
async def trigger_audit_agent(
    clinic_id: int, treatment_plan_id: int, db: Session = Depends(get_db)
):
    """Trigger the Chair-Side Clinical Audit & Compliance Guardrail Agent (synchronous)."""
    try:
        result = await audit_agent.run_safety_check(db, clinic_id, treatment_plan_id)
        if not result:
            raise HTTPException(
                status_code=404,
                detail="Treatment plan not found for this clinic.",
            )
        return {
            "status": "Completed",
            "agent": "ClinicalAuditGuardrail",
            "audit_id": result.id,
            "safety_status": result.safety_status,
            "notes": result.audit_notes,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Audit agent failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=_error_payload("ClinicalAuditGuardrail", exc))
