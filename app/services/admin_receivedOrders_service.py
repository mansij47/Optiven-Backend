
from fastapi import HTTPException
from app.db import db
from app.utils.raise_order import build_product_detail, fetch_inventory_details, parse_status_string

# recieved orders by customer

async def get_all_sales_orders(store_id: str):
    # Fetch orders strictly with status = "0" (received)
    orders = await db.SalesOrders.find(
        {"order_status": "0", "store_id": store_id},
        {"_id": 0}
    ).to_list(length=None)

    for order in orders:
        updated_products = []

        for product in order.get("products", []):
            product_id = product.get("product_id")
            ordered_quantity = int(product.get("order_quantity", 0))

            # Fetch from Inventory
            inventory_item = await db.Inventory.find_one({
                "store_id": store_id,
                "product_id": product_id
            },
            {"_id":0})

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

async def delete_order_by_id(order_id: str, store_id: str) -> int:
    result = await db.SalesOrders.delete_one({
        "order_id": order_id,
        "store_id": store_id
    })
    return result.deleted_count


async def update_sales_order(order_id: str, store_id: str, updated_data: dict):
    order = await db.SalesOrders.find_one({"order_id": order_id, "store_id": store_id},{"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found or does not belong to your store.")

    original_products = order.get("products", [])
    updated_products, subtotal = await rebuild_products_list(original_products, updated_data.get("products", []), store_id)

    # Prepare final update dict
    final_update_data = prepare_updated_order_data(updated_data, updated_products, subtotal, order, store_id, order_id)

    result = await db.SalesOrders.update_one(
        {"order_id": order_id, "store_id": store_id},
        {"$set": final_update_data}
    )

    return result.modified_count

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

def get_new_quantity_for_product(product_id: str, updated_products: list, default_quantity: int) -> int:
    for p in updated_products:
        if p["product_id"] == product_id:
            return p["quantity"]
    return default_quantity
    
def prepare_updated_order_data(updated_data: dict, updated_products: list, subtotal: float, order: dict, store_id: str, order_id: str):
    updated_data["products"] = updated_products
    updated_data["total_order_price"] = round(subtotal, 2)
    updated_data["order_status"] = order.get("order_status", "0")
    updated_data["store_id"] = store_id
    updated_data["order_id"] = order_id
    updated_data["customer_id"] = order.get("customer_id")
    return updated_data

    
