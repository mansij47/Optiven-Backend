from fastapi import HTTPException
from app.db import db
from app.utils.raise_order import build_product_detail, fetch_inventory_details, generate_customer_id, generate_order_id, parse_status_string

# it includes both - sold orders and requested orders

async def get_all_sold_orders(store_id: str):
    # Filter orders by store_id and order_status = "1"
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




# adding new order of customer

async def add_sales_order(order_data: dict, store_id: str):
    # Generate customer_id
    customer_id = await generate_customer_id()

    # Process products
    final_products, subtotal = await process_products(order_data.get("products", []), store_id)

    # Fill order fields
    order_data["products"] = final_products
    order_data["total_order_price"] = round(subtotal, 2)
    order_data["order_id"] = await generate_order_id()
    order_data["customer_id"] = customer_id
    order_data["order_status"] = "0"
    order_data["store_id"] = store_id

    # Insert into SalesOrders
    await db.SalesOrders.insert_one(order_data)
    return order_data["order_id"]

async def process_products(products: list, store_id: str):
    final_products = []
    subtotal = 0.0

    for prod in products:
        product_id = prod["product_id"]
        order_quantity = prod["quantity"]

        inventory_data = await fetch_inventory_details(product_id, store_id)

        product_detail, total_with_tax = build_product_detail(
            inventory_item=inventory_data["inventory_item"],
            product_id=product_id,
            unit_price=inventory_data["unit_price"],
            product_tax=inventory_data["product_tax"],
            order_quantity=order_quantity,
            inventory_quantity=inventory_data["inventory_quantity"]
        )

        subtotal += total_with_tax
        final_products.append(product_detail)

    return final_products, subtotal