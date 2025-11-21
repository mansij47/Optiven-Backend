from typing import Optional
from app.db import db
from app.models.sales_model import ProductDetails, SalesOrderDetails, SalesProductItem
from app.services.sales_add_raise_services import fetch_inventory_details
from fastapi import HTTPException
from app.utils.sales_utils import build_product_detail, parse_return_status, parse_status_string
from bson.son import SON
from datetime import datetime
# async def get_all_sales_orders(store_id: str):
#     orders = await db.SalesOrders.find(
#         {"order_status": "0", "store_id": store_id},
#         {"_id": 0}
#     ).to_list(length=None)

#     for order in orders:
#         updated_products = []

#         for product in order.get("products", []):
#             product_id = product.get("product_id")
#             ordered_quantity = int(product.get("order_quantity", 0))
#             inventory_item = await db.Inventory.find_one({
#                 "store_id": store_id,
#                 "product_id": product_id
#             })

#             try:
#                 inventory_quantity = int(inventory_item.get("quantity", 0)) if inventory_item else 0
#             except (ValueError, TypeError):
#                 inventory_quantity = 0

#             # Compare and determine product_status
#             product_status = "Stock-out" if inventory_quantity < ordered_quantity else "Stock-in"

#             # Add product_status to product
#             product["product_status"] = product_status
#             updated_products.append(product)

#         # Update products list
#         order["products"] = updated_products

#         # Convert status field
#         order["status"] = parse_status_string(order.get("status", "0"))

#         # Remove order_status field if present
#         if "order_status" in order:
#             del order["order_status"]

#     return orders

# async def get_all_sold_orders(store_id: str):
#     orders = await db.SalesOrders.find(
#         {"store_id": store_id, "order_status": "1"},
#         {"_id": 0}
#     ).to_list(length=None)

#     for order in orders:
#         # Convert order_status to status text
#         order["status"] = parse_status_string(order["order_status"])
#         # Remove raw order_status field from final output
#         order.pop("order_status", None)

#     return orders


async def get_all_sales_orders(store_id: str):
    cursor = db.SalesOrders.find(
        {"order_status": "0", "store_id": store_id},
        {"_id": 0}
    ).sort([("_id", -1)])   # ✅ latest first

    orders = await cursor.to_list(length=None)

    for order in orders:
        updated_products = []
        for product in order.get("products", []):
            product_id = product.get("product_id")
            ordered_quantity = int(product.get("order_quantity", 0))
            item_ids = product.get("item_ids", [])

            # ✅ Count available items from ProductItems collection (this is the source of truth)
            available_items_count = await db.ProductItems.count_documents({
                "product_id": product_id,
                "store_id": store_id,
                "status": "available"
            })

            # Determine product_status based on available items
            product_status = "Stock-out" if available_items_count < ordered_quantity else "Stock-in"
            product["product_status"] = product_status
            
            # ✅ ITEM-BASED APPROACH: Add item details for tracking (only basic info for list view)
            if item_ids:
                product["item_count"] = len(item_ids)
                product["has_item_details"] = True
            else:
                product["item_count"] = 0
                product["has_item_details"] = False
            
            updated_products.append(product)

        # Replace products list
        order["products"] = updated_products

        # Convert status field
        order["status"] = parse_status_string(order.get("status", "0"))

        # Clean up order_status
        order.pop("order_status", None)

    return orders


async def get_all_sold_orders(store_id: str):
    cursor = db.SalesOrders.find(
        {"store_id": store_id, "order_status": "1"},
        {"_id": 0}
    ).sort([("_id", -1)])   # ✅ latest first

    orders = await cursor.to_list(length=None)

    for order in orders:
        # ✅ ITEM-BASED APPROACH: Add item count for each product
        updated_products = []
        for product in order.get("products", []):
            item_ids = product.get("item_ids", [])
            
            # Add item tracking metadata
            if item_ids:
                product["item_count"] = len(item_ids)
                product["has_item_details"] = True
            else:
                product["item_count"] = 0
                product["has_item_details"] = False
            
            updated_products.append(product)
        
        order["products"] = updated_products
        
        # Convert order_status to status text
        order["status"] = parse_status_string(order["order_status"])
        # Remove raw order_status field from final output
        order.pop("order_status", None)

    return orders


async def fetch_order_and_validate(order_id: str, store_id: str):
    order = await db.SalesOrders.find_one({
        "order_id": order_id,
        "store_id": store_id,
        "order_status": "0"   # Make sure using correct field
    },{"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found or already sold.")
    return order

async def update_inventory_for_order(order, store_id: str):
    sold_items_map = {}  # Track which items were sold for each product
    
    for product in order.get("products", []):
        product_id = product.get("product_id")
        order_quantity = int(product.get("order_quantity", 0))  # Correct field

        # ✅ Find available items for this product (hierarchical structure)
        available_items = await db.ProductItems.find(
            {
                "product_id": product_id,
                "store_id": store_id,
                "status": "available"
            }
        ).limit(order_quantity).to_list(order_quantity)

        if len(available_items) < order_quantity:
            # Not enough items available
            continue

        # Store the item IDs that were sold for this product
        sold_item_ids = []
        
        # ✅ Mark each item as sold
        for item in available_items:
            item_id = item["item_id"]
            sold_item_ids.append(item_id)
            
            # ✅ Preserve previous sales history by using $push to add to sales_history array
            # If item was previously sold and returned, we keep that history
            update_data = {
                "$set": {
                    "status": "sold",
                    "updated_at": datetime.utcnow(),
                    "sold_order_id": order.get("order_id"),
                    "sold_at": datetime.utcnow()
                }
            }
            
            # If item has previous sale history (was returned), archive it
            if item.get("sold_order_id") and item.get("sold_order_id") != order.get("order_id"):
                # Initialize sales_history array if it doesn't exist, then add previous sale
                update_data["$push"] = {
                    "sales_history": {
                        "previous_order_id": item.get("sold_order_id"),
                        "previous_sold_at": item.get("sold_at"),
                        "returned_at": item.get("returned_at"),
                        "return_reason": item.get("return_reason"),
                        "archived_at": datetime.utcnow()
                    }
                }
            
            await db.ProductItems.update_one(
                {"item_id": item_id},
                update_data
            )

        # Store the sold items for this product
        sold_items_map[product_id] = sold_item_ids

        # ✅ Update product quantity (count remaining available items)
        remaining_items = await db.ProductItems.count_documents({
            "product_id": product_id,
            "store_id": store_id,
            "status": "available"
        })

        await db.Inventory.update_one(
            {"product_id": product_id, "store_id": store_id},
            {
                "$set": {
                    "quantity": remaining_items,
                    "updated_at": datetime.utcnow()
                }
            }
        )
    
    return sold_items_map

async def mark_order_status_as_sold(order_id: str, store_id: str):
    result = await db.SalesOrders.update_one(
        {
            "order_id": order_id,
            "store_id": store_id,
            "order_status": "0"
        },
        {
            "$set": {"order_status": "1"}
        }
    )
    return result.modified_count

async def mark_order_as_sold(order_id: str, store_id: str):
    order = await fetch_order_and_validate(order_id, store_id)
    sold_items_map = await update_inventory_for_order(order, store_id)
    
    # Update the order products with item_ids information
    updated_products = []
    for product in order.get("products", []):
        product_id = product.get("product_id")
        product_copy = product.copy()
        
        # Add item_ids array (handles both single and multiple items)
        if product_id in sold_items_map:
            item_ids = sold_items_map[product_id]
            if len(item_ids) > 0:
                product_copy["item_ids"] = item_ids  # Always store as array
        
        updated_products.append(product_copy)
    
    # Update the order with item information
    await db.SalesOrders.update_one(
        {
            "order_id": order_id,
            "store_id": store_id,
            "order_status": "0"
        },
        {
            "$set": {
                "order_status": "1",
                "products": updated_products,
                "sold_at": datetime.utcnow()
            }
        }
    )
    
    return 1  # Return success count


async def delete_order_by_id(order_id: str, store_id: str) -> int:
    result = await db.SalesOrders.delete_one({
        "order_id": order_id,
        "store_id": store_id
    })
    return result.deleted_count


# 🔹 Helper to find updated quantity
def get_new_quantity_for_product(product_id: str, updated_products: list, default_quantity: int) -> int:
    for p in updated_products:
        if p["product_id"] == product_id:
            return p["quantity"]
    return default_quantity

# 🔹 Helper to rebuild products list and compute subtotal
async def rebuild_products_list(original_products: list, updated_products_input: list, store_id: str):
    updated_products = []
    subtotal = 0.0

    for prod in original_products:
        product_id = prod.get("product_id")
        default_quantity = prod.get("order_quantity", 0)
        new_quantity = get_new_quantity_for_product(product_id, updated_products_input, default_quantity)

        inventory_data = await fetch_inventory_details(product_id, store_id)

        product_detail, total_with_tax = build_product_detail(
            inventory_item=inventory_data["inventory_item"],
            product_id=product_id,
            unit_price=inventory_data["unit_price"],
            product_tax=inventory_data["product_tax"],
            order_quantity=new_quantity,
            inventory_quantity=inventory_data["inventory_quantity"]
        )

        subtotal += total_with_tax
        updated_products.append(product_detail)

    return updated_products, subtotal

# 🔹 Helper to prepare the final update dict
def prepare_updated_order_data(updated_data: dict, updated_products: list, subtotal: float, order: dict, store_id: str, order_id: str):
    updated_data["products"] = updated_products
    updated_data["total_order_price"] = round(subtotal, 2)
    updated_data["order_status"] = order.get("order_status", "0")
    updated_data["store_id"] = store_id
    updated_data["order_id"] = order_id
    updated_data["customer_id"] = order.get("customer_id")
    return updated_data

# 🔹 Main function
async def update_sales_order(order_id: str, store_id: str, updated_data: dict):
    order_id = order_id.strip()  # ✅ strip tabs/newlines/spaces

    order = await db.SalesOrders.find_one({"order_id": order_id, "store_id": store_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found or does not belong to your store.")

    original_products = order.get("products", [])
    updated_products, subtotal = await rebuild_products_list(original_products, updated_data.get("products", []), store_id)

    final_update_data = prepare_updated_order_data(updated_data, updated_products, subtotal, order, store_id, order_id)

    result = await db.SalesOrders.update_one(
        {"order_id": order_id, "store_id": store_id},
        {"$set": final_update_data}
    )

    return result.modified_count

async def get_all_products(store_id: str):
    try:
        products_cursor = db.Inventory.find({"store_id": store_id}, {"_id": 0})

        products = []
        async for product in products_cursor:
            product_id = product.get("product_id")
            
            # ✅ Count available items from ProductItems collection
            available_items_count = await db.ProductItems.count_documents({
                "product_id": product_id,
                "store_id": store_id,
                "status": "available"
            })
            
            # ✅ ITEM-BASED APPROACH: Get sample item info (vendor, warranty, etc.)
            sample_item = await db.ProductItems.find_one({
                "product_id": product_id,
                "store_id": store_id,
                "status": "available"
            }, {"_id": 0})
            
            # Update quantity to reflect actual available items
            product["quantity"] = available_items_count
            product["status"] = "Stock-in" if available_items_count > 0 else "Stock-out"
            
            # ✅ Add item-level metadata from sample item
            if sample_item:
                product["vendor_name"] = sample_item.get("vendor_name", "Unknown")
                product["vendor_id"] = sample_item.get("vendor_id")
                product["has_warranty"] = sample_item.get("has_warranty", False)
                product["warranty_tenure"] = sample_item.get("warranty_tenure", 0)
                product["warranty_unit"] = sample_item.get("warranty_unit", "months")
                product["is_consumer_returnable"] = sample_item.get("is_consumer_returnable", False)
                product["is_seller_returnable"] = sample_item.get("is_seller_returnable", False)
                product["average_price"] = sample_item.get("unit_price", product.get("unit_price", 0))
            
            products.append(product)

        return products
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving products: {str(e)}")
    
async def get_all_returns(store_id: str):
    # Filter by store_id and sent_to_procurement = 0, and exclude _id
    cursor = db.ReturnOrders.find({
        "store_id": store_id,
        "sent_to_procurement": 0
    }, {"_id": 0}) 

    result = []

    async for item in cursor:
        # Instead of building a custom dictionary, append full item
        result.append(item)

    return result

async def get_return_by_id(return_id: str, store_id: str):
    order = await db.ReturnOrders.find_one(
        {"return_id": return_id, "store_id": store_id},
        {"_id": 0}  # Exclude internal MongoDB _id field
    )
        
    if not order:
        raise HTTPException(status_code=404, detail="Return order not found in this store")

    return order

async def delete_return(return_id: str, store_id: str):
    result = await db.ReturnOrders.delete_one({
        "return_id": return_id,
        "store_id": store_id
    })

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Return order not found or not in your store")

    return {"message": f"Return order {return_id} deleted successfully"}


async def mark_return_sent_to_procurement(return_id: str, store_id: str):
    result = await db.ReturnOrders.update_one(
        {"return_id": return_id, "store_id": store_id},
        {"$set": {"sent_to_procurement": 1}}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Return order not found for this store")

    return {"message": f"Return order {return_id} marked as sent to procurement"}

async def get_all_procurement_returns(store_id: str, status_filter: str = "all"):
    query = {"sent_to_procurement": 1, "store_id": store_id}
    
    # Add status filter if not "all"
    if status_filter == "pending":
        # Match documents with status="pending" OR status field doesn't exist (old records)
        query["$or"] = [
            {"status": "pending"},
            {"status": {"$exists": False}}
        ]
    elif status_filter == "completed":
        query["status"] = "completed"
    
    cursor = db.ReturnOrders.find(query, {"_id": 0}).sort([("_id", -1)])
    result = []
    async for r in cursor:
        result.append(r)  # Append the entire document as it is
    return result

async def get_procurement_return_by_id(return_id: str , store_id: str):
    return await db.ReturnOrders.find_one(
    {"return_id": return_id, "store_id": store_id},
    {"_id": 0}
)


async def get_product_details_service(store_id: str, product_id: Optional[str] = None, product_name: Optional[str] = None) -> ProductDetails:
    query = {"store_id": store_id}

    if product_id:
        query["product_id"] = product_id
    elif product_name:
        query["product_name"] = product_name

    product = await db.Inventory.find_one(query, {"_id": 0})

    if not product:
        raise HTTPException(status_code=404, detail="Product not found for this store")

    # ✅ Get available items count from ProductItems
    available_items_count = await db.ProductItems.count_documents({
        "product_id": product.get("product_id"),
        "store_id": store_id,
        "status": "available"
    })

    # ✅ Calculate average price from ProductItems
    items_cursor = db.ProductItems.find({
        "product_id": product.get("product_id"),
        "store_id": store_id,
        "status": "available"
    }, {"unit_price": 1, "_id": 0})
    
    items = await items_cursor.to_list(length=None)
    
    # Calculate average price - handle string values and zeros
    average_price = 0.0
    if items:
        total_price = 0.0
        valid_count = 0
        
        for item in items:
            try:
                price_value = item.get("unit_price", 0)
                # Convert string to float if needed
                if isinstance(price_value, str):
                    price_value = float(price_value) if price_value and price_value != "0" else 0.0
                else:
                    price_value = float(price_value)
                
                if price_value > 0:
                    total_price += price_value
                    valid_count += 1
            except (ValueError, TypeError):
                continue
        
        if valid_count > 0:
            average_price = round(total_price / valid_count, 2)
    
    # If still 0, try to get from Inventory table
    if average_price == 0:
        try:
            inv_price = product.get("unit_price", 0)
            if isinstance(inv_price, str):
                average_price = float(inv_price) if inv_price and inv_price != "0" else 0.0
            else:
                average_price = float(inv_price)
        except (ValueError, TypeError):
            average_price = 0.0

    # ✅ Ensure consumer_return_conditions is always a list
    consumer_conditions = product.get("consumer_return_conditions", [])
    if isinstance(consumer_conditions, str):
        consumer_conditions = [consumer_conditions] if consumer_conditions else []

    return ProductDetails(
        product_id=product.get("product_id"),
        product_name=product.get("product_name"),
        category=product.get("category"),
        price=average_price,
        quantity_available=available_items_count,
        unit=product.get("unit", "pcs"),
        store_id=product.get("store_id"),
        tax=product.get("tax", 0),
        consumer_return_conditions=consumer_conditions
    )

async def get_sales_order_by_id(order_id: str, store_id: str):
    order = await db.SalesOrders.find_one(
         {
            "order_id": order_id,
            "store_id": store_id,
            "order_status": {"$in": ["0", "1"]},  # Allow both statuses
        },
        {"_id": 0}
    )

    if not order:
        raise HTTPException(status_code=404, detail="Order not found or already processed.")

    updated_products = []

    for product in order.get("products", []):
        product_id = product.get("product_id")
        ordered_quantity = int(product.get("order_quantity", 0))
        item_ids = product.get("item_ids", [])

        # ✅ Count available items from ProductItems collection
        available_items_count = await db.ProductItems.count_documents({
            "product_id": product_id,
            "store_id": store_id,
            "status": "available"
        })

        # Determine product status based on available items
        product_status = "Stock-out" if available_items_count < ordered_quantity else "Stock-in"
        product["product_status"] = product_status
        
        # ✅ ITEM-BASED APPROACH: Fetch full item details if item_ids exist
        if item_ids:
            items_details = []
            for item_id in item_ids:
                item = await db.ProductItems.find_one({
                    "item_id": item_id,
                    "product_id": product_id,
                    "store_id": store_id
                }, {"_id": 0})
                
                if item:
                    items_details.append({
                        "item_id": item_id,
                        "vendor_id": item.get("vendor_id"),
                        "vendor_name": item.get("vendor_name", "Unknown"),
                        "contract_id": item.get("contract_id"),
                        "purchase_date": item.get("purchase_date"),
                        "delivery_date": item.get("delivery_date"),
                        "unit_price": item.get("unit_price"),
                        "batch_number": item.get("batch_number"),
                        "serial_number": item.get("serial_number"),
                        "status": item.get("status"),
                        "has_warranty": item.get("has_warranty", False),
                        "warranty_tenure": item.get("warranty_tenure", 0),
                        "warranty_unit": item.get("warranty_unit", "months"),
                        "is_consumer_returnable": item.get("is_consumer_returnable", False),
                        "consumer_return_conditions": item.get("consumer_return_conditions", []),
                        "is_seller_returnable": item.get("is_seller_returnable", False),
                        "seller_return_conditions": item.get("seller_return_conditions", [])
                    })
            
            product["items"] = items_details
        
        updated_products.append(product)

    # Final transformation
    order["products"] = updated_products
    order["status"] = parse_status_string(order.get("status", "0"))

    if "order_status" in order:
        del order["order_status"]

    return order

async def get_sold_order_by_id(order_id: str, store_id: str):
    order = await db.SalesOrders.find_one(
        {"order_id": order_id, "store_id": store_id, "order_status": "1"},
        {"_id": 0}
    )

    if not order:
        return None

    # ✅ ITEM-BASED APPROACH: Enrich products with item details
    updated_products = []
    for product in order.get("products", []):
        product_id = product.get("product_id")
        item_ids = product.get("item_ids", [])
        
        # Fetch full item details if item_ids exist
        if item_ids:
            items_details = []
            for item_id in item_ids:
                item = await db.ProductItems.find_one({
                    "item_id": item_id,
                    "product_id": product_id,
                    "store_id": store_id
                }, {"_id": 0})
                
                if item:
                    items_details.append({
                        "item_id": item_id,
                        "vendor_id": item.get("vendor_id"),
                        "vendor_name": item.get("vendor_name", "Unknown"),
                        "contract_id": item.get("contract_id"),
                        "purchase_date": item.get("purchase_date"),
                        "delivery_date": item.get("delivery_date"),
                        "unit_price": item.get("unit_price"),
                        "batch_number": item.get("batch_number"),
                        "serial_number": item.get("serial_number"),
                        "status": item.get("status"),
                        "sold_at": item.get("sold_at"),
                        "sold_order_id": item.get("sold_order_id"),
                        "has_warranty": item.get("has_warranty", False),
                        "warranty_tenure": item.get("warranty_tenure", 0),
                        "warranty_unit": item.get("warranty_unit", "months"),
                        "is_consumer_returnable": item.get("is_consumer_returnable", False),
                        "consumer_return_conditions": item.get("consumer_return_conditions", []),
                        "is_seller_returnable": item.get("is_seller_returnable", False),
                        "seller_return_conditions": item.get("seller_return_conditions", [])
                    })
            
            product["items"] = items_details
        
        updated_products.append(product)
    
    order["products"] = updated_products
    
    # Convert order_status to a readable status and remove original key
    order["status"] = parse_status_string(order.get("order_status", ""))
    order.pop("order_status", None)

    return order


async def get_sales_dashboard_summary(store_id: str):
    # Get received (pending) orders
    received_orders = await db.SalesOrders.find(
        {"store_id": store_id, "order_status": "0"},
        {"_id": 0, "total_order_price": 1}
    ).to_list(length=None)

    # Get sold orders
    sold_orders = await db.SalesOrders.find(
        {"store_id": store_id, "order_status": "1"},
        {"_id": 0, "total_order_price": 1}
    ).to_list(length=None)

    # Get return orders count from ReturnOrders collection
    return_orders_count = await db.ReturnOrders.count_documents({"store_id": store_id})
    total_received = len(received_orders)
    total_sold = len(sold_orders)
    total_orders = total_received + total_sold

    sold_price_sum = 0.0
    for order in sold_orders:
        try:
            sold_price_sum += float(order.get("total_order_price", 0))
        except (ValueError, TypeError):
            continue

    return {
        "total_orders": total_orders,
        "received_orders": total_received,
        "sold_orders": total_sold,
        "sold_order_total_price": round(sold_price_sum, 2),
        "return_orders": return_orders_count
    }

async def get_sold_orders_by_month(store_id: str):
    """
    Aggregates sold orders (order_status=1) by month and year.
    Returns a list of {month, year, count}.
    """
    pipeline = [
        {
            "$match": {
                "store_id": store_id,
                "order_status": "1"
            }
        },
        {
            "$group": {
                "_id": {
                    "year": {"$year": "$order_date"},
                    "month": {"$month": "$order_date"}
                },
                "count": {"$sum": 1}
            }
        },
        {"$sort": SON([("_id.year", 1), ("_id.month", 1)])}
    ]

    result = await db.SalesOrders.aggregate(pipeline).to_list(length=None)

    # Convert to frontend-friendly format
    return [
        {
            "year": r["_id"]["year"],
            "month": r["_id"]["month"],
            "count": r["count"]
        }
        for r in result
    ]


async def get_return_orders_by_month(store_id: str):
    pipeline = [
        {"$match": {"store_id": store_id}},
        {"$addFields": {
            "return_date_parsed": {
                "$dateFromString": {
                    "dateString": "$return_date",
                    "format": "%Y-%m-%d"
                }
            }
        }},
        {"$group": {
            "_id": {
                "year": {"$year": "$return_date_parsed"},
                "month": {"$month": "$return_date_parsed"}
            },
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id.year": 1, "_id.month": 1}}
    ]

    result = await db.ReturnOrders.aggregate(pipeline).to_list(length=None)

    return [
        {"year": r["_id"]["year"], "month": r["_id"]["month"], "count": r["count"]}
        for r in result
    ]
