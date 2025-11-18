from app.db import db  # Motor async MongoDB client
from bson import ObjectId

requested_orders_collection = db["RequestedOrders"]

# List of Requested orders (latest first)
async def get_all_requested_orders(store_id: str):
    orders = []
    cursor = requested_orders_collection.find(
        {"store_id": store_id}
    ).sort("_id", -1)  # 👈 reverse order, latest first
    
    async for order in cursor:
        order["_id"] = str(order["_id"])  # Convert ObjectId to string
        orders.append(order)
    return orders

# Delete Requested Order
async def delete_requested_order(order_id: str):
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(order_id):
            return {"success": False, "message": "Invalid order ID"}
        
        result = await requested_orders_collection.delete_one({
            "_id": ObjectId(order_id)
        })
        
        if result.deleted_count == 1:
            return {"success": True, "message": "Requested order deleted successfully"}
        else:
            return {"success": False, "message": "Requested order not found"}
    
    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}