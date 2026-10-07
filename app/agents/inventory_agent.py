import asyncio
import json
from sqlalchemy.orm import Session
from app.models.models import InventoryItem, PurchaseOrder
from app.services.llm import generate_json_response

class InventoryAgent:
    """
    Inventory & Supply Chain Auto-Pilot Agent (Cost Moat)
    """
    async def monitor_and_order(self, db: Session, clinic_id: int):
        items = db.query(InventoryItem).filter(
            InventoryItem.clinic_id == clinic_id,
            InventoryItem.quantity < 50
        ).all()
        
        if not items:
            return None
            
        items_payload = [{"sku": i.sku, "name": i.name, "current_stock": i.quantity} for i in items]
        
        system_prompt = (
            "You are a dental supply chain procurement agent. Given a list of low-stock inventory items, "
            "determine the best supplier, estimate total cost based on current market rates, and formulate a purchase order. "
            "Return JSON ONLY with keys: 'supplier_name' (string), 'total_cost' (float), and 'reorder_quantities' (dict mapping SKU to integer)."
        )
        user_prompt = f"Low Stock Items: {json.dumps(items_payload)}"
        
        llm_response = await generate_json_response(system_prompt, user_prompt)
        
        if llm_response.get("simulated"):
            supplier = "Henry Schein (Simulated)"
            total_cost = 450.00
            order_data = [{"sku": i.sku, "name": i.name, "order_qty": 100} for i in items]
        else:
            supplier = llm_response.get("supplier_name", "Unknown Supplier")
            total_cost = float(llm_response.get("total_cost", 0.0))
            reorder_q = llm_response.get("reorder_quantities", {})
            order_data = [{"sku": i.sku, "name": i.name, "order_qty": reorder_q.get(i.sku, 100)} for i in items]
            
        po = PurchaseOrder(
            clinic_id=clinic_id,
            supplier_name=supplier,
            items_json=json.dumps(order_data),
            total_cost=total_cost,
            status="Drafted"
        )
        db.add(po)
        db.commit()
        db.refresh(po)
        
        return po
