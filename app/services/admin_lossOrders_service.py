from fastapi import HTTPException
from datetime import datetime
from bson import ObjectId
from app.db import db
from app.models.admin_model import LossOrder

loss_orders_collection = db.LossOrders
users_collection = db.Users
sales_orders_collection = db.SalesOrders  # For revenue calculation


# 🔹 Dashboard: All data is filtered by store_id from logged-in user
async def get_loss_data_by_user(user_id: str):
    user = await users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID not found for user")

    # ---------- Loss Orders (filtered by store_id) ----------
    cursor = loss_orders_collection.find({"store_id": store_id})
    loss_data = []
    total_items_lost = 0
    total_loss = 0

    async for doc in cursor:
        doc["_id"] = str(doc["_id"])

        try:
            quantity = float(doc.get("quantity_lost", 0))
        except (ValueError, TypeError):
            quantity = 0

        try:
            unit_price = float(doc.get("unit_price", 0))
        except (ValueError, TypeError):
            unit_price = 0

        loss_value = quantity * unit_price
        doc["loss_value"] = loss_value

        loss_data.append(doc)
        total_items_lost += quantity
        total_loss += loss_value

    # ---------- Revenue Calculation (filtered by store_id) ----------
    revenue_pipeline = [
    {"$match": {"store_id": store_id}},  # Only for this store
    {"$unwind": "$products"},  # Flatten products array
    {
        "$addFields": {
            "product_revenue": {
                "$multiply": [
                    {
                        "$add": [
                            {"$toDouble": "$products.unit_price"},
                            {
                                "$toDouble": {
                                    "$ifNull": ["$products.tax", 0] # Default tax to 0 if missing
                                }
                            }
                        ]
                    },
                    {"$toDouble": "$products.order_quantity"} 
                ]
            }
        }
    },
    {
        "$group": {
            "_id": None,
            "total_revenue": {"$sum": "$product_revenue"}
        }
    }
]


    revenue_result = await sales_orders_collection.aggregate(revenue_pipeline).to_list(length=1)
    total_revenue = round(revenue_result[0]["total_revenue"], 2) if revenue_result else 0

    # ---------- Top 5 Loss Products ----------
    top_loss_products = sorted(
        loss_data, key=lambda x: x.get("loss_value", 0), reverse=True
    )[:5]

    # ---------- Daily Loss Chart ----------
    daily_loss = {}
    for item in loss_data:
        created_date = item.get("date_reported")
        try:
            dt = datetime.strptime(created_date, "%Y-%m-%d")
            day = dt.strftime("%a")
        except:
            day = "Unknown"

        daily_loss[day] = daily_loss.get(day, 0) + item.get("loss_value", 0)

    chart_data = [{"day": day, "loss": loss} for day, loss in daily_loss.items()]

    # ---------- Final Response ----------
    return {
        "metrics": {
            "total_loss": round(total_loss, 2),
            "total_items_lost": int(total_items_lost),
            "total_revenue": total_revenue
        },
        "top_loss_products": top_loss_products,
        "chart_data": chart_data,
        "table_data": loss_data
    }


# 🔹 List of Loss Orders (filtered by store_id)
async def get_loss_orders_by_store(user_id: str):
    user = await users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID not found for user")

    cursor = db.LossOrders.find({"store_id": store_id})
    loss_orders = []

    async for order in cursor:
        order.pop("_id", None)

        quantity = order.get("quantity_lost", 0)
        price = order.get("unit_price", 0.0)

        try:
            loss = float(quantity) * float(price)
        except (ValueError, TypeError):
            loss = 0.0

        order["loss_amount"] = round(loss, 2)
        loss_orders.append(order)

    if not loss_orders:
        raise HTTPException(status_code=404, detail="No loss orders found for this store.")

    return loss_orders


# 🔹 View Loss Orders by Product (filtered by store_id)
async def get_loss_orders_by_product_id(product_id: str, user_id: str):
    user = await users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID not found for user")

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

        order["loss_amount"] = round(loss, 2)
        loss_orders.append(order)

    if not loss_orders:
        raise HTTPException(status_code=404, detail="No loss orders found for this product in your store.")

    return loss_orders
