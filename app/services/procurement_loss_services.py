from fastapi import HTTPException
from app.models.procurement_models import LossOrder
from app.db import db  
from bson.objectid import ObjectId

#List of Loss Orders
async def get_loss_orders_by_store(store_id: str):
    cursor = db["LossOrders"].find({"store_id": store_id}).sort("_id", -1)  # latest first
    loss_orders = []

    async for order in cursor:
        order.pop("_id", None)  # remove Mongo ObjectId

        quantity = order.get("quantity_lost", 0)
        price = order.get("unit_price", 0.0)

        try:
            loss = float(quantity) * float(price)
        except (ValueError, TypeError):
            loss = 0.0

        # ✅ Add `loss_amount` just for response
        order["loss_amount"] = round(loss, 2)
        
        # ✅ Fetch complete item details from ProductItems collection
        damaged_item_ids = order.get("damaged_item_ids", [])
        if damaged_item_ids:
            items_details = []
            for item_id in damaged_item_ids:
                item_doc = await db.ProductItems.find_one(
                    {"item_id": item_id, "store_id": store_id},
                    {"_id": 0}
                )
                if item_doc:
                    items_details.append({
                        "item_id": item_doc.get("item_id"),
                        "item_name": item_doc.get("item_name"),
                        "vendor_id": item_doc.get("vendor_id"),
                        "vendor_name": item_doc.get("vendor_name"),
                        "contract_id": item_doc.get("contract_id"),
                        "unit_price": item_doc.get("unit_price"),
                        "batch_number": item_doc.get("batch_number"),
                        "serial_number": item_doc.get("serial_no"),
                        "status": item_doc.get("status"),
                        "has_warranty": item_doc.get("has_warranty", False),
                        "warranty_tenure": item_doc.get("warranty_tenure", 0),
                        "warranty_unit": item_doc.get("warranty_unit", "months"),
                        "is_consumer_returnable": item_doc.get("is_consumer_returnable", False),
                        "consumer_return_conditions": item_doc.get("consumer_return_conditions", []),
                        "is_seller_returnable": item_doc.get("is_seller_returnable", False),
                        "seller_return_conditions": item_doc.get("seller_return_conditions", []),
                        "created_at": item_doc.get("created_at"),
                        "updated_at": item_doc.get("updated_at")
                    })
            
            order["items_details"] = items_details
            order["item_count"] = len(items_details)
            order["has_item_details"] = len(items_details) > 0
        else:
            order["items_details"] = []
            order["item_count"] = 0
            order["has_item_details"] = False

        loss_orders.append(order)

    return loss_orders  # will be [] if no docs


#Veiw loss order details by Product_id 
async def get_loss_orders_by_product_id(product_id: str, store_id: str):
    cursor = db.LossOrders.find({
        "product_id": product_id,
        "store_id": store_id
    })

    loss_orders = []

    async for order in cursor:
        order.pop("_id", None)

        quantity = order.get("quantity_lost", 0)
        price = order.get("unit_price", 0.0)

        try:
            loss = float(quantity) * float(price)
        except (ValueError, TypeError):
            loss = 0.0

        # ✅ Add `loss_amount` just for response
        order["loss_amount"] = round(loss, 2)
        
        # ✅ Fetch complete item details from ProductItems collection
        damaged_item_ids = order.get("damaged_item_ids", [])
        if damaged_item_ids:
            items_details = []
            for item_id in damaged_item_ids:
                item_doc = await db.ProductItems.find_one(
                    {"item_id": item_id, "store_id": store_id},
                    {"_id": 0}
                )
                if item_doc:
                    items_details.append({
                        "item_id": item_doc.get("item_id"),
                        "item_name": item_doc.get("item_name"),
                        "vendor_id": item_doc.get("vendor_id"),
                        "vendor_name": item_doc.get("vendor_name"),
                        "contract_id": item_doc.get("contract_id"),
                        "unit_price": item_doc.get("unit_price"),
                        "batch_number": item_doc.get("batch_number"),
                        "serial_number": item_doc.get("serial_no"),
                        "status": item_doc.get("status"),
                        "has_warranty": item_doc.get("has_warranty", False),
                        "warranty_tenure": item_doc.get("warranty_tenure", 0),
                        "warranty_unit": item_doc.get("warranty_unit", "months"),
                        "is_consumer_returnable": item_doc.get("is_consumer_returnable", False),
                        "consumer_return_conditions": item_doc.get("consumer_return_conditions", []),
                        "is_seller_returnable": item_doc.get("is_seller_returnable", False),
                        "seller_return_conditions": item_doc.get("seller_return_conditions", []),
                        "created_at": item_doc.get("created_at"),
                        "updated_at": item_doc.get("updated_at")
                    })
            
            order["items_details"] = items_details
            order["item_count"] = len(items_details)
            order["has_item_details"] = len(items_details) > 0
        else:
            order["items_details"] = []
            order["item_count"] = 0
            order["has_item_details"] = False

        loss_orders.append(order)

    if not loss_orders:
        raise HTTPException(status_code=404, detail="No loss orders found for this product in your store.")

    return loss_orders