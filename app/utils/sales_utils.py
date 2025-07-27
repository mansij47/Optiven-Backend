import re
from fastapi import HTTPException
from app.db import db  # Adjust import if your db connection is elsewhere

async def generate_order_id():
    last_order = await db.SalesOrders.find_one(
        {"order_id": {"$regex": "^ORD\\d{3}$"}},{"_id": 0},
        sort=[("order_id", -1)]
    )

    if last_order and last_order.get("order_id", "").startswith("ORD"):
        try:
            last_number = int(last_order["order_id"][3:])
            new_number = last_number + 1
        except ValueError:
            new_number = 1
    else:
        new_number = 1

    return f"ORD{new_number:03d}"

def build_product_detail(inventory_item: dict, product_id: str, unit_price: float,
                         product_tax: float, order_quantity: int, inventory_quantity: int):
    line_total = unit_price * order_quantity
    tax = product_tax * order_quantity

    product_detail = {
        "product_id": product_id,
        "product_name": inventory_item["product_name"],
        "unit_price": unit_price,
        "category": inventory_item["category"],
        "order_quantity": order_quantity,
        "inventory_quantity": inventory_quantity,
        "tax": product_tax,
         "unit": inventory_item.get("unit", "")  # ✅ added this line to fetch 'unit
    }

    return product_detail, line_total + tax


# -----------------------------------------
# Function to generate sequential customer_id starting from CUT001
# -----------------------------------------
async def generate_customer_id():
    # Find the last customer_id starting with CUT
    last_order = await db.SalesOrders.find_one(
        {"customer_id": {"$regex": "^CUST"}},
        sort=[("customer_id", -1)]
    )
    
    if last_order and "customer_id" in last_order:
        # Extract numeric part
        match = re.search(r"CUST(\d+)", last_order["customer_id"])
        if match:
            next_num = int(match.group(1)) + 1
        else:
            next_num = 1
    else:
        next_num = 1

    return f"CUST{str(next_num).zfill(3)}"


async def generate_request_id():
    last_request = await db.RequestedOrders.find_one(
        {"request_id": {"$regex": "^REQ\\d{3}$"}},{"_id": 0},
        sort=[("request_id", -1)]
    )
    if last_request and last_request.get("request_id", "").startswith("REQ"):
        try:
            last_number = int(last_request["request_id"][3:])
            new_number = last_number + 1
        except ValueError:
            new_number = 1
    else:
        new_number = 1

    return f"REQ{new_number:03d}"


def parse_status_string(status: str) -> str:
    if status == "0":
        return "received"
    elif status == "1":
        return "sold"
    return status  # or "unknown"

def parse_return_status(status: int) -> str:
    return "return" if status == 0 else "procurement"

async def fetch_inventory_details(product_id: str, store_id: str):
    inventory_item = await db.Inventory.find_one({
        "product_id": product_id,
        "store_id": store_id
    }, {"_id": 0})

    if not inventory_item:
        raise HTTPException(status_code=404, detail=f"Product with ID {product_id} not found in inventory.")

    try:
        unit_price = float(inventory_item["unit_price"])
    except (ValueError, TypeError, KeyError):
        raise HTTPException(status_code=500, detail=f"Invalid unit price for product ID {product_id}.")

    try:
        product_tax = float(inventory_item.get("tax", 0))
    except (ValueError, TypeError):
        product_tax = 0

    inventory_quantity = int(inventory_item.get("quantity", 0)) if inventory_item else 0

    return {
        "inventory_item": inventory_item,
        "unit_price": unit_price,
        "product_tax": product_tax,
        "inventory_quantity": inventory_quantity
    }

# --- Helper function to generate new return_id ---
async def generate_return_id():
    latest = await db.ReturnOrders.find_one({},{"_id": 0}, sort=[("return_id", -1)])
    if latest and "return_id" in latest:
        last_num = int(latest["return_id"].replace("RET", ""))
        return f"RET{last_num + 1:03d}"
    else:
        return "RET001"
    
# --- Helper function to enrich products and calculate total returned amount ---
async def enrich_products(products: list, return_quantity: int, reason: str):
    print(products)
    enriched_products = []
    total_amount = 0.0

    for product in products:
        product_id = product.get("product_id")
        product_name = product.get("product_name")
        unit_price = product.get("unit_price", 0.0)
        tax = product.get("tax", 0.0)

        if not product_id or not product_name:
            continue

        # Fetch additional inventory info
        inventory = await db.Inventory.find_one({"product_id": product_id}, {"_id": 0})
        if not inventory:
            continue

        print(inventory.get("consumer_return_conditions", []))
        is_customer_returnable = inventory.get("is_consumer_returnable", False)
        consumer_conditions = inventory.get("consumer_return_conditions", [])
        print(consumer_conditions)        
        # Validate return eligibility
        if not is_customer_returnable or reason not in consumer_conditions:
            continue

        try:
            return_quantity = int(return_quantity)
            unit_price = float(unit_price)
            tax = float(tax)
        except (ValueError, TypeError):
            continue

        item_amount = (unit_price * return_quantity) - (tax * return_quantity)
        total_amount += item_amount

        enriched_products.append({
            "product_id": product_id,
            "product_name": product_name,
            "return_quantity": return_quantity,
            "unit_price": unit_price,
            "tax": tax,
            "is_customer_returnable": is_customer_returnable,
            "consumer_return_conditions": consumer_conditions,
            "is_seller_returnable": inventory.get("is_seller_returnable", False),
            "seller_return_conditions": inventory.get("seller_return_conditions", [])
        })
        print(enriched_products)

    return enriched_products, total_amount


