from typing import Optional
from app.db import db
from app.models.sales_model import ProductDetails, SalesOrderDetails, SalesProductItem
from app.services.sales_add_raise_services import fetch_inventory_details
from app.utils.tax_utils import calculate_product_total_with_tax
from fastapi import HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from app.utils.sales_utils import build_product_detail, parse_return_status, parse_status_string
from app.utils.sold_order_pdf_utils import generate_sold_order_pdf
from app.utils.received_order_pdf_utils import generate_received_order_pdf
from bson.son import SON
from datetime import datetime,timezone
from app.utils.inventory_sync import sync_inventory_on_change

sales_orders_collection = db["SalesOrders"]
requested_orders_collection = db["RequestedOrders"]
stores_collection = db["Stores"]



# ✅ Helper function to calculate average selling_price from available items
async def calculate_average_selling_price_from_items(product_id: str, store_id: str) -> float:
    """
    Calculate average selling_price from all available items of a product.
    Only uses selling_price field. Returns 0.0 if no items found or items don't have selling_price.
    """
    if not product_id:
        return 0.0
    
    items_cursor = db.ProductItems.find({
        "product_id": product_id,
        "store_id": store_id,
        "status": "available"
    }, {"selling_price": 1, "_id": 0})
    
    items = await items_cursor.to_list(length=None)
    
    if not items:
        return 0.0
    
    total_price = 0.0
    valid_count = 0
    
    for item in items:
        try:
            price_value = item.get("selling_price", 0)
            if isinstance(price_value, str):
                price_value = float(price_value) if price_value and price_value != "0" else 0.0
            else:
                price_value = float(price_value) if price_value else 0.0
            
            if price_value > 0:
                total_price += price_value
                valid_count += 1
        except (ValueError, TypeError):
            continue
    
    if valid_count > 0:
        return round(total_price / valid_count, 2)
    
    return 0.0


# ✅ Helper function to calculate total price for a product (same logic as Add Order)
def calculate_product_total_price(unit_price: float, tax: float, quantity: int) -> float:
    """
    Calculate total price for a product: quantity * (unit_price + tax_amount)
    Uses centralized tax calculation utility from tax_utils
    """
    return calculate_product_total_with_tax(unit_price, tax, quantity)


async def get_all_sales_orders(store_id: str):
    """
    Fetch sales orders history.
    - READ ONLY
    - NO inventory queries
    - NO recalculations
    - SINGLE DB CALL
    """

    # ✅ 1 DB READ ONLY
    orders = await db.SalesOrders.find(
        {"store_id": store_id},
        {"_id": 0}
    ).sort([("_id", -1)]).to_list(length=None)

    for order in orders:
        updated_products = []

        for product in order.get("products", []):
            # ✅ Use snapshot values stored at order time
            product_data = {
                "product_id": product.get("product_id"),
                "product_name": product.get("product_name"),
                "order_quantity": int(product.get("order_quantity", 0)),
                "unit_price": float(product.get("unit_price", 0)),
                "tax": float(product.get("tax", 0)),
                "product_status": product.get("product_status", "Unknown"),
                "item_ids": product.get("item_ids", []),
            }

            # ✅ UI helpers (NO DB CALLS)
            item_ids = product_data["item_ids"]
            product_data["item_count"] = len(item_ids)
            product_data["has_item_details"] = bool(item_ids)

            updated_products.append(product_data)

        # Replace products list safely
        order["products"] = updated_products

        # ✅ Use stored total_order_price (NO recalculation)
        order["total_order_price"] = float(
            order.get("total_order_price", 0)
        )

        # ✅ Include currency field
        order["currency"] = order.get("currency", "INR")

        # ✅ Parse order status (existing logic preserved)
        order["status"] = parse_status_string(order.get("status", "0"))

        # Cleanup (existing behavior)
        order.pop("order_status", None)

    return orders



async def get_all_sold_orders(store_id: str):
    cursor = db.SalesOrders.find(
        {"store_id": store_id, "order_status": "1"},
        {"_id": 0}
    ).sort([("_id", -1)])   # ✅ latest first

    orders = await cursor.to_list(length=None)

    for order in orders:
        # ✅ ITEM-BASED APPROACH: Add item count and selling_price for each product
        updated_products = []
        for product in order.get("products", []):
            product_id = product.get("product_id")
            item_ids = product.get("item_ids", [])
            
            # ✅ Calculate average selling_price from items using helper function
            avg_selling_price = await calculate_average_selling_price_from_items(product_id, store_id)
            product["unit_price"] = avg_selling_price  # Set to 0 if no selling_price exists
            
            # Add item tracking metadata
            if item_ids:
                product["item_count"] = len(item_ids)
                product["has_item_details"] = True
            else:
                product["item_count"] = 0
                product["has_item_details"] = False
            
            updated_products.append(product)
        
        order["products"] = updated_products
        
        # ✅ Recalculate total_order_price dynamically using selling_price
        total_order_price = 0.0
        for product in updated_products:
            selling_price = float(product.get("selling_price", 0))
            tax = float(product.get("tax", 0))
            quantity = int(product.get("order_quantity", 0))
            product_total = calculate_product_total_price(selling_price, tax, quantity)
            total_order_price += product_total
        
        # ✅ Add shipping charges to total if present
        shipping_charges = float(order.get("shipping_charges", 0))
        order["shipping_charges"] = shipping_charges
        order["total_order_price"] = round(total_order_price + shipping_charges, 2)
        
        # Convert order_status to status text
        order["status"] = parse_status_string(order["order_status"])
        # Remove raw order_status field from final output
        order.pop("order_status", None)

    return orders


async def fetch_order_and_validate(order_id: str, store_id: str):
    # ✅ Fetch order with basic validation
    order = await db.SalesOrders.find_one({
        "order_id": order_id,
        "store_id": store_id,
        "order_status": "0"   # Not yet sold
    },{"_id": 0})
    
    if not order:
        # Check if order exists but is already sold
        existing_order = await db.SalesOrders.find_one({
            "order_id": order_id,
            "store_id": store_id
        }, {"order_status": 1, "quotation_status": 1, "_id": 0})
        
        if existing_order:
            if existing_order.get("order_status") == "1":
                raise HTTPException(status_code=404, detail="Order already sold.")
            elif existing_order.get("quotation_status") == "completed":
                raise HTTPException(status_code=404, detail="Quotation already completed.")
        
        raise HTTPException(status_code=404, detail="Order not found.")
    
    # Additional check: if order has quotation_status field, verify it's not completed
    if order.get("quotation_status") == "completed":
        raise HTTPException(status_code=404, detail="Quotation already completed.")
    
    return order

async def update_inventory_for_order(order, store_id: str, tax: float = None):
    sold_items_map = {}  # Track which items were sold for each product
    
    # ✅ Extract customer information from order
    customer_name = order.get("customer_name", "N/A")
    customer_phone = order.get("customer_phone", "N/A")
    customer_email = order.get("customer_email", "N/A")
    order_id = order.get("order_id")
    
    # ✅ DEBUG: Log the order and store_id
    print(f"🔍 [SELL] Processing order for store_id: {store_id}")
    print(f"🔍 [SELL] Order products: {order.get('products', [])}")
    print(f"🔍 [SELL] Customer: {customer_name} ({customer_email})")
    
    # ✅ VALIDATION PHASE: Check all products before making any changes
    for product in order.get("products", []):
        product_id = product.get("product_id")
        product_name = product.get("product_name", "Unknown")
        order_quantity = int(product.get("order_quantity", 0))
        
        print(f"🔍 [SELL] Validating product: {product_name} (ID: {product_id}), Qty: {order_quantity}")
        
        if not product_id or product_id.strip() == "":
            print(f"❌ [SELL] Product '{product_name}' has empty product_id - likely a preorder item")
            raise HTTPException(
                status_code=400,
                detail=f"Product '{product_name}' is missing product_id. Cannot process order. This might be a preorder item that hasn't been added to inventory yet."
            )
        
        # Check if product exists in inventory
        product_doc = await db.Inventory.find_one(
            {"product_id": product_id, "store_id": store_id}
        )
        
        if not product_doc:
            print(f"❌ [SELL] Product not found in Inventory: product_id={product_id}, store_id={store_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Product '{product_name}' (ID: {product_id}) not found in store {store_id} inventory. Please add this product to your store's inventory first."
            )
        
        # Check available quantity
        available_count = await db.ProductItems.count_documents({
            "product_id": product_id,
            "store_id": store_id,
            "status": "available"
        })
        
        print(f"✅ [SELL] Found {available_count} available items for {product_name}")
        
        if available_count < order_quantity:
            print(f"❌ [SELL] Insufficient stock: need {order_quantity}, have {available_count}")
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for '{product_name}'. Required: {order_quantity}, Available: {available_count} in store {store_id}"
            )
    
    # ✅ EXECUTION PHASE: All validations passed, now process the sale
    print(f"✅ [SELL] Validation complete! Starting execution phase...")
    
    for product in order.get("products", []):
        product_id = product.get("product_id")
        order_quantity = int(product.get("order_quantity", 0))
        
        print(f"🔄 [SELL] Processing sale for: {product.get('product_name')} (ID: {product_id})")
        
        # ✅ Get selling_price from order's product (custom price set by sales)
        order_selling_price = product.get("selling_price")
        
        if not order_selling_price:
            product_doc = await db.Inventory.find_one(
                {"product_id": product_id, "store_id": store_id},
                {"average_selling_price": 1}
            )
            order_selling_price = product_doc.get("average_selling_price") if product_doc else None

        # ✅ Find available items for this product
        available_items = await db.ProductItems.find(
            {
                "product_id": product_id,
                "store_id": store_id,
                "status": "available"
            }
        ).limit(order_quantity).to_list(order_quantity)

        print(f"🔄 [SELL] Found {len(available_items)} items to mark as sold")

        # Store the item IDs that were sold for this product
        sold_item_ids = []
        
        # ✅ Mark each item as sold with actual selling_price from order and Tax (sales GST)
        for item in available_items:
            item_id = item["item_id"]
            sold_item_ids.append(item_id)
            
            # ✅ Create history entry for this sale with customer information
            sale_history_entry = {
                "event_type": "sale",
                "order_id": order_id,
                "customer_name": customer_name,
                "customer_phone": customer_phone,
                "customer_email": customer_email,
                "selling_price": order_selling_price,
                "sold_at": datetime.utcnow(),
                "timestamp": datetime.utcnow()
            }
            
            # Add tax to history if provided
            if tax is not None:
                sale_history_entry["tax"] = tax
            
            update_data = {
                "$set": {
                    "status": "sold",
                    "updated_at": datetime.utcnow(),
                    "sold_order_id": order_id,
                    "sold_at": datetime.utcnow()
                },
                "$push": {
                    "history": sale_history_entry
                }
            }
            
            # ✅ Update Tax field (sales GST) if provided from popup
            if tax is not None:
                update_data["$set"]["Tax"] = tax
            
            # ✅ Add store_id to update filter for safety
            result = await db.ProductItems.update_one(
                {"item_id": item_id, "store_id": store_id},
                update_data
            )
            print(f"✅ [SELL] Marked item {item_id} as sold - Modified count: {result.modified_count}")
            
            # Verify the update actually worked
            verify_item = await db.ProductItems.find_one({"item_id": item_id, "store_id": store_id})
            # print(f"🔍 [SELL] Verified item {item_id} status after update: {verify_item.get('status')}, store: {verify_item.get('store_id')}")

        # Store the sold items for this product
        sold_items_map[product_id] = sold_item_ids
        print(f"✅ [SELL] Sold {len(sold_item_ids)} items for product {product_id}")

        # ✅ DEBUG: Check ALL items for this product to see actual statuses
        all_items_debug = await db.ProductItems.find({
            "product_id": product_id,
            "store_id": store_id
        }, {"item_id": 1, "status": 1, "_id": 0}).to_list(None)
        # print(f"🔍 [SELL] ALL items for {product_id} in {store_id}: {all_items_debug}")

        # ✅ Update product quantity (count remaining available items)
        remaining_items = await db.ProductItems.count_documents({
            "product_id": product_id,
            "store_id": store_id,
            "status": "available"
        })
        
        # print(f"🔍 [SELL] Counting remaining items - product_id: {product_id}, store_id: {store_id}, remaining: {remaining_items}")

        await db.Inventory.update_one(
            {"product_id": product_id, "store_id": store_id},
            {
                "$set": {
                    "quantity": remaining_items,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        print(f"✅ [SELL] Updated inventory quantity to {remaining_items} for product {product_id}")
    
    print(f"✅ [SELL] Execution phase complete! Sold items: {sold_items_map}")        
        
    
    return sold_items_map

async def mark_order_status_as_sold(order_id: str, store_id: str):
    # ✅ Updated to also set quotation_status to completed
    result = await db.SalesOrders.update_one(
        {
            "order_id": order_id,
            "store_id": store_id,
            "order_status": "0"
        },
        {
            "$set": {
                "order_status": "1",
                "quotation_status": "completed"
            }
        }
    )
    return result.modified_count

async def mark_order_as_sold(order_id: str, store_id: str, quantity: int = None, price: float = None, tax: float = None, payment_status: str = "Paid", background_tasks: BackgroundTasks = None, created_by: dict = None):
    order = await fetch_order_and_validate(order_id, store_id)
    
    # ✅ If quantity is provided from popup, update the order's quantity before processing
    if quantity is not None:
        for product in order.get("products", []):
            product["order_quantity"] = quantity
    
    sold_items_map = await update_inventory_for_order(order, store_id, tax=tax)
    
    # Update the order products with item_ids information
    updated_products = []
    affected_product_ids = []  # Track products that need inventory sync
    
    for product in order.get("products", []):
        product_id = product.get("product_id")
        product_copy = product.copy()
        
        # Track products for inventory sync
        if product_id:
            affected_product_ids.append(product_id)
        
        # Update with edited values if provided
        if quantity is not None:
            product_copy["order_quantity"] = quantity
        if price is not None:
            product_copy["unit_price"] = price
        if tax is not None:
            product_copy["tax"] = tax
        
        # Add item_ids array (handles both single and multiple items)
        if product_id in sold_items_map:
            item_ids = sold_items_map[product_id]
            if len(item_ids) > 0:
                product_copy["item_ids"] = item_ids  # Always store as array
        
        updated_products.append(product_copy)
    
    # Update the order with item information
    # ✅ IMPORTANT: order_status is ALWAYS "1" for sold orders, regardless of payment status
    # payment_status tracks whether payment was received ("Paid") or deferred ("Pay Later")
    update_fields = {
        "order_status": "1",  # Always "1" for sold orders
        "payment_status": payment_status,  # Track payment separately
        "products": updated_products,
        "quotation_status": "completed",
        "sold_at": datetime.now(timezone.utc),  # ✅ FIXED
        "updated_at": datetime.now(timezone.utc)
    }

    if created_by:
        update_fields["created_by"] = created_by

    await db.SalesOrders.update_one(
        {
            "order_id": order_id,
            "store_id": store_id,
            "order_status": "0"
        },
        {
            "$set": update_fields
        }
    )
    
    # ✅ EVENT-DRIVEN: Sync inventory for all affected products (with background tasks)
    for product_id in affected_product_ids:
        await sync_inventory_on_change(product_id, store_id, background_tasks)
    
    # ✅ AUTO-SYNC: Add this sold order to ProfitOrders collection (real-time)
    try:
        from app.services import admin_profitOrders_service
        result = await admin_profitOrders_service.sync_single_order_to_profit(order_id, store_id)
        print(f"✅ Profit sync: {result['synced_count']} new, {result['updated_count']} updated for order {order_id}")
    except Exception as e:
        # Log error but don't fail the main operation
        print(f"⚠️ Warning: Failed to sync profit for order {order_id}: {str(e)}")
    
    # ✅ AUTO-SYNC: Add this sold order to CustomerHistory collection
    try:
        from app.services import customer_services
        sync_result = await customer_services.sync_order_to_customer_history(order_id, store_id)
        print(f"✅ Customer history sync: order {order_id} synced successfully")
    except Exception as e:
        # Log error but don't fail the main operation
        print(f"⚠️ Warning: Failed to sync customer history for order {order_id}: {str(e)}")
    
    return 1  # Return success count


async def mark_pending_order_as_paid(order_id: str, store_id: str):
    """
    Update payment status from 'Pay Later' to 'Paid' for a sold order.
    Also updates sold_at timestamp to current time.
    """
    # Find the order
    order = await db.SalesOrders.find_one({
        "order_id": order_id,
        "store_id": store_id,
        "order_status": "1"  # Only sold orders
    })
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found or not sold yet")
    
    # Update payment status to Paid
    result = await db.SalesOrders.update_one(
        {
            "order_id": order_id,
            "store_id": store_id,
            "order_status": "1"
        },
        {
            "$set": {
                "payment_status": "Paid",
                "sold_at": datetime.now(timezone.utc),  # Update payment date
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )
    
    # ✅ Sync to CustomerHistory collection
    try:
        from app.services import customer_services
        await customer_services.sync_order_to_customer_history(order_id, store_id)
        print(f"✅ Customer history synced for order {order_id}")
    except Exception as e:
        print(f"⚠️ Warning: Failed to sync customer history: {str(e)}")
    
    return result.modified_count


async def delete_order_by_id(order_id: str, store_id: str) -> int:
    result = await db.SalesOrders.delete_one({
        "order_id": order_id,
        "store_id": store_id
    })
    return result.deleted_count


# 🔹 Helper to find updated quantity
def get_new_quantity_for_product(product_id: str, updated_products: list, default_quantity: int) -> int:
    for p in updated_products:
        if p.get("product_id") == product_id:
            # Handle both 'quantity' and 'order_quantity' keys
            return p.get("order_quantity") or p.get("quantity", default_quantity)
    return default_quantity

# 🔹 Helper to rebuild products list and compute subtotal
async def rebuild_products_list(original_products: list, updated_products_input: list, store_id: str):
    updated_products = []
    subtotal = 0.0

    for prod in original_products:
        product_id = prod.get("product_id")
        default_quantity = prod.get("order_quantity", 0)
        
        # Find if this product has updates in the input
        updated_product = None
        for p in updated_products_input:
            if p.get("product_id") == product_id:
                updated_product = p
                break
        
        # Get quantity, price, and tax from updated data or use defaults
        new_quantity = updated_product.get("order_quantity") or updated_product.get("quantity") if updated_product else default_quantity
        new_unit_price = updated_product.get("unit_price") if updated_product else prod.get("unit_price")
        new_tax = updated_product.get("tax") if updated_product else prod.get("tax")

        inventory_data = await fetch_inventory_details(product_id, store_id)
        
        # ✅ Use updated values if provided, otherwise use inventory defaults
        final_unit_price = new_unit_price if new_unit_price is not None else inventory_data["unit_price"]
        final_tax = new_tax if new_tax is not None else inventory_data["product_tax"]
        
        # ✅ Determine selling_price: if price was updated, use it; otherwise use existing selling_price or unit_price
        # This ensures that price changes during sell flow are preserved in selling_price field
        if updated_product and updated_product.get("unit_price") is not None:
            # Price was explicitly updated in sell flow - use it as selling_price
            final_selling_price = updated_product.get("unit_price")
        else:
            # No price update - preserve existing selling_price or fall back to unit_price
            final_selling_price = prod.get("selling_price") or final_unit_price

        product_detail, total_with_tax = build_product_detail(
            inventory_item=inventory_data["inventory_item"],
            product_id=product_id,
            unit_price=inventory_data["unit_price"],  # ✅ Always use original inventory price as unit_price
            product_tax=final_tax,
            order_quantity=new_quantity,
            inventory_quantity=inventory_data["inventory_quantity"],
            consumer_return_conditions=inventory_data["consumer_return_conditions"],
            selling_price=final_selling_price,  # ✅ Use the updated price as selling_price (what customer pays)
            seller_return_conditions=inventory_data["seller_return_conditions"],
            is_seller_returnable=inventory_data["is_seller_returnable"],
            is_consumer_returnable=inventory_data["is_consumer_returnable"]
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
    # Preserve currency from updated_data, fallback to existing order currency or INR
    if "currency" not in updated_data:
        updated_data["currency"] = order.get("currency", "INR")
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
            product["status"] = "Stock-in" if available_items_count > 1 else "Stock-out"
            
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
        {"$set": {
            "sent_to_procurement": 1,
            "status": "pending"  # Set default status as pending
        }}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Return order not found for this store")

    return {"message": f"Return order {return_id} marked as sent to procurement", "status": "pending"}

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
        # Trim whitespace and normalize spaces - use flexible regex without anchors
        product_name = product_name.strip()
        # Escape special regex characters and allow flexible matching
        import re
        escaped_name = re.escape(product_name)
        # Use flexible matching - case insensitive, allows extra whitespace
        query["product_name"] = {"$regex": escaped_name, "$options": "i"}

    product = await db.Inventory.find_one(query, {"_id": 0})

    if not product:
        raise HTTPException(status_code=404, detail=f"Product not found for this store. Searched for: '{product_name}' in store: '{store_id}'")

    # ✅ Get available items count from ProductItems
    available_items_count = await db.ProductItems.count_documents({
        "product_id": product.get("product_id"),
        "store_id": store_id,
        "status": "available"
    })

    # ✅ Calculate average selling_price from ProductItems
    items_cursor = db.ProductItems.find({
        "product_id": product.get("product_id"),
        "store_id": store_id,
        "status": "available"
    }, {"selling_price": 1, "_id": 0})
    
    items = await items_cursor.to_list(length=None)
    
    # Calculate average selling price - handle string values and zeros
    average_price = 0.0
    if items:
        total_price = 0.0
        valid_count = 0
        
        for item in items:
            try:
                price_value = item.get("selling_price", 0)
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
    
    # If still 0, try to get from product's average_selling_price
    if average_price == 0:
        try:
            inv_price = product.get("average_selling_price", 0)
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
    # ✅ Allow fetching orders regardless of status (pending or sold)
    order = await db.SalesOrders.find_one(
         {
            "order_id": order_id,
            "store_id": store_id
        },
        {"_id": 0}
    )

    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    updated_products = []

    for product in order.get("products", []):
        product_id = product.get("product_id")
        ordered_quantity = int(product.get("order_quantity", 0))
        item_ids = product.get("item_ids", [])

        # ✅ Fetch vendor_tax from Inventory collection
        inventory_product = await db.Inventory.find_one({
            "product_id": product_id,
            "store_id": store_id
        }, {"vendor_tax": 1, "_id": 0})
        
        if inventory_product and inventory_product.get("vendor_tax"):
            product["vendor_tax"] = inventory_product.get("vendor_tax")

        # ✅ Count available items from ProductItems collection
        available_items_count = await db.ProductItems.count_documents({
            "product_id": product_id,
            "store_id": store_id,
            "status": "available"
        })

        # Determine product status based on available items
        # Business rule: if available quantity is 1 (or 0), mark Stock-out
        product_status = "Stock-out" if available_items_count <= 1 else "Stock-in"
        product["product_status"] = product_status
        
        # ✅ Calculate average selling_price from available items using helper function
        avg_selling_price = await calculate_average_selling_price_from_items(product_id, store_id)
        product["unit_price"] = avg_selling_price  # Set to 0 if no selling_price exists
        
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
    
    # ✅ Recalculate total_order_price dynamically
    total_order_price = 0.0
    for product in updated_products:
        unit_price = float(product.get("unit_price", 0))
        tax = float(product.get("tax", 0))
        quantity = int(product.get("order_quantity", 0))
        product_total = calculate_product_total_price(unit_price, tax, quantity)
        total_order_price += product_total
    
    order["total_order_price"] = round(total_order_price, 2)
    
    # ✅ Include currency field
    order["currency"] = order.get("currency", "INR")
    
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
        
        # ✅ Calculate average selling_price from available items using helper function
        avg_selling_price = await calculate_average_selling_price_from_items(product_id, store_id)
        product["unit_price"] = avg_selling_price  # Set to 0 if no selling_price exists
        
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
                        "selling_price": item.get("selling_price"),  # ✅ Selling price captured at time of sale
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
    
    # ✅ Recalculate total_order_price dynamically using selling_price
    total_order_price = 0.0
    for product in updated_products:
        selling_price = float(product.get("selling_price", 0))
        tax = float(product.get("tax", 0))
        quantity = int(product.get("order_quantity", 0))
        product_total = calculate_product_total_price(selling_price, tax, quantity)
        total_order_price += product_total
    
    # ✅ Add shipping charges to total if present
    shipping_charges = float(order.get("shipping_charges", 0))
    order["total_order_price"] = round(total_order_price + shipping_charges, 2)
    
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


async def generate_sold_order_pdf_service(order_id: str, store_id: str):
    """
    Service function to generate PDF for a sold order
    
    Args:
        order_id: The sold order ID
        store_id: The store ID
        
    Returns:
        FileResponse: PDF file download response
    """
    # Fetch the sold order using existing function
    order_data = await get_sold_order_by_id(order_id, store_id)
    
    if not order_data:
        raise HTTPException(status_code=404, detail="Sold order not found")
    
    # Fetch store name from Stores collection
    print(f"🔍 Fetching store name for store_id: {store_id}")
    store = await stores_collection.find_one({"store_id": store_id}, {"_id": 0, "store_name": 1})
    print(f"🔍 Store found: {store}")
    if store and "store_name" in store:
        order_data["store_name"] = store["store_name"]
        print(f"✅ Added store_name to order_data: {store['store_name']}")
    else:
        print(f"❌ Store name not found for store_id: {store_id}")
        order_data["store_name"] = "-"
    
    print(f"🔍 Order data before PDF generation: store_name = {order_data.get('store_name', 'NOT SET')}")
    
    # Ensure status field exists
    if 'status' not in order_data:
        order_data['status'] = 'Sold'
    
    # Generate PDF using temporary file (no permanent storage)
    try:
        pdf_path = generate_sold_order_pdf(order_data, output_dir=None)
        
        # Return as downloadable file with automatic cleanup
        return FileResponse(
            path=pdf_path,
            media_type='application/pdf',
            filename=f"SoldOrder_{order_id}.pdf",
            background=None  # File will be cleaned up after response
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")


async def generate_received_order_pdf_service(order_id: str, store_id: str):
    """
    Service function to generate PDF for a received order (quotation)
    
    Args:
        order_id: The received order ID
        store_id: The store ID
        
    Returns:
        FileResponse: PDF file download response
    """
    # Fetch the received order from SalesOrders collection
    order = await sales_orders_collection.find_one({
        "order_id": order_id,
        "store_id": store_id
    }, {"_id": 0})
    
    if not order:
        raise HTTPException(status_code=404, detail="Received order not found")
    
    # Fetch store name from Stores collection
    store = await stores_collection.find_one({"store_id": store_id}, {"_id": 0, "store_name": 1})
    if store and "store_name" in store:
        order["store_name"] = store["store_name"]
    else:
        order["store_name"] = "-"
    
    # Generate PDF using temporary file
    try:
        pdf_path = generate_received_order_pdf(order, output_dir=None)
        
        # Return as downloadable file with automatic cleanup
        return FileResponse(
            path=pdf_path,
            media_type='application/pdf',
            filename=f"Quotation_{order_id}.pdf",
            background=None
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")

