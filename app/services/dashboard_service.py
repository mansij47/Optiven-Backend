from datetime import datetime
from pymongo import DESCENDING
from app.db import db

inventory_collection = db.Inventory
sales_orders_collection = db.SalesOrders
loss_products_collection = db.LossProduct

async def get_dashboard_data():
    # ---------- 1. Total Items ----------
    total_items = await inventory_collection.count_documents({})

    # ---------- 2. Low Stock Items ----------
    low_stock_items = await inventory_collection.count_documents({"quantity": {"$lt": 10, "$gt": 0}})

    # ---------- 3. Out of Stock Items ----------
    out_of_stock_items = await inventory_collection.count_documents({"quantity": {"$lte": 0}})

    # ---------- 4. Unique Visits (static for now) ----------
    unique_visits = 1034

    # ---------- 5. Inventory Status (Bar Chart) ----------
    inventory_cursor = inventory_collection.find({}, {"_id": 0, "product_name": 1, "quantity": 1})
    inventory_status = await inventory_cursor.to_list(length=None)

    # ---------- 6. Finance Report (Bar Chart - Sales by Month) ----------
    pipeline = [
        {
            "$group": {
                "_id": { "$month": "$created_at" },
                "total_sales": { "$sum": "$total_price" }
            }
        },
        { "$sort": { "_id": 1 } }
    ]
    monthly_sales_cursor = sales_orders_collection.aggregate(pipeline)
    monthly_sales = [doc async for doc in monthly_sales_cursor]

    months = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]

    month_labels = []
    finance_report_data = []

    for m in monthly_sales:
        month_index = m.get("_id")
        if month_index is not None and 1 <= month_index <= 12:
            month_labels.append(months[month_index - 1])
            finance_report_data.append(m["total_sales"])

    # ---------- 7. Top Selling Products (Table) ----------
    top_selling_pipeline = [
        { "$unwind": "$items" },
        { "$group": {
            "_id": "$items.product_name",
            "total_quantity": { "$sum": "$items.quantity" },
            "total_sales": { "$sum": "$items.total_price" }
        }},
        { "$sort": { "total_quantity": -1 } },
        { "$limit": 5 }
    ]
    top_selling_cursor = sales_orders_collection.aggregate(top_selling_pipeline)
    top_selling_products = [doc async for doc in top_selling_cursor]

    # ---------- 8. Loss Products Table ----------
    loss_cursor = loss_products_collection.find({}, {"_id": 0})
    loss_products = await loss_cursor.to_list(length=None)

    return {
        "total_items": total_items,
        "low_stock_items": low_stock_items,
        "out_of_stock_items": out_of_stock_items,
        "unique_visits": unique_visits,
        "inventory_status": inventory_status,
        "finance_report": {
            "labels": month_labels,
            "data": finance_report_data
        },
        "top_selling_products": top_selling_products,
        "loss_products": loss_products
    }
    