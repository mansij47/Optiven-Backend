from datetime import datetime
from fastapi import HTTPException
from app.db import db
from app.services.notification_service import create_notification
from app.utils.raise_order import generate_request_id  # Motor async MongoDB client


async def get_all_requested_orders(store_id: str):
    try:
        # Sort by updated_at (desc) to show recently updated requests first, fallback to created_at
        cursor = db.RequestedOrders.find({"store_id": store_id}).sort([
            ("updated_at", -1),
            ("created_at", -1)
        ])
        orders = []

        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            orders.append(doc)

        return orders

    except Exception as e:
        raise Exception(f"Error fetching requested orders: {str(e)}")
    

# this is sales wala
async def prepare_request_data(order_id: str, store_id: str, estimate_date: str, org_id: str, requester: dict):
    order = await db.SalesOrders.find_one({"order_id": order_id, "store_id": store_id}, {"_id":0})
    if not order or not order.get("products"):
        raise HTTPException(status_code=404, detail="Sales order or products not found.")

    product = order["products"][0]
    product_name = product["product_name"]
    category = product["category"]
    unit = "pcs"  # Hardcoded, adjust if needed
    order_quantity = product.get("order_quantity", 0)

    inventory_item = await db.Inventory.find_one({"product_name": product_name, "store_id": store_id}, {"_id":0})
    if not inventory_item:
        raise HTTPException(status_code=404, detail="Product not found in inventory.")

    # ✅ Count available items from ProductItems (not Inventory.quantity)
    inventory_quantity = await db.ProductItems.count_documents({
        "product_id": inventory_item.get("product_id"),
        "store_id": store_id,
        "status": "available"
    })

    requested_quantity = max(order_quantity - inventory_quantity, 0)
    if requested_quantity <= 0:
        raise HTTPException(status_code=400, detail="No extra quantity to request.")

    return {
        "org_id": org_id,
        "store_id": store_id,
        "product_name": product_name,
        "quantity": requested_quantity,
        "unit": unit,
        "category": category,
        "estimate_date": estimate_date,
        "requested_by": requester
    }

async def raise_request_order_service(order_id: str, estimate_date: str, org_id: str, store_id: str, requester: dict):
    request_data = await prepare_request_data(order_id, store_id, estimate_date, org_id, requester)
    
    # Check if product already exists in requested orders
    existing_request = await db.RequestedOrders.find_one({
        "product_name": request_data["product_name"],
        "store_id": store_id,
        "org_id": org_id
    })
    
    if existing_request:
        # Update existing request: add quantities and update other fields
        new_quantity = existing_request.get("quantity", 0) + request_data["quantity"]
        
        await db.RequestedOrders.update_one(
            {"_id": existing_request["_id"]},
            {
                "$set": {
                    "quantity": new_quantity,
                    "estimate_date": estimate_date,
                    "requested_by": requester,
                    "updated_at": datetime.utcnow()  # store as real datetime
                }
            }
        )
        return existing_request["request_id"]
    else:
        # Create new request
        request_id = await generate_request_id()
        request_data["request_id"] = request_id
        request_data["created_at"] = datetime.utcnow()  # real datetime
        request_data["updated_at"] = datetime.utcnow()  # real datetime
        
        await db.RequestedOrders.insert_one(request_data)
        return request_id

#admin wala - directly requesting for new product

async def generate_request_id():
    latest = await db.RequestedOrders.find_one({}, sort=[("request_id", -1)])
    if latest and "request_id" in latest:
        last_num = int(latest["request_id"].replace("REQ", ""))
        return f"REQ{last_num + 1:03d}"
    else:
        return "REQ001"

async def raise_order_request_service(data: dict, org_id: str, store_id: str, requested_by: dict):
    # Check if product already exists in requested orders
    existing_request = await db.RequestedOrders.find_one({
        "product_name": data["product_name"],
        "store_id": store_id,
        "org_id": org_id
    })
    
    if existing_request:
        # Update existing request: add quantities and update other fields
        new_quantity = existing_request.get("quantity", 0) + data["quantity"]
        
        await db.RequestedOrders.update_one(
            {"_id": existing_request["_id"]},
            {
                "$set": {
                    "quantity": new_quantity,
                    "unit": data.get("unit", "pcs"),
                    "category": data.get("category", "general"),
                    "sub_category": data.get("sub_category", ""),
                    "estimate_date": data.get("estimate_date", datetime.utcnow().strftime("%Y-%m-%d")),  # keep date-only string
                    "requested_by": requested_by,
                    "updated_at": datetime.utcnow()  # real datetime
                }
            }
        )
        return {"message": "Request updated successfully (quantity added to existing request)", "request_id": existing_request["request_id"]}
    else:
        # Create new request
        request_id = await generate_request_id()
        
        request_doc = {
            "request_id": request_id,
            "org_id": org_id,
            "store_id": store_id,
            "product_name": data["product_name"],
            "quantity": data["quantity"],
            "unit": data.get("unit", "pcs"),
            "category": data.get("category", "general"),
            "sub_category": data.get("sub_category", ""),
            "estimate_date": data.get("estimate_date", datetime.utcnow().strftime("%Y-%m-%d")),
            "requested_by": requested_by,
            "created_at": datetime.utcnow(),  # real datetime
            "updated_at": datetime.utcnow()  # real datetime
        }
        await db.RequestedOrders.insert_one(request_doc)
        return {"message": "Request raised successfully", "request_id": request_id}