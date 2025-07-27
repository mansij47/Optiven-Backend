from fastapi import HTTPException
from datetime import datetime
from app.db import db
from app.models.procurement_models import ReturnValidationRequest

# MongoDB collections
return_orders_collection = db["ReturnOrders"]
loss_orders_collection = db["LossOrders"]
return_to_vendor_collection = db["ReturnToVendor"]
inventory_collection = db["Inventory"]

#Validation of Return Orders (ReturnToVendor, Loss & Inventory)
async def validate_return_order(data: ReturnValidationRequest, store_id: str, org_id: str = None):
    # Find return order by return_id and store_id
    return_order = await return_orders_collection.find_one({
        "return_id": data.return_id,
        "store_id": store_id
    })

    if not return_order:
        raise HTTPException(status_code=404, detail="Return order not found for given return_id and store_id")

    # Access the first product (adjust if handling multiple in future)
    product = return_order["product"][0]

    reason = return_order.get("reason", "")
    is_seller_returnable = return_order.get("is_seller_returnable", False)

    # ✅ CASE 1: Product Damage & Seller Returnable → ReturnToVendor
    if reason == "Product Damage" and is_seller_returnable:
        await return_to_vendor_collection.insert_one({
            "return_id": return_order["return_id"],
            "order_id": return_order["order_id"],
            "store_id": store_id,
            "org_id": org_id,
            "vendor_name": product.get("vendor_name", "Unknown"),
            "product_name": product["product_name"],
            "delivery_date": product.get("delivery_date", datetime.now().strftime("%Y-%m-%d")),
            "status": "0",
            "return_amount": str(product.get("return_amount", "0.0")),
            "original_quantity": product.get("original_quantity", product["return_quantity"]),
            "return_quantity": product["return_quantity"],
            "unit": product.get("unit", "pcs"),
            "contract_id": product.get("contract_id", "UNKNOWN"),
            "purchase_date": product.get("purchase_date", datetime.now().strftime("%Y-%m-%d")),
            "product_condition": "Damaged and returnable",
            "total_price": product.get("total_price", product["return_quantity"] * product.get("unit_price", 0)),
            "unit_price": product.get("unit_price", 0),
            "return_reason": return_order.get("seller_return_conditions", ["Unknown"])[0]
        })
        action = "Added to ReturnToVendor"

    # ✅ CASE 2: Product Damage & NOT Seller Returnable → LossOrders
    elif reason == "Product Damage" and not is_seller_returnable:
        await loss_orders_collection.insert_one({
            "product_id": product["product_id"],
            "org_id": org_id,
            "store_id": store_id,
            "product_name": product["product_name"],
            "category": product.get("category", "stationery"),
            "date_reported": datetime.now().strftime("%Y-%m-%d"),
            "quantity_lost": product["return_quantity"],
            "unit": product.get("unit", "pcs"),
            "unit_price": str(product.get("unit_price", "0")),
            "reason": "Damaged and not returnable"
        })
        action = "Added to LossOrders"

    # ✅ CASE 3: Not Product Damage → Inventory
    else:
        await inventory_collection.insert_one({
            "product_id": product["product_id"],
            "org_id": org_id,
            "store_id": store_id,
            "product_name": product["product_name"],
            "is_consumer_returnable": return_order.get("is_customer_returnable", False),
            "consumer_return_conditions": return_order.get("consumer_return_conditions", []),
            "is_seller_returnable": return_order.get("is_seller_returnable", False),
            "seller_return_conditions": return_order.get("seller_return_conditions", []),
            "unit_price": str(product.get("unit_price", "0.0")),
            "quantity": product["return_quantity"],
            "category": product.get("category", "stationery"),
            "sub_category": product.get("sub_category", "misc"),
            "tags": product.get("tags", []),
            "tax": product.get("tax", 0),
            "has_warranty": product.get("has_warranty", False),
            "warranty_tenure": product.get("warranty_tenure", 0),
            "warranty_unit": product.get("warranty_unit", "months"),
            "last_updated": datetime.now().isoformat()
        })
        action = "Added to Inventory"

    # ✅ Delete the return order after processing
    await return_orders_collection.delete_one({
        "return_id": data.return_id,
        "store_id": store_id
    })

    return {"message": f"Validation successful. {action}."}
