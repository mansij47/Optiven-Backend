from datetime import datetime
from bson import ObjectId
from app.db import db

inventory_collection = db["Inventory"]
loss_orders_collection = db["LossOrders"]
return_to_vendor_collection = db["ReturnToVendor"]
purchase_orders_collection = db["PurchaseOrders"]

async def validate_purchase_order(data, store_id: str, org_id: str):
    # Add to Inventory
    if (data.received_quantity == data.expected_quantity) and not data.is_product_damaged:
        inventory_data = {
            "product_id": data.product_id or f"P{ObjectId()}"[:6],
            "org_id": org_id,
            "store_id": store_id,
            "product_name": data.product_name,
            "is_consumer_returnable": data.is_consumer_returnable,
            "consumer_return_conditions": data.consumer_return_conditions or [],
            "is_seller_returnable": data.returnable,
            "seller_return_conditions": data.return_conditions or [],
            "unit_price": str(data.unit_price),
            "quantity": str(data.received_quantity),
            "category": data.category,
            "sub_category": data.sub_category or "misc",
            "tags": [],
            "tax": data.tax,
            "has_warranty": data.has_warranty,
            "warranty_tenure": data.warranty_tenure,
            "warranty_unit": data.warranty_unit,
            "last_updated": datetime.utcnow().isoformat(),
        }
        await inventory_collection.insert_one(inventory_data)

    # Return to Vendor
    elif (data.received_quantity != data.expected_quantity) or (data.is_product_damaged and data.returnable):
        return_data = {
            "store_id": store_id,
            "org_id": org_id,
            "return_id": f"RV{ObjectId()}"[:6],
            "order_id": data.order_id,
            "vendor_name": data.supplier_name,
            "product_name": data.product_name,
            "delivery_date": data.delivery_date,
            "status": "0",
            "return_amount": str(data.unit_price * (data.expected_quantity - data.received_quantity)),
            "original_quantity": data.expected_quantity,
            "return_quantity": data.expected_quantity - data.received_quantity,
            "unit": data.quantity_unit,
            "contract_id": data.contract_id,
            "purchase_date": datetime.utcnow().strftime("%Y-%m-%d"),
            "product_condition": "Damaged and returnable",
            "total_price": data.unit_price * data.expected_quantity,
            "unit_price": data.unit_price,
            "return_reason": ", ".join(data.return_conditions or ["Mismatch or damaged"])
        }
        await return_to_vendor_collection.insert_one(return_data)

    # Loss Orders
    elif data.is_product_damaged and not data.returnable:
        loss_data = {
            "product_id": data.product_id or f"P{ObjectId()}"[:6],
            "org_id": org_id,
            "store_id": store_id,
            "product_name": data.product_name,
            "category": data.category,
            "date_reported": datetime.utcnow().strftime("%Y-%m-%d"),
            "quantity_lost": data.expected_quantity - data.received_quantity,
            "unit": data.quantity_unit,
            "unit_price": str(data.unit_price),
            "reason": "Damaged and not returnable",
        }
        await loss_orders_collection.insert_one(loss_data)

    # Update validation status in purchase order
    await purchase_orders_collection.update_one(
        {"order_id": data.order_id},
        {"$set": {"validation_status": "Completed", "received_status": "Received"}}
    )

    return {"message": "Validation completed and data stored appropriately."}
