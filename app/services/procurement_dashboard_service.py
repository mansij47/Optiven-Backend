from app.db import db
from typing import List
from app.models.procurement_models import ProcurementDashboardResponse, MonthlyStats, SupplierContract
from datetime import datetime
from collections import defaultdict

def extract_month(date_str: str) -> str:
    try:
        # Try ISO 8601 format with time
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except ValueError:
        try:
            # Try YYYY-MM-DD format
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return None
    return dt.strftime("%b")  # Returns 'Jan', 'Feb', etc.

async def get_procurement_dashboard_data(store_id: str) -> ProcurementDashboardResponse:
    # 1. Basic Stats
    total_pos = await db.PurchaseOrders.count_documents({"store_id": store_id})
    
    pending_validations = await db.PurchaseOrders.count_documents({
        "store_id": store_id,
        "validation_status": "Pending"
    })
    
    active_contracts = await db.Contracts.count_documents({
        "store_id": store_id,
        "status": "accepted"
    })

    returns_initiated = await db.ReturnOrders.count_documents({"store_id": store_id})

    # 2. Monthly Stats
    po_by_month = defaultdict(int)
    async for doc in db.PurchaseOrders.find({"store_id": store_id}):
        if delivery_date := doc.get("delivery_date"):
            month = extract_month(delivery_date)
            if month:
                po_by_month[month] += 1

    ro_by_month = defaultdict(int)
    async for doc in db.ReturnOrders.find({"store_id": store_id}):
        if return_date := doc.get("return_date"):
            month = extract_month(return_date)
            if month:
                ro_by_month[month] += 1

    months_ordered = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    
    monthly_data = [
        MonthlyStats(
            month=m,
            orders=po_by_month.get(m, 0),
            returns=ro_by_month.get(m, 0)
        ) for m in months_ordered
    ]

    # 3. Recent Supplier Contracts
    contracts_cursor = db.Contracts.find({"store_id": store_id}).sort("created_at", -1).limit(3)
    contracts: List[SupplierContract] = []

    async for doc in contracts_cursor:
        raw_value = doc.get("contract_value", 0)
        value = f"₹{int(raw_value):,}" if isinstance(raw_value, (int, float)) else str(raw_value or "₹0")

        contracts.append(SupplierContract(
            name=doc.get("vendor_name", "Unknown"),
            value=value,
            status=doc.get("status", "unknown").capitalize()
        ))

    return ProcurementDashboardResponse(
        total_purchase_orders=total_pos,
        pending_validations=pending_validations,
        active_contracts=active_contracts,
        returns_initiated=returns_initiated,
        monthly_data=monthly_data,
        supplier_contracts=contracts
    )
    