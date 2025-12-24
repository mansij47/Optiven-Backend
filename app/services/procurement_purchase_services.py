from fastapi import HTTPException
from fastapi.responses import FileResponse
from app.db import db
from app.models.procurement_models import PurchaseOrderResponse, PurchaseOrderDetailResponse
from app.utils.purchase_order_pdf_utils import generate_purchase_order_pdf_from_schema
import os

purchase_orders_collection = db["PurchaseOrders"]
stores_collection = db["Stores"]

# Maps stored integer values to readable status
RECEIVED_MAP = {0: "Waiting", 1: "Received"}
VALIDATION_MAP = {0: "Pending", 1: "Completed"}

async def get_all_purchase_orders(store_id: str):
    # 👇 Added sort so latest entries come first
    cursor = purchase_orders_collection.find(
        {"store_id": store_id}, {"_id": 0}
    ).sort("_id", -1)

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

async def get_purchase_order_by_id(order_id: str, store_id: str):
    order = await purchase_orders_collection.find_one(
        {"order_id": order_id, "store_id": store_id}, {"_id": 0}
    )
    if not order:
        raise HTTPException(status_code=404, detail="Purchase Order not found")

    # received_status normalize
    raw_received = order.get("received_status", 0)
    if isinstance(raw_received, int):
        order["received_status"] = RECEIVED_MAP.get(raw_received, "Waiting")
    elif isinstance(raw_received, str):
        order["received_status"] = raw_received
    else:
        order["received_status"] = "Waiting"

    # validation_status normalize
    raw_validation = order.get("validation_status", 0)
    if isinstance(raw_validation, int):
        order["validation_status"] = VALIDATION_MAP.get(raw_validation, "Pending")
    elif isinstance(raw_validation, str):
        order["validation_status"] = raw_validation
    else:
        order["validation_status"] = "Pending"

    return PurchaseOrderDetailResponse(**order)



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


async def generate_purchase_order_pdf_service(order_id: str, store_id: str):
    """
    Generate PDF for a purchase order
    
    Args:
        order_id: Purchase order ID
        store_id: Store ID for validation
        
    Returns:
        FileResponse: PDF file response
    """
    # Fetch the order details
    order = await purchase_orders_collection.find_one(
        {"order_id": order_id, "store_id": store_id}, {"_id": 0}
    )
    
    if not order:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
    
    # Fetch store name from Stores collection
    print(f"🔍 Fetching store name for store_id: {store_id}")
    store = await stores_collection.find_one({"store_id": store_id}, {"_id": 0, "store_name": 1})
    print(f"🔍 Store found: {store}")
    if store and "store_name" in store:
        order["store_name"] = store["store_name"]
        print(f"✅ Added store_name to order: {store['store_name']}")
    else:
        print(f"❌ Store name not found for store_id: {store_id}")
        order["store_name"] = "-"
    
    print(f"🔍 Order data before Pydantic model: store_name = {order.get('store_name', 'NOT SET')}")
    
    # Normalize status fields
    raw_received = order.get("received_status", 0)
    if isinstance(raw_received, int):
        order["received_status"] = RECEIVED_MAP.get(raw_received, "Waiting")
    elif isinstance(raw_received, str):
        order["received_status"] = raw_received
    else:
        order["received_status"] = "Waiting"

    raw_validation = order.get("validation_status", 0)
    if isinstance(raw_validation, int):
        order["validation_status"] = VALIDATION_MAP.get(raw_validation, "Pending")
    elif isinstance(raw_validation, str):
        order["validation_status"] = raw_validation
    else:
        order["validation_status"] = "Pending"
    
    # Create response model
    order_response = PurchaseOrderDetailResponse(**order)
    
    # Generate PDF using temporary file (no permanent storage)
    try:
        pdf_path = generate_purchase_order_pdf_from_schema(order_response, output_dir=None)
        
        if not os.path.exists(pdf_path):
            raise HTTPException(status_code=500, detail="Failed to generate PDF")
        
        return FileResponse(
            path=pdf_path,
            media_type='application/pdf',
            filename=f"PurchaseOrder_{order_id}.pdf",
            headers={
                "Content-Disposition": f"attachment; filename=PurchaseOrder_{order_id}.pdf"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")
