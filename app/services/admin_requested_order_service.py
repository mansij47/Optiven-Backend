from datetime import datetime
from fastapi import HTTPException
from app.db import db
from app.services.notification_service import create_notification
from app.utils.raise_order import generate_request_id  # Motor async MongoDB client


async def get_all_requested_orders(store_id: str):
    try:
        cursor = db.RequestedOrders.find({"store_id": store_id})
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

    try:
        inventory_quantity = int(inventory_item.get("quantity", 0))
    except (ValueError, TypeError):
        inventory_quantity = 0

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
    request_id = await generate_request_id()
    request_data["request_id"] = request_id

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
    request_id = await generate_request_id()

    request_doc = {
        "request_id": request_id,
        "org_id": org_id,
        "store_id": store_id,
        "product_name": data["product_name"],
        "quantity": data["quantity"],
        "unit": data.get("unit", "pcs"),
        "category": data.get("category", "general"),
        "estimate_date": data.get("estimate_date", datetime.utcnow().strftime("%Y-%m-%d")),
        "requested_by": requested_by
    }

    await db.RequestedOrders.insert_one(request_doc)
    
    # import app.services.notification_service as notification_service
    
    # notification = {
    #     "sender": {
    #         "id": requested_by.get("id"),
    #         "name": requested_by.get("name")
    #     },
    #     "receiver": [
    #         {
    #             "id": user.get("id"),
    #             "name": user.get("name")
    #         }
    #         for user in await db.Users.find({"role": "admin"}).to_list()
    #     ],
    #     "type_of_notification": "order_request",
    #     "title": f"New Order Request: {data['product_name']}",
    #     "message": f"An order request has been raised for {data['quantity']} {data.get('unit', 'pcs')} of {data['product_name']}.",
    #     "status": 0,
    #     "time": datetime.utcnow().strftime("%H:%M:%S"),
    #     "date": datetime.utcnow().strftime("%Y-%m-%d")
    # }
    

    # notification_service.create_notifications_service(notification)

    return {"message": "Request raised successfully", "request_id": request_id}