from fastapi import HTTPException
from app.db import db
from app.models.procurement_models import PurchaseOrderResponse

purchase_orders_collection = db["PurchaseOrders"]

# Maps stored integer values to readable status
RECEIVED_MAP = {0: "Waiting", 1: "Received"}
VALIDATION_MAP = {0: "Pending", 1: "Completed"}

async def get_all_purchase_orders(store_id: str):
    cursor = purchase_orders_collection.find({"store_id": store_id}, {"_id": 0})
    result = []
    async for order in cursor:
        # Handle received_status (supports both int and string)
        raw_received = order.get("received_status", 0)
        if isinstance(raw_received, int):
            order["received_status"] = RECEIVED_MAP.get(raw_received, "Waiting")
        elif isinstance(raw_received, str):
            order["received_status"] = raw_received
        else:
            order["received_status"] = "Waiting"

        # Handle validation_status (supports both int and string)
        raw_validation = order.get("validation_status", 0)
        if isinstance(raw_validation, int):
            order["validation_status"] = VALIDATION_MAP.get(raw_validation, "Pending")
        elif isinstance(raw_validation, str):
            order["validation_status"] = raw_validation
        else:
            order["validation_status"] = "Pending"

        result.append(PurchaseOrderResponse(**order))
    return result


async def mark_purchase_order_as_received(order_id: str) -> dict:
    existing_order = await purchase_orders_collection.find_one({"order_id": order_id})
    
    if not existing_order:
        raise HTTPException(status_code=404, detail="Purchase Order not found")

    # Set numeric value for consistent mapping
    await purchase_orders_collection.update_one(
        {"order_id": order_id},
        {"$set": {"received_status": 1}}
    )
    
    return {"message": "Purchase Order marked as received successfully"}
