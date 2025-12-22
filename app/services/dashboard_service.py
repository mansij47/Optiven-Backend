from datetime import datetime
from pymongo import DESCENDING
from app.db import db

inventory_collection = db.Inventory
sales_orders_collection = db.SalesOrders
# loss_products_collection = db.LossProduct

async def get_dashboard_data(store_id: str):
    # Add store_id filter
    store_filter = {"store_id": store_id}

    # ---------- 1. Total Items ----------
    total_items = await inventory_collection.count_documents(store_filter)

    # ---------- 2. Low Stock Items ----------
    # Count products with "Low Stock" status (includes legacy "running-out" for backward compatibility)
    low_stock_items = await inventory_collection.count_documents({
        **store_filter,
        "status": {"$in": ["Low Stock", "running-out"]}
    })

    # ---------- 3. Out of Stock Items ----------
    # Count products with "Stock-out" status
    out_of_stock_items = await inventory_collection.count_documents({
        **store_filter,
        "status": "Stock-out"
    })

    # ---------- 5. Total Revenue ----------
    # Sum total_order_price from sold orders only (same logic as Sales Dashboard)
    revenue_pipeline = [
        {"$match": {"store_id": store_id, "order_status": "1"}},  # Filter by store and ONLY sold orders
        {
            "$group": {
                "_id": None,
                "total_revenue": {"$sum": {"$toDouble": "$total_order_price"}}
            }
        }
    ]

    revenue_cursor = sales_orders_collection.aggregate(revenue_pipeline)
    revenue_result = [doc async for doc in revenue_cursor]
    total_revenue = round(revenue_result[0]["total_revenue"], 2) if revenue_result else 0.0

    # ---------- 6. Inventory Status ----------
    inventory_cursor = inventory_collection.find(
        store_filter,
        {"_id": 0, "product_name": 1, "quantity": 1}
    )
    inventory_status = await inventory_cursor.to_list(length=None)

    # ---------- 7. Finance Report (Updated) ----------
    # Group by month and store_id, sum total sales, products sold (quantity), and total orders per month
    finance_pipeline = [
        { "$match": {"store_id": store_id, "order_status": "1"} },  # Only sold orders
        { "$unwind": "$products" },
        {
            "$addFields": {
                "order_month": { "$month": { "$toDate": "$order_date" } },
                "product_quantity": { "$toInt": "$products.order_quantity" }
            }
        },
        {
            "$group": {
                "_id": {
                    "month": "$order_month",
                    "store_id": "$store_id",
                    "order_id": "$order_id"  # Group by order_id to get unique orders
                },
                "products_sold": { "$sum": "$product_quantity" },
                "order_total": { "$first": { "$toDouble": "$total_order_price" } }  # Get order's total price once
            }
        },
        {
            "$group": {
                "_id": {
                    "month": "$_id.month",
                    "store_id": "$_id.store_id"
                },
                "total_sales": { "$sum": "$order_total" },  # Sum all order totals
                "products_sold": { "$sum": "$products_sold" },
                "total_orders": { "$sum": 1 }  # Count unique orders
            }
        },
        {
            "$addFields": {
                "average_order_value": {
                    "$cond": [
                        { "$eq": [ "$total_orders", 0 ] },
                        0,
                        { "$divide": [ "$total_sales", "$total_orders" ] }
                    ]
                }
            }
        },
        { "$sort": { "_id.month": 1 } }
    ]
    finance_cursor = sales_orders_collection.aggregate(finance_pipeline)
    finance_data = [doc async for doc in finance_cursor if doc["_id"]["store_id"] == store_id]

    months = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]

    finance_report = {
        "labels": [],
        "total_sales": [],
        "total_orders": [],
        "products_sold": [],
        "average_order_value": []
    }

    for entry in finance_data:
        month_index = entry["_id"]["month"]
        if 1 <= month_index <= 12:
            finance_report["labels"].append(months[month_index - 1])
            finance_report["total_sales"].append(round(entry["total_sales"], 2))
            finance_report["total_orders"].append(entry["total_orders"])
            finance_report["products_sold"].append(entry["products_sold"])
            finance_report["average_order_value"].append(round(entry["average_order_value"], 2))

    # ---------- 8. Top Selling Products ----------
    top_selling_pipeline = [
        { "$match": {"store_id": store_id, "order_status": "1"} },  # Only sold orders
        { "$unwind": "$products" },
        {
            "$group": {
                "_id": "$products.product_name",
                "total_quantity": { "$sum": "$products.order_quantity" },
                "total_sales": {
                    "$sum": {
                        "$multiply": [
                            { "$toDouble": "$products.unit_price" },
                            "$products.order_quantity"
                        ]
                    }
                },
                "total_order_price": { "$sum": { "$toDouble": "$total_order_price" } }  # ✅ Added here
            }
        },
        { "$sort": { "total_quantity": -1 } },
        { "$limit": 5 }
    ]
    top_selling_cursor = sales_orders_collection.aggregate(top_selling_pipeline)
    top_selling_products = [doc async for doc in top_selling_cursor]

    return {
        "total_items": total_items,
        "low_stock_items": low_stock_items,
        "out_of_stock_items": out_of_stock_items,
        "revenue": total_revenue,
        "inventory_status": inventory_status,
        "finance_report": finance_report,
        "top_selling_products": top_selling_products,
    }
