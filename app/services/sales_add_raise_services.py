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

    print(f"Final products: {final_products}")
    # Fill order fields
    order_data["products"] = final_products
    order_data["total_order_price"] = round(subtotal, 2)
    order_data["order_id"] = await generate_order_id()
    order_data["customer_id"] = customer_id
    order_data["status"] = "received"  # Changed from order_status to status
    order_data["store_id"] = store_id

    # Fix: Collect return conditions from all products
    order_data["consumer_return_conditions"] = [
        condition
        for product in final_products
        for condition in product.get("consumer_return_conditions", [])
    ]

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
            inventory_quantity=inventory_data["inventory_quantity"],
            consumer_return_conditions=inventory_data["consumer_return_conditions"]
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
    # if requested_quantity <= 0:
    #     raise HTTPException(status_code=400, detail="No extra quantity to request.(Inventory has enough stock)")

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
    
    # Check if product already exists in requested orders
    existing_request = await db.RequestedOrders.find_one({
        "product_name": request_data["product_name"],
        "store_id": store_id,
        "org_id": org_id
    })
    
    if existing_request:
        # Update existing request: add quantities and update other fields
        new_quantity = existing_request.get("quantity", 0) + request_data["quantity"]
        
        await db.RequestedOrders.update_one(
            {"_id": existing_request["_id"]},
            {
                "$set": {
                    "quantity": new_quantity,
                    "estimate_date": estimate_date,
                    "requested_by": requester,
                    "updated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                }
            }
        )
        return existing_request["request_id"]
    else:
        # Create new request
        request_id = await generate_request_id()
        request_data["request_id"] = request_id
        request_data["created_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        
        await db.RequestedOrders.insert_one(request_data)
        return request_id

# --- Helper function to fetch and validate the sales order ---
async def fetch_sales_order(order_id: str, store_id: str):
    # Clean the input strings to remove any whitespace or tabs
    order_id = order_id.strip()
    store_id = store_id.strip()
    
    # Debug print to check what we're searching for
    print(f"Searching for order_id: '{order_id}' in store_id: '{store_id}'")
    
    # Find the specific order for this store
    order = await db.SalesOrders.find_one({"order_id": order_id, "store_id": store_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail=f"Sales order not found for order_id: {order_id} and store_id: {store_id}")
    
    # Check both status fields - handle both old and new format
    order_status = order.get("order_status")
    status = order.get("status")
    
    # Order is returnable if either:
    # - order_status is "1" (old format) OR
    # - status is "received" (new format)
    if order_status != "1" and status != "received":
        current_status = status or order_status
        raise HTTPException(
            status_code=400, 
            detail=f"Order cannot be returned. Current status: {current_status}. Order must be either fulfilled (status=1) or received."
        )
    
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
        "status": "pending",
        "store_id": store_id
    }

# --- Main function that orchestrates the workflow ---
async def add_return(data: ReturnOrderRequest, store_id: str):
    try:
        # Fetch sales order
        order = await fetch_sales_order(data.order_id, store_id)
        
        products_list = order.get("products", [])
        if not products_list:
            raise HTTPException(status_code=404, detail="Product array is missing or empty in Sales Order")
    except HTTPException as e:
        # Add more context to the error
        raise HTTPException(
            status_code=e.status_code,
            detail=f"Error processing return for order {data.order_id}: {str(e.detail)}"
        )

    # ✅ Pass order_id and store_id to enrich_products for item-level tracking
    enriched_products, total_amount, skipped_products = await enrich_products(
        products_list, data.return_quantity, data.reason, order_id=data.order_id, store_id=store_id
    )
    
    if not enriched_products:
        raise HTTPException(
            status_code=404,
            detail=f"No valid product data eligible for return. Skipped products: {skipped_products}"
        )

    return_id = await generate_return_id()

    return_doc = build_return_doc(data, order, enriched_products, total_amount, return_id, store_id)
    await db.ReturnOrders.insert_one(return_doc)

    # ✅ ITEM-BASED APPROACH: Update order by removing returned item_ids
    updated_products = []
    should_delete = True  # Assume deletion unless a product still has items left

    for product in products_list:
        product_id = product.get("product_id")
        order_qty = int(product.get("order_quantity", 0))
        product_item_ids = product.get("item_ids", [])
        
        if order_qty <= 0:
            continue
        
        # Find which items are being returned for this product
        returned_item_ids = []
        for enriched in enriched_products:
            if enriched.get("product_id") == product_id:
                returned_item_ids = enriched.get("item_ids", [])
                break
        
        # Remove returned item_ids from product's item_ids list
        remaining_item_ids = [item_id for item_id in product_item_ids if item_id not in returned_item_ids]
        
        if data.return_quantity >= order_qty or len(remaining_item_ids) == 0:
            # The product is fully returned, skip adding it to updated_products
            continue
        else:
            # Partial return, update the order_quantity and item_ids
            product["order_quantity"] = len(remaining_item_ids)
            product["item_ids"] = remaining_item_ids
            updated_products.append(product)
            should_delete = False  # Since at least one product still has remaining items

    if should_delete:
        # Delete the entire order
        await db.SalesOrders.delete_one({"order_id": data.order_id, "store_id": store_id})
    else:
        # Update the order with the new product quantities and item_ids
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

