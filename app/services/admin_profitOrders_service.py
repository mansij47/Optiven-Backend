from fastapi import HTTPException
from datetime import datetime
from bson import ObjectId
from app.db import db
from app.models.admin_model import ProfitOrder

profit_orders_collection = db.ProfitOrders
users_collection = db.Users
sales_orders_collection = db.SalesOrders  # For profit calculation


# 🔹 NEW: Sync Profit Orders from SalesOrders to ProfitOrders Collection
async def sync_profit_orders_from_sales(store_id: str):
    """
    Syncs sold SalesOrders (order_status="1") to ProfitOrders collection.
    This ensures ProfitOrders collection has all profit data for CRUD operations.
    """
    # Fetch all sold orders from SalesOrders
    cursor = db.SalesOrders.find({
        "store_id": store_id,
        "order_status": "1"  # Only sold orders
    })
    
    synced_count = 0
    updated_count = 0
    
    async for order in cursor:
        order_id = order.get("order_id")
        order_date = order.get("order_date")
        sold_at = order.get("sold_at")
        sales_order_mongo_id = str(order.get("_id"))
        
        # Process each product in the order
        for product in order.get("products", []):
            product_id = product.get("product_id")
            product_name = product.get("product_name")
            category = product.get("category")
            quantity_sold = int(product.get("order_quantity", 0))
            item_ids = product.get("item_ids", [])
            unit = product.get("unit", "")
            
            # Calculate unit_price and selling_price from items
            if item_ids:
                total_unit_price = 0.0
                total_selling_price = 0.0
                valid_items = 0
                
                for item_id in item_ids:
                    item = await db.ProductItems.find_one({
                        "item_id": item_id,
                        "product_id": product_id,
                        "store_id": store_id
                    })
                    
                    if item:
                        try:
                            item_unit_price = float(item.get("unit_price", 0))
                            item_selling_price = float(item.get("selling_price", 0))
                            
                            # If selling_price doesn't exist, calculate it
                            if item_selling_price == 0 and item_unit_price > 0:
                                item_selling_price = item_unit_price + 50
                            
                            total_unit_price += item_unit_price
                            total_selling_price += item_selling_price
                            valid_items += 1
                        except (ValueError, TypeError):
                            continue
                
                # Calculate average prices
                if valid_items > 0:
                    avg_unit_price = total_unit_price / valid_items
                    avg_selling_price = total_selling_price / valid_items
                else:
                    avg_unit_price = 0.0
                    avg_selling_price = 0.0
            else:
                # Fallback to product-level prices if no items
                avg_unit_price = float(product.get("unit_price", 0))
                avg_selling_price = avg_unit_price + 50 if avg_unit_price > 0 else 0.0
            
            # Calculate profit
            profit_per_item = avg_selling_price - avg_unit_price
            total_profit = profit_per_item * quantity_sold
            
            # Create profit order document
            profit_order_data = {
                "order_id": order_id,
                "sales_order_id": sales_order_mongo_id,  # Reference to SalesOrders
                "product_id": product_id,
                "product_name": product_name,
                "category": category,
                "date_recorded": sold_at.strftime("%Y-%m-%d") if sold_at else order_date,
                "quantity_sold": quantity_sold,
                "unit": unit,
                "unit_price": round(avg_unit_price, 2),
                "selling_price": round(avg_selling_price, 2),
                "profit_amount": round(total_profit, 2),
                "store_id": store_id,
                "updated_at": datetime.utcnow()
            }
            
            # Check if this profit order already exists (by order_id + product_id)
            existing = await db.ProfitOrders.find_one({
                "order_id": order_id,
                "product_id": product_id,
                "store_id": store_id
            })
            
            if existing:
                # Update existing record
                await db.ProfitOrders.update_one(
                    {"_id": existing["_id"]},
                    {"$set": profit_order_data}
                )
                updated_count += 1
            else:
                # Insert new record
                profit_order_data["created_at"] = datetime.utcnow()
                await db.ProfitOrders.insert_one(profit_order_data)
                synced_count += 1
    
    return {
        "message": "Profit orders synced successfully",
        "synced_count": synced_count,
        "updated_count": updated_count,
        "total_processed": synced_count + updated_count
    }


# 🔹 Dashboard: Get Profit Data by User (filtered by store_id)
async def get_profit_data_by_user(user_id: str):
    user = await users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID not found for user")

    # ---------- Calculate Profit from Sold SalesOrders ----------
    cursor = db.SalesOrders.find({
        "store_id": store_id,
        "order_status": "1"  # Only sold orders
    })
    
    profit_data = []
    total_items_sold = 0
    total_profit = 0
    
    async for order in cursor:
        sold_at = order.get("sold_at")
        order_date = order.get("order_date")
        
        # Process each product in the order
        for product in order.get("products", []):
            product_id = product.get("product_id")
            product_name = product.get("product_name")
            category = product.get("category")
            quantity_sold = int(product.get("order_quantity", 0))
            item_ids = product.get("item_ids", [])
            
            # Calculate unit_price and selling_price from items
            if item_ids:
                total_unit_price = 0.0
                total_selling_price = 0.0
                valid_items = 0
                
                for item_id in item_ids:
                    item = await db.ProductItems.find_one({
                        "item_id": item_id,
                        "product_id": product_id,
                        "store_id": store_id
                    })
                    
                    if item:
                        try:
                            item_unit_price = float(item.get("unit_price", 0))
                            item_selling_price = float(item.get("selling_price", 0))
                            
                            # If selling_price doesn't exist, calculate it
                            if item_selling_price == 0 and item_unit_price > 0:
                                item_selling_price = item_unit_price + 50
                            
                            total_unit_price += item_unit_price
                            total_selling_price += item_selling_price
                            valid_items += 1
                        except (ValueError, TypeError):
                            continue
                
                # Calculate average prices
                if valid_items > 0:
                    avg_unit_price = total_unit_price / valid_items
                    avg_selling_price = total_selling_price / valid_items
                else:
                    avg_unit_price = 0.0
                    avg_selling_price = 0.0
            else:
                # Fallback to product-level prices if no items
                avg_unit_price = float(product.get("unit_price", 0))
                avg_selling_price = avg_unit_price + 50 if avg_unit_price > 0 else 0.0
            
            # Calculate profit
            profit_per_item = avg_selling_price - avg_unit_price
            profit_value = profit_per_item * quantity_sold
            
            doc = {
                "product_id": product_id,
                "product_name": product_name,
                "category": category,
                "date_recorded": sold_at.strftime("%Y-%m-%d") if sold_at else order_date,
                "quantity_sold": quantity_sold,
                "unit_price": round(avg_unit_price, 2),
                "selling_price": round(avg_selling_price, 2),
                "profit_value": round(profit_value, 2)
            }
            
            profit_data.append(doc)
            total_items_sold += quantity_sold
            total_profit += profit_value

    # ---------- Revenue Calculation (from all orders in store) ----------
    revenue_pipeline = [
        {"$match": {"store_id": store_id, "order_status": "1"}},  # Only sold orders
        {"$unwind": "$products"},  # Flatten products array
        {
            "$addFields": {
                "product_revenue": {
                    "$multiply": [
                        {
                            "$add": [
                                {"$toDouble": "$products.unit_price"},
                                {
                                    "$multiply": [
                                        {"$toDouble": "$products.unit_price"},
                                        {"$divide": [{"$toDouble": {"$ifNull": ["$products.tax", 0]}}, 100]}
                                    ]
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

    # ---------- Top 5 Profit Products ----------
    top_profit_products = sorted(
        profit_data, key=lambda x: x.get("profit_value", 0), reverse=True
    )[:5]

    # ---------- Daily Profit Chart ----------
    daily_profit = {}
    for item in profit_data:
        recorded_date = item.get("date_recorded")
        try:
            dt = datetime.strptime(recorded_date, "%Y-%m-%d")
            day = dt.strftime("%a")
        except:
            day = "Unknown"

        daily_profit[day] = daily_profit.get(day, 0) + item.get("profit_value", 0)

    chart_data = [{"day": day, "profit": profit} for day, profit in daily_profit.items()]

    # ---------- Final Response ----------
    return {
        "metrics": {
            "total_profit": round(total_profit, 2),
            "total_items_sold": int(total_items_sold),
            "total_revenue": total_revenue
        },
        "top_profit_products": top_profit_products,
        "chart_data": chart_data,
        "table_data": profit_data
    }


# 🔹 List of Profit Orders (filtered by store_id)
async def get_profit_orders_by_store(store_id: str):
    """
    Get profit orders from ProfitOrders collection.
    Auto-syncs from SalesOrders if ProfitOrders is empty or outdated.
    """
    # First, check if ProfitOrders collection has data
    profit_count = await db.ProfitOrders.count_documents({"store_id": store_id})
    
    # If no profit orders exist, sync from SalesOrders
    if profit_count == 0:
        await sync_profit_orders_from_sales(store_id)
    
    # Fetch from ProfitOrders collection
    cursor = db.ProfitOrders.find({
        "store_id": store_id
    }).sort("_id", -1)  # latest first
    
    profit_orders = []
    
    async for order in cursor:
        order["_id"] = str(order["_id"])
        profit_orders.append(order)
    
    return profit_orders


# 🔹 Get Single Profit Order by ID
async def get_profit_order_by_id(order_id: str, store_id: str):
    try:
        order = await db.ProfitOrders.find_one({
            "_id": ObjectId(order_id),
            "store_id": store_id
        })

        if not order:
            raise HTTPException(status_code=404, detail="Profit order not found")

        order["_id"] = str(order["_id"])

        # Calculate profit
        quantity = order.get("quantity_sold", 0)
        unit_price = order.get("unit_price", 0.0)
        selling_price = order.get("selling_price", 0.0)

        try:
            profit = (float(selling_price) - float(unit_price)) * float(quantity)
        except (ValueError, TypeError):
            profit = 0.0

        order["profit_amount"] = round(profit, 2)

        return order

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching profit order: {str(e)}")


# 🔹 View Profit Orders by Product (filtered by store_id)
async def get_profit_orders_by_product_id(product_id: str, store_id: str):
    # Ensure data is synced
    profit_count = await db.ProfitOrders.count_documents({
        "product_id": product_id,
        "store_id": store_id
    })
    
    if profit_count == 0:
        await sync_profit_orders_from_sales(store_id)
    
    cursor = db.ProfitOrders.find({
        "product_id": product_id,
        "store_id": store_id
    })

    profit_orders = []

    async for order in cursor:
        order["_id"] = str(order["_id"])
        # profit_amount should already be calculated and stored
        profit_orders.append(order)

    # Return empty list instead of 404 if no data
    return profit_orders


# 🔹 Create Profit Order
async def create_profit_order(profit_order_data: dict, store_id: str, org_id: str):
    # Calculate profit amount
    quantity = float(profit_order_data.get("quantity_sold", 0))
    unit_price = float(profit_order_data.get("unit_price", 0))
    selling_price = float(profit_order_data.get("selling_price", 0))

    profit_amount = (selling_price - unit_price) * quantity

    # Prepare data for insertion
    profit_order = {
        **profit_order_data,
        "store_id": store_id,
        "org_id": org_id,
        "profit_amount": round(profit_amount, 2),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    result = await db.ProfitOrders.insert_one(profit_order)

    if result.inserted_id:
        profit_order["_id"] = str(result.inserted_id)
        return {"message": "Profit order created successfully", "data": profit_order}
    else:
        raise HTTPException(status_code=500, detail="Failed to create profit order")


# 🔹 Update Profit Order
async def update_profit_order(order_id: str, update_data: dict, store_id: str):
    try:
        # Check if order exists
        existing_order = await db.ProfitOrders.find_one({
            "_id": ObjectId(order_id),
            "store_id": store_id
        })

        if not existing_order:
            raise HTTPException(status_code=404, detail="Profit order not found")

        # Recalculate profit if relevant fields are updated
        quantity = float(update_data.get("quantity_sold", existing_order.get("quantity_sold", 0)))
        unit_price = float(update_data.get("unit_price", existing_order.get("unit_price", 0)))
        selling_price = float(update_data.get("selling_price", existing_order.get("selling_price", 0)))

        profit_amount = (selling_price - unit_price) * quantity

        # Add updated fields
        update_data["profit_amount"] = round(profit_amount, 2)
        update_data["updated_at"] = datetime.utcnow()

        # Update the order
        result = await db.ProfitOrders.update_one(
            {"_id": ObjectId(order_id), "store_id": store_id},
            {"$set": update_data}
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=400, detail="No changes made to profit order")

        return {"message": "Profit order updated successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating profit order: {str(e)}")


# 🔹 Delete Profit Order
async def delete_profit_order(order_id: str, store_id: str):
    try:
        result = await db.ProfitOrders.delete_one({
            "_id": ObjectId(order_id),
            "store_id": store_id
        })

        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Profit order not found")

        return {"message": "Profit order deleted successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting profit order: {str(e)}")


# 🔹 Export Profit Orders as CSV
async def export_profit_orders_csv(store_id: str, org_id: str):
    from fastapi.responses import StreamingResponse
    import io
    import csv

    cursor = db.ProfitOrders.find({"store_id": store_id, "org_id": org_id})
    profit_orders = []

    async for order in cursor:
        quantity = order.get("quantity_sold", 0)
        unit_price = order.get("unit_price", 0.0)
        selling_price = order.get("selling_price", 0.0)

        try:
            profit = (float(selling_price) - float(unit_price)) * float(quantity)
        except (ValueError, TypeError):
            profit = 0.0

        profit_orders.append({
            "Product Name": order.get("product_name", ""),
            "Category": order.get("category", ""),
            "Date Recorded": order.get("date_recorded", ""),
            "Quantity Sold": quantity,
            "Unit": order.get("unit", ""),
            "Unit Price": unit_price,
            "Selling Price": selling_price,
            "Profit Amount": round(profit, 2),
            "Order ID": order.get("order_id", ""),
        })

    if not profit_orders:
        raise HTTPException(status_code=404, detail="No profit orders found for export")

    # Create CSV
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=profit_orders[0].keys())
    writer.writeheader()
    writer.writerows(profit_orders)

    output.seek(0)

    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=profit_orders_{store_id}.csv"}
    )
