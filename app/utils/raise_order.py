from typing import Optional
from fastapi import HTTPException
from app.db import db
import re


async def generate_request_id():
    last_request = await db.RequestedOrders.find_one(   {"request_id": {"$regex": "^REQ\\d{3}$"}},   sort=[("request_id", -1)] )
    if last_request and last_request.get("request_id", "").startswith("REQ"):
        try:
            last_number = int(last_request["request_id"][3:])
            new_number = last_number + 1
        except ValueError:
            new_number = 1
    else:
        new_number = 1

    return f"REQ{new_number:03d}"

async def generate_order_id(): # type: ignore
    last_order = await db.SalesOrders.find_one(
        {"order_id": {"$regex": "^ORD\\d{3}$"}},
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


def build_product_detail(inventory_item: dict, product_id: str, unit_price: float, # type: ignore
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
        "tax": product_tax
    }

    return product_detail, line_total + tax

def parse_status_string(status: str) -> str:
    if status == "0":
        return "received"
    elif status == "1":
        return "sold"
    return status  # or "unknown"



# utils/id_generator.py or in your services file
async def _next_id(col, field_: str, prefix: str, store_id:Optional [str]=None) -> str: # type: ignore
    query = {field_: {"$regex": f"^{prefix}\\d+$"}}
    
    if store_id:
        query["store_id"] = store_id # type: ignore

    last = await col.find_one(query, sort=[(field_, -1)])

    if not last or field_ not in last:
        return f"{prefix}001"

    try:
        last_num = int(last[field_][len(prefix):])
        next_num = last_num + 1
    except (ValueError, TypeError):
        next_num = 1

    return f"{prefix}{str(next_num).zfill(3)}"


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
        "tax": product_tax
    }

    return product_detail, line_total + tax

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