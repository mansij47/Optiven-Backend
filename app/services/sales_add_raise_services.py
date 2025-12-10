from datetime import datetime
from app.db import db
from fastapi import HTTPException
from pymongo import ReturnDocument
from app.models.sales_model import ReturnOrderRequest, SendToProcurement
from app.utils.sales_utils import enrich_products, fetch_inventory_details, generate_customer_id, generate_order_id, build_product_detail, generate_request_id, generate_return_id

async def add_sales_order(order_data: dict, store_id: str):
    # Generate customer_id
    customer_id = await generate_customer_id()

    # Process products and detect preorder/stock-out condition
    final_products, subtotal, stock_out_or_preorder = await process_products(order_data.get("products", []), store_id)

    # print(f"[DEBUG] Final products after processing: {final_products}")
    # Fill order fields
    order_data["products"] = final_products
    order_data["total_order_price"] = round(subtotal, 2)
    order_data["order_id"] = await generate_order_id()
    order_data["customer_id"] = customer_id
    
    # Set type and status based on inventory availability
    if stock_out_or_preorder:
        order_data["type"] = "preorder"
        order_data["status"] = "Preorder"  # Changed from "Stock-out" to "Preorder"
    else:
        order_data["type"] = "order"
        order_data["status"] = "Stock-in"
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
    stock_out_or_preorder = False

    # print(f"[DEBUG] Incoming products to process: {products}")
    
    for prod in products:
        product_id = prod.get("product_id", "")
        order_quantity = prod["quantity"]
        
        # print(f"[DEBUG] Processing product: product_id='{product_id}', product_name='{prod.get('product_name')}', quantity={order_quantity}")

        # Check if product_id is empty (preorder case) - skip inventory lookup
        if not product_id or product_id.strip() == "":
            # Product not found in inventory -> preorder
            # Leave product_id empty - will be populated when inventory is created
            # Try multiple field names for product name
            product_name = (prod.get("product_name") or 
                          prod.get("name") or 
                          prod.get("product") or 
                          "Unknown")
            # print(f"Product not in inventory (empty product_id), creating preorder: {prod}")
            # print(f"[DEBUG] Extracted product_name: {product_name}")
            
            product_detail = {
                "product_id": "",  # Empty - will be updated when inventory is added
                "product_name": product_name,
                "unit_price": 0,
                "category": prod.get("category", ""),
                "order_quantity": order_quantity,
                "inventory_quantity": 0,
                "tax": 0,
                "unit": prod.get("unit", "pcs"),
                "consumer_return_conditions": [],
                "product_status": "Preorder"
            }
            stock_out_or_preorder = True
            final_products.append(product_detail)
            continue  # Skip to next product

        try:
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

            # Check inventory status and quantity
            inventory_status = inventory_data["inventory_item"].get("status", "")
            
            # If inventory is Stock-out OR insufficient quantity -> mark as Preorder
            if inventory_status in ["Stock-out", "stock-out", "stockout"] or inventory_data["inventory_quantity"] < order_quantity:
                product_detail["product_status"] = "Stock-out"  # Changed from "Stock-out" to "Preorder"
                stock_out_or_preorder = True
            else:
                product_detail["product_status"] = "Stock-in"

            subtotal += total_with_tax
            final_products.append(product_detail)
            
        except HTTPException:
            # Product not found in inventory -> preorder
            # Leave product_id empty - will be populated when inventory is created
            product_name = prod.get("product_name") or prod.get("name") or "Unknown"
            print(f"Product not in inventory, creating preorder: {prod}")
            print(f"[DEBUG] Extracted product_name: {product_name}")
            
            product_detail = {
                "product_id": "",  # Empty - will be updated when inventory is added
                "product_name": product_name,
                "unit_price": 0,
                "category": prod.get("category", ""),
                "order_quantity": order_quantity,
                "inventory_quantity": 0,
                "tax": 0,
                "unit": prod.get("unit", "pcs"),
                "consumer_return_conditions": [],
                "product_status": "Preorder"
            }
            stock_out_or_preorder = True
            final_products.append(product_detail)

    return final_products, subtotal, stock_out_or_preorder



async def prepare_request_data(order_id: str, store_id: str, estimate_date: str, org_id: str, requester: dict):
    order = await db.SalesOrders.find_one({"order_id": order_id, "store_id": store_id})
    if not order or not order.get("products"):
        raise HTTPException(status_code=404, detail="Sales order or products not found.")

    product = order["products"][0]
    product_name = product["product_name"]
    category = product["category"]
    unit = "pcs"  # Hardcoded, adjust if needed
    order_quantity = product.get("order_quantity", 0)
    
    # ✅ Get order type from sales order (preorder or order)
    order_type = order.get("type", "order")  # Default to "order" if not specified

    # print(f"[DEBUG] Preparing request for product: {product_name}, order_quantity: {order_quantity}")

    # Try to find inventory item (may not exist for preorders) - case-insensitive
    inventory_item = await db.Inventory.find_one({
        "product_name": {"$regex": f"^{product_name}$", "$options": "i"},
        "store_id": store_id
    })
    
    # Determine requested quantity based on order type and inventory status
    if not inventory_item:
        # Product not in inventory at all (preorder) - request full order quantity
        # print(f"[DEBUG] Product not found in inventory - requesting full order quantity: {order_quantity}")
        requested_quantity = order_quantity
    else:
        # Check inventory status and quantity
        inventory_status = inventory_item.get("status", "")
        inventory_quantity = int(inventory_item.get("quantity", 0)) if inventory_item.get("quantity") else 0
        min_stock = int(inventory_item.get("min_stock", 0)) if inventory_item.get("min_stock") else 0
        
        # print(f"[DEBUG] Inventory found - status: {inventory_status}, quantity: {inventory_quantity}, min_stock: {min_stock}")
        
        # If inventory is Stock-out OR quantity is below min_stock OR insufficient for order, request what's needed
        if (inventory_status in ["Stock-out", "stock-out", "stockout"] or 
            inventory_quantity < min_stock or 
            inventory_quantity < order_quantity):
            # Need more stock - request full order quantity
            # print(f"[DEBUG] Need more stock (status={inventory_status}, qty={inventory_quantity}, min={min_stock}, order={order_quantity}) - requesting: {order_quantity}")
            requested_quantity = order_quantity
        else:
            # Sufficient stock available
            requested_quantity = 0
            # print(f"[DEBUG] Sufficient stock available - requested: {requested_quantity}")

    # print(f"[DEBUG] Final requested_quantity: {requested_quantity}")
    
    return {
        "org_id": org_id,
        "store_id": store_id,
        "product_name": product_name,
        "quantity": requested_quantity,
        "unit": unit,
        "category": category,
        "estimate_date": estimate_date,
        "requested_by": requester,
        "type": order_type,  # ✅ Propagate order type
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

# async def raise_request_order_service(order_id: str, estimate_date: str, org_id: str, store_id: str, requester: dict):
#     request_data = await prepare_request_data(order_id, store_id, estimate_date, org_id, requester)
    
#     # Check if product already exists in requested orders
#     existing_request = await db.RequestedOrders.find_one({
#         "product_name": request_data["product_name"],
#         "store_id": store_id,
#         "org_id": org_id
#     })
    
#     if existing_request:
#         # Update existing request: add quantities and update other fields
#         new_quantity = existing_request.get("quantity", 0) + request_data["quantity"]
        
#         await db.RequestedOrders.update_one(
#             {"_id": existing_request["_id"]},
#             {
#                 "$set": {
#                     "quantity": new_quantity,
#                     "estimate_date": estimate_date,
#                     "requested_by": requester,
#                     "updated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
#                 }
#             }
#         )
#         return existing_request["request_id"]
#     else:
#         # Create new request
#         request_id = await generate_request_id()
#         request_data["request_id"] = request_id
#         request_data["created_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        
#         await db.RequestedOrders.insert_one(request_data)
#         return request_id


async def raise_request_order_service(order_id: str, estimate_date: str, org_id: str, store_id: str, requester: dict):
    request_data = await prepare_request_data(order_id, store_id, estimate_date, org_id, requester)

    # print(f"[DEBUG] Request data prepared: {request_data}")

    # ---- Minimal hardening ----
    qty = int(request_data.get("quantity", 0))
    if qty < 0:
        raise ValueError("quantity cannot be negative")
    
    if qty == 0:
        raise HTTPException(status_code=400, detail="Cannot raise request with 0 quantity. Product may already be in stock.")

    print(f"[DEBUG] Quantity to increment: {qty}")

    # Build a deterministic matcher (add category if present in your data)
    matcher = {
        "store_id": store_id,
        "org_id": org_id,
        "product_name": request_data["product_name"],
    }
    if request_data.get("category"):
        matcher["category"] = request_data["category"]
    
    # print(f"[DEBUG] Matcher: {matcher}")

    # Prepare $setOnInsert with all fields from request_data except 'quantity' and fields in $set
    insert_snapshot = dict(request_data)  # shallow copy
    insert_snapshot.pop("quantity", None)  # quantity will be handled by $inc only
    insert_snapshot.pop("estimate_date", None)  # estimate_date will be handled by $set
    insert_snapshot.pop("requested_by", None)  # requested_by will be handled by $set
    insert_snapshot.update({
        "request_id": await generate_request_id(),
        "order_id": order_id,
        "created_at": datetime.utcnow(), 
        "updated_at": datetime.utcnow(),
    })

    # One atomic upsert handles both paths:
    # - If exists: increments quantity + updates mutable fields + updated_at
    # - If not exists: inserts snapshot + sets created_at + then $inc sets quantity from 0 -> qty
    doc = await db.RequestedOrders.find_one_and_update(
        filter=matcher,
        update={
            "$inc": {"quantity": qty},  # ✅ atomic; no race conditions
            "$set": {
                "estimate_date": estimate_date,
                "requested_by": requester,
                "updated_at": datetime.utcnow(),  # ✅ real datetime
            },
            "$setOnInsert": insert_snapshot,
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )

    return doc["request_id"]


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

