from app.db import db  # Motor async MongoDB client
from bson import ObjectId

requested_orders_collection = db["RequestedOrders"]

#List of Requested order 
async def get_all_requested_orders(store_id: str):
    orders = []
    cursor = requested_orders_collection.find({"store_id": store_id})
    async for order in cursor:
        order["_id"] = str(order["_id"])  # Convert ObjectId to string
        orders.append(order)
    return orders
