from typing import Optional
from app.db import db
from app.models.sales_model import ProductDetails, SalesOrderDetails, SalesProductItem
from app.services.sales_add_raise_services import fetch_inventory_details
from fastapi import HTTPException
from app.utils.sales_utils import build_product_detail, parse_return_status, parse_status_string
from bson.son import SON
async def get_all_sales_orders(store_id: str):
    orders = await db.SalesOrders.find(
        {"order_status": "0", "store_id": store_id},
        {"_id": 0}
    ).to_list(length=None)

    for order in orders:
        updated_products = []

        for product in order.get("products", []):
            product_id = product.get("product_id")
            ordered_quantity = int(product.get("order_quantity", 0))
            inventory_item = await db.Inventory.find_one({
                "store_id": store_id,
                "product_id": product_id
            })

            try:
                inventory_quantity = int(inventory_item.get("quantity", 0)) if inventory_item else 0
            except (ValueError, TypeError):
                inventory_quantity = 0

            # Compare and determine product_status
            product_status = "Stock-out" if inventory_quantity < ordered_quantity else "Stock-in"

            # Add product_status to product
            product["product_status"] = product_status
            updated_products.append(product)

        # Update products list
        order["products"] = updated_products

        # Convert status field
        order["status"] = parse_status_string(order.get("status", "0"))

        # Remove order_status field if present
        if "order_status" in order:
            del order["order_status"]

    return orders

async def get_all_sold_orders(store_id: str):
    orders = await db.SalesOrders.find(
        {"store_id": store_id, "order_status": "1"},
        {"_id": 0}
    ).to_list(length=None)

    for order in orders:
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
    for product in order.get("products", []):
        product_id = product.get("product_id")
        order_quantity = int(product.get("order_quantity", 0))  # Correct field

        # Fetch inventory item
        inventory_item = await db.Inventory.find_one({
            "product_id": product_id,
            "store_id": store_id
        },{"_id": 0})

        if not inventory_item:
            continue

        try:
            current_quantity = int(inventory_item.get("quantity", 0))
        except (ValueError, TypeError):
            current_quantity = 0

        # Calculate new quantity
        new_quantity = max(current_quantity - order_quantity, 0)

        # Update inventory
        await db.Inventory.update_one(
            {"product_id": product_id, "store_id": store_id},
            {"$set": {"quantity": new_quantity}}
        )

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
    await update_inventory_for_order(order, store_id)
    updated_count = await mark_order_status_as_sold(order_id, store_id)
    return updated_count


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
            try:
                quantity = int(product.get("quantity", 0))
            except (ValueError, TypeError):
                quantity = 0

            product["status"] = "Stock-in" if quantity > 0 else "Stock-out"
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

async def get_all_procurement_returns(store_id: str):
    cursor = db.ReturnOrders.find({"sent_to_procurement": 1,"store_id": store_id},{"_id":0})
    result = []
    async for r in cursor:
        result.append(r)  # Append the entire document as it is
    return result

async def get_procurement_return_by_id(return_id: str, store_id: str):
    return await db.ReturnOrders.find_one(
        {
            "return_id": return_id,
            "store_id": store_id,
            "sent_to_procurement": 1  # Only fetch if sent_to_procurement is 1
        },
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

    return ProductDetails(
        product_id=product.get("product_id"),
        product_name=product.get("product_name"),
        category=product.get("category"),
        price=float(product.get("unit_price", 0)),
        quantity_available=product.get("quantity", 0),
        unit=product.get("unit", "pcs"),
        store_id=product.get("store_id"),
        tax=product.get("tax", 0)
    )

async def get_sales_order_by_id(order_id: str, store_id: str):
    order = await db.SalesOrders.find_one(
        {"order_id": order_id, "order_status": "0", "store_id": store_id},
        {"_id": 0}
    )

    if not order:
        raise HTTPException(status_code=404, detail="Order not found or already processed.")

    updated_products = []

    for product in order.get("products", []):
        product_id = product.get("product_id")
        ordered_quantity = int(product.get("order_quantity", 0))

        inventory_item = await db.Inventory.find_one({
            "store_id": store_id,
            "product_id": product_id
        })

        try:
            inventory_quantity = int(inventory_item.get("quantity", 0)) if inventory_item else 0
        except (ValueError, TypeError):
            inventory_quantity = 0

        # Determine product status
        product_status = "Stock-out" if inventory_quantity < ordered_quantity else "Stock-in"
        product["product_status"] = product_status
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

    if order:
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

    total_received = len(received_orders)
    total_sold = len(sold_orders)
    total_orders = total_received + total_sold

    # Calculate total price sum of sold orders
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
        "sold_order_total_price": round(sold_price_sum, 2)
    }
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

        inventory_item = await db.Inventory.find_one({
            "store_id": store_id,
            "product_id": product_id
        })

        try:
            inventory_quantity = int(inventory_item.get("quantity", 0)) if inventory_item else 0
        except (ValueError, TypeError):
            inventory_quantity = 0

        # Determine product status
        product_status = "Stock-out" if inventory_quantity < ordered_quantity else "Stock-in"
        product["product_status"] = product_status
        updated_products.append(product)

    # Final transformation
    order["products"] = updated_products
    order["status"] = parse_status_string(order.get("status", "0"))

    if "order_status" in order:
        del order["order_status"]

    return order

async def get_sales_dashboard_summary(store_id: str):
    # Get received orders
    received_orders = await db.SalesOrders.find(
        {"store_id": store_id, "order_status": "0"},
        {"_id": 0, "total_order_price": 1}
    ).to_list(length=None)

    # Get sold orders
    sold_orders = await db.SalesOrders.find(
        {"store_id": store_id, "order_status": "1"},
        {"_id": 0, "total_order_price": 1}
    ).to_list(length=None)

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
