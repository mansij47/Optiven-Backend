# services/procurement_validation_services.py
from fastapi import HTTPException
from bson import ObjectId
from app.db import db
from app.models.procurement_models import PurchaseOrderValidationInput, PurchaseOrderValidationRequest, PurchaseOrderSubmitRequest

async def validate_purchase_order_preview(
    data: PurchaseOrderValidationInput, store_id: str, org_id: str
):
    """
    Frontend se sirf 4-5 fields aati hain.
    Baaki details DB se order_id ke base par fetch hoke merge hoti hain.
    """

  
    order = await db["PurchaseOrders"].find_one({"order_id": data.order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Purchase order not found.")

    # 🔹 Merge karo (DB details + frontend input)
    merged_data = {
        "order_id": str(order["_id"]),
        "contract_id": order.get("contract_id"),
        "delivery_date": order.get("delivery_date"),
        "vendor_name": order.get("vendor_name"),
        "expected_quantity": data.expected_quantity,
        "received_quantity": data.received_quantity,
        "unit": order.get("unit"),
        "is_product_damaged": data.is_product_damaged,
        "returnable": order.get("returnable"),
        "return_conditions": order.get("return_conditions", []),
        "is_consumer_returnable": order.get("is_consumer_returnable", False),
        "consumer_return_conditions": order.get("consumer_return_conditions", []),
        "unit_price": order.get("unit_price"),
        "category": order.get("category"),
        "product_name": order.get("product_name"),
        "sub_category": order.get("sub_category"),
        "has_warranty": order.get("has_warranty", False),
        "warranty_tenure": order.get("warranty_tenure", 0),
        "warranty_unit": order.get("warranty_unit", "months"),
        "tax": order.get("tax", 0),
        "product_id": order.get("product_id"),
        "selected_action": data.selected_action,
    }

    # Pydantic model banake validate karo
    full_request = PurchaseOrderValidationRequest(**merged_data)

    # 👇 Tera pura decision logic call
    return await _run_validation_logic(full_request, store_id, org_id)


async def _run_validation_logic(data: PurchaseOrderValidationRequest, store_id: str, org_id: str):
    """
    Yeh wahi tera pura decision logic hai jo tu already likh chuka hai
    (damaged / returnable / inventory / loss logic).
    """

    # ✅ Case 1: Agar product damaged nahi hai
    if not data.is_product_damaged:
        if data.selected_action == "ReturnToVendor":
            if data.returnable:
                return {
                    "message": "♻️ Product undamaged hai par returnable true hai, ReturnToVendor me jayega.",
                    "collection": "ReturnToVendor",
                    "payload": data.dict(),
                    "store_id": store_id,
                    "org_id": org_id
                }
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Undamaged product aur returnable false hone par ReturnToVendor nahi ho sakta."
                )

        elif data.selected_action in [None, "Inventory"]:
            return {
                "message": "✅ Product undamaged hai, Inventory me jayega.",
                "collection": "Inventory",
                "payload": data.dict(),
                "store_id": store_id,
                "org_id": org_id
            }

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid selected_action `{data.selected_action}` for undamaged product."
            )

    # ✅ Case 2: Damaged + returnable
    if data.is_product_damaged and data.returnable:
        if data.selected_action in [None, "ReturnToVendor"]:
            return {
                "message": "♻️ Product damaged hai aur returnable true hai, ReturnToVendor me jayega.",
                "collection": "ReturnToVendor",
                "payload": data.dict(),
                "store_id": store_id,
                "org_id": org_id
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid selected_action `{data.selected_action}` for damaged + returnable product."
            )

    # ✅ Case 3: Damaged + not returnable
    if data.is_product_damaged and not data.returnable:
        if data.selected_action in [None, "LossOrders"]:
            return {
                "message": "❌ Product damaged hai aur returnable false hai, LossOrders me jayega.",
                "collection": "LossOrders",
                "payload": data.dict(),
                "store_id": store_id,
                "org_id": org_id
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid selected_action `{data.selected_action}` for damaged + non-returnable product."
            )

    raise HTTPException(status_code=400, detail="Invalid payload / condition match nahi hui.")


import uuid
from datetime import datetime

def generate_id(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:6].upper()}"

async def submit_purchase_order(data: PurchaseOrderSubmitRequest, store_id: str, org_id: str):
    base_order = await db["PurchaseOrders"].find_one({"order_id": data.order_id})
    if not base_order:
        raise HTTPException(status_code=404, detail="Order not found")

    # --- INVENTORY CASE ---
    if data.selected_action == "Inventory":
        final_doc = {
            "product_id": generate_id("PRD"),
            "org_id": org_id,
            "store_id": store_id,
            "product_name": base_order.get("product_name"),
            "is_consumer_returnable": data.is_consumer_returnable,
            "consumer_return_conditions": data.consumer_return_conditions,
            "is_seller_returnable": base_order.get("returnable", False),
            "seller_return_conditions": base_order.get("return_conditions", []),
            "unit_price": str(base_order.get("unit_price", "0")),
            "unit": base_order.get("unit"),
            "quantity": data.received_quantity,
            "category": base_order.get("category"),
            "sub_category": base_order.get("sub_category", ""),
            "tags": [],
            "tax": float(base_order.get("tax", 0)),
            "has_warranty": base_order.get("has_warranty", False),
            "warranty_tenure": base_order.get("warranty_tenure", 0),
            "warranty_unit": base_order.get("warranty_unit", "months"),
            "last_updated": str(datetime.now()),
            "status": "active",
        }
        target_collection = db["Inventory"]

    # --- LOSS ORDERS CASE ---
    elif data.selected_action == "LossOrders":
        final_doc = {
            "product_id": generate_id("PRD"),
            "org_id": org_id,
            "store_id": store_id,
            "product_name": base_order.get("product_name"),
            "category": base_order.get("category"),
            "date_reported": str(datetime.now().date()),
            "quantity_lost": data.received_quantity,
            "unit": base_order.get("unit"),
            "unit_price": str(base_order.get("unit_price", "0")),
            "reason": "Damaged & Not Returnable",
        }
        target_collection = db["LossOrders"]

    # --- RETURN TO VENDOR CASE ---
    elif data.selected_action == "ReturnToVendor":
        final_doc = {
            "return_id": generate_id("RTV"),
            "order_id": data.order_id,
            "vendor_name": base_order.get("vendor_name"),
            "product_name": base_order.get("product_name"),
            "delivery_date": base_order.get("delivery_date"),
            "status": 1,
            "return_amount": str(data.received_quantity * float(base_order.get("unit_price", 0))),
            "original_quantity": data.expected_quantity,
            "return_quantity": data.received_quantity,
            "unit": base_order.get("unit"),
            "contract_id": base_order.get("contract_id"),
            "purchase_date": str(datetime.now().date()),
            "product_condition": "Damaged",
            "total_price": int(data.received_quantity * float(base_order.get("unit_price", 0))),
            "unit_price": int(base_order.get("unit_price", 0)),
            "return_reason": "Damaged on Delivery",
            "store_id": store_id,
            "org_id": org_id,
        }
        target_collection = db["ReturnToVendor"]

    else:
        raise HTTPException(status_code=400, detail="Invalid selected_action")

    # Insert document
    result = await target_collection.insert_one(final_doc)
    final_doc["_id"] = str(result.inserted_id)
    return final_doc
