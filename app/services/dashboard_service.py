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
    low_stock_items = await inventory_collection.count_documents({
        **store_filter,
        "quantity": {"$lt": 10, "$gt": 0}
    })

    # ---------- 3. Out of Stock Items ----------
    out_of_stock_items = await inventory_collection.count_documents({
        **store_filter,
        "quantity": {"$lte": 0}
    })

    # ---------- 5. Total Revenue ----------
    revenue_pipeline = [
        { "$match": store_filter },
        { "$unwind": "$products" },
        { "$match": { "products.store_id": store_id } },  # ✅ ensure revenue is only for products with same store_id
        {
            "$group": {
                "_id": None,
                "total_revenue": {
                    "$sum": {
                        "$multiply": [
                            { "$toDouble": "$products.unit_price" },
                            "$products.quantity"
                        ]
                    }
                }
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

    # ---------- 7. Finance Report ----------
    finance_pipeline = [
        { "$match": store_filter },
        { "$unwind": "$products" },
        { "$match": { "products.store_id": store_id } },  # ✅ filter by product store_id
        {
            "$addFields": {
                "total_price": {
                    "$multiply": [
                        { "$toDouble": "$products.unit_price" },
                        "$products.quantity"
                    ]
                }
            }
        },
        {
            "$group": {
                "_id": { "$month": { "$toDate": "$order_date" } },
                "total_sales": { "$sum": "$total_price" },
                "products_sold": { "$sum": "$products.quantity" },
                "total_orders": { "$sum": 1 }
            }
        },
        {
            "$addFields": {
                "average_order_value": {
                    "$cond": [
                        { "$eq": ["$total_orders", 0] },
                        0,
                        { "$divide": ["$total_sales", "$total_orders"] }
                    ]
                }
            }
        },
        { "$sort": { "_id": 1 } }
    ]
    finance_cursor = sales_orders_collection.aggregate(finance_pipeline)
    finance_data = [doc async for doc in finance_cursor]

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
        month_index = entry["_id"]
        if 1 <= month_index <= 12:
            finance_report["labels"].append(months[month_index - 1])
            finance_report["total_sales"].append(round(entry["total_sales"], 2))
            finance_report["total_orders"].append(entry["total_orders"])
            finance_report["products_sold"].append(entry["products_sold"])
            finance_report["average_order_value"].append(round(entry["average_order_value"], 2))

    # ---------- 8. Top Selling Products ----------
    top_selling_pipeline = [
        { "$match": store_filter },
        { "$unwind": "$products" },
        { "$match": { "products.store_id": store_id } },  # ✅ filter products by store_id
        {
            "$group": {
                "_id": "$products.product_name",
                "total_quantity": { "$sum": "$products.quantity" },
                "total_sales": {
                    "$sum": {
                        "$multiply": [
                            { "$toDouble": "$products.unit_price" },
                            "$products.quantity"
                        ]
                    }
                }
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
