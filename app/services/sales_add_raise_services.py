from datetime import datetime
from app.db import db
from fastapi import HTTPException
from app.models.sales_model import ReturnOrderRequest, SendToProcurement
from app.utils.sales_utils import enrich_products, fetch_inventory_details, generate_customer_id, generate_order_id, build_product_detail, generate_request_id, generate_return_id


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



async def prepare_request_data(order_id: str, store_id: str, estimate_date: str, org_id: str, requester: dict):
    order = await db.SalesOrders.find_one({"order_id": order_id, "store_id": store_id})
    if not order or not order.get("products"):
        raise HTTPException(status_code=404, detail="Sales order or products not found.")

    product = order["products"][0]
    product_name = product["product_name"]
    category = product["category"]
    unit = "pcs"  # Hardcoded, adjust if needed
    order_quantity = product.get("order_quantity", 0)

    inventory_item = await db.Inventory.find_one({"product_name": product_name, "store_id": store_id})
    if not inventory_item:
        raise HTTPException(status_code=404, detail="Product not found in inventory.")

    try:
        inventory_quantity = int(inventory_item.get("quantity", 0))
    except (ValueError, TypeError):
        inventory_quantity = 0

    requested_quantity = max(order_quantity - inventory_quantity, 0)
    if requested_quantity <= 0:
        raise HTTPException(status_code=400, detail="No extra quantity to request.")

    return {
        "org_id": org_id,
        "store_id": store_id,
        "product_name": product_name,
        "quantity": requested_quantity,
        "unit": unit,
        "category": category,
        "estimate_date": estimate_date,
        "requested_by": requester
    }

async def raise_request_order_service(order_id: str, estimate_date: str, org_id: str, store_id: str, requester: dict):
    request_data = await prepare_request_data(order_id, store_id, estimate_date, org_id, requester)
    request_id = await generate_request_id()
    request_data["request_id"] = request_id

    await db.RequestedOrders.insert_one(request_data)
    return request_id

# --- Helper function to fetch and validate the sales order ---
async def fetch_sales_order(order_id: str, store_id: str):
    order = await db.SalesOrders.find_one({"order_id": order_id, "store_id": store_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Sales order not found for this store")
    if order.get("order_status") != "1":
        raise HTTPException(status_code=400, detail="Only fulfilled (order_status=1) orders can be returned")
    return order

# --- Helper function to build return document ---
def build_return_doc(data, order, products, total_amount, return_id, store_id):
    return {
        "return_id": return_id,
        "order_id": data.order_id,
        "customer_id": order.get("customer_id"),
        "customer_name": order.get("customer_name"),
        "phone_no": order.get("customer_phone"),
        "email": order.get("customer_email"),
        "product": products,
        "return_date": datetime.utcnow().strftime("%Y-%m-%d"),
        "is_customer_returnable": True,
        "remarks": data.remarks,
        "reason": data.reason,
        "returned_amount": round(total_amount, 2),
        "sent_to_procurement": 0,
        "store_id": store_id
    }

# --- Main function that orchestrates the workflow ---
async def add_return(data: ReturnOrderRequest, store_id: str):
    # Fetch sales order
    order = await fetch_sales_order(data.order_id, store_id)

    products_list = order.get("products", [])
    if not products_list:
        raise HTTPException(status_code=404, detail="Product array is missing or empty in Sales Order")

    enriched_products, total_amount, skipped_products = await enrich_products(
        products_list, data.return_quantity, data.reason
    )
    
    if not enriched_products:
        raise HTTPException(
            status_code=404,
            detail=f"No valid product data eligible for return. Skipped products: {skipped_products}"
        )

    return_id = await generate_return_id()

    return_doc = build_return_doc(data, order, enriched_products, total_amount, return_id, store_id)
    await db.ReturnOrders.insert_one(return_doc)

    # Check return_quantity against order_quantity
    updated_products = []
    should_delete = True  # Assume deletion unless a product still has quantity left

    for product in products_list:
        order_qty = int(product.get("order_quantity", 0))
        if order_qty <= 0:
            continue
        
        if data.return_quantity >= order_qty:
            # The product is fully returned, so skip adding it to updated_products
            continue
        else:
            # Partial return, update the order_quantity
            product["order_quantity"] = order_qty - data.return_quantity
            updated_products.append(product)
            should_delete = False  # Since at least one product still has remaining quantity

    if should_delete:
        # Delete the entire order
        await db.SalesOrders.delete_one({"order_id": data.order_id, "store_id": store_id})
    else:
        # Update the order with the new product quantities
        await db.SalesOrders.update_one(
            {"order_id": data.order_id, "store_id": store_id},
            {"$set": {"products": updated_products}}
        )

    return {
        "message": "Return order added successfully",
        "return_id": return_id,
        "returned_amount": return_doc["returned_amount"],
        "enriched_products": enriched_products,
        "skipped_products": skipped_products
    }

