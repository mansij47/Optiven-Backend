# services/procurement_validation_services.py
from fastapi import HTTPException
from bson import ObjectId
from app.db import db
from app.models.procurement_models import PurchaseOrderValidationInput, PurchaseOrderValidationRequest, PurchaseOrderSubmitRequest
import uuid
from datetime import datetime


async def update_sales_orders_on_inventory_change(product_name: str, product_id: str, store_id: str, unit_price: float, tax: float):
    """
    Update sales orders when inventory is added/updated:
    - Populate product_id (was empty for preorders)
    - Change type from 'preorder' to 'order'
    - Change status from 'Preorder' to 'Stock-in'
    - Update unit_price and tax with actual values passed from inventory
    - Recalculate total_order_price
    Match by product_name (case-insensitive) since preorders have empty product_id
    """
    # Use the unit_price and tax passed directly (from ProductItems or PurchaseOrder)
    inventory_unit_price = float(unit_price)
    inventory_tax = float(tax)
    
    # Find all preorder sales orders with this product (case-insensitive match)
    # Also check for orders with unit_price = 0 and tax = 0 (preorder indicators)
    preorder_orders = db.SalesOrders.find({
        "store_id": store_id,
        "type": "preorder",
        "products": {
            "$elemMatch": {
                "product_name": {"$regex": f"^{product_name}$", "$options": "i"},
                "unit_price": 0,
                "tax": 0
            }
        }
    })
    
    async for order in preorder_orders:
        # Update product details for matching products in the order
        updated_products = []
        new_total_price = 0.0
        
        for product in order.get("products", []):
            if product.get("product_name", "").lower() == product_name.lower():
                # ✅ Update all fields for the matching product
                product["product_id"] = product_id  # Populate the product_id from inventory
                product["product_status"] = "Stock-in"
                product["unit_price"] = inventory_unit_price  # ✅ Update with real unit price
                product["tax"] = inventory_tax  # ✅ Update with real tax
                
                # ✅ Calculate this product's contribution to total
                order_quantity = int(product.get("order_quantity", 0))
                line_total = (inventory_unit_price * order_quantity)
                tax_amount = (inventory_tax * order_quantity)
                new_total_price += (line_total + tax_amount)
            else:
                # For other products, calculate their contribution to total
                order_quantity = int(product.get("order_quantity", 0))
                unit_price = float(product.get("unit_price", 0))
                tax = float(product.get("tax", 0))
                line_total = (unit_price * order_quantity)
                tax_amount = (tax * order_quantity)
                new_total_price += (line_total + tax_amount)
            
            updated_products.append(product)
        
        # ✅ Update the order with all changes including recalculated total
        await db.SalesOrders.update_one(
            {"_id": order["_id"]},
            {
                "$set": {
                    "type": "order",
                    "status": "Stock-in",
                    "products": updated_products,
                    "total_order_price": round(new_total_price, 2),  # ✅ Update total price
                    "updated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                }
            }
        )
    
    print(f"[INFO] Updated preorder sales orders for product: {product_name}, assigned product_id: {product_id}, unit_price: {inventory_unit_price}, tax: {inventory_tax}")


async def validate_purchase_order_preview(
    data: PurchaseOrderValidationInput, store_id: str, org_id: str
):
    """
    Frontend se sirf 4-5 fields aati hain.
    Baaki details DB se order_id ke base par fetch hoke merge hoti hain.
    """

  
    order = await db["PurchaseOrders"].find_one({"order_id": data.order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Purchase order not found.")

    # 🔹 Merge karo (DB details + frontend input)
    merged_data = {
        "order_id": str(order["_id"]),
        "contract_id": order.get("contract_id"),
        "delivery_date": order.get("delivery_date"),
        "vendor_name": order.get("vendor_name"),
        "expected_quantity": data.expected_quantity,
        "received_quantity": data.received_quantity,
        "unit": order.get("unit"),
        "is_product_damaged": data.is_product_damaged,
        "returnable": order.get("returnable"),
        "return_conditions": order.get("return_conditions", []),
        "is_consumer_returnable": order.get("is_consumer_returnable", False),
        "consumer_return_conditions": order.get("consumer_return_conditions", []),
        "unit_price": order.get("unit_price"),
        "category": order.get("category"),
        "product_name": order.get("product_name"),
        "sub_category": order.get("sub_category"),
        "has_warranty": order.get("has_warranty", False) or (order.get("warranty_tenure", 0) > 0),
        "warranty_tenure": order.get("warranty_tenure", 0),
        "warranty_unit": order.get("warranty_unit", "months"),
        "tax": order.get("tax", 0),
        "product_id": order.get("product_id"),
        "selected_action": data.selected_action,
    }

    # Pydantic model banake validate karo
    full_request = PurchaseOrderValidationRequest(**merged_data)

    # 👇 Tera pura decision logic call
    return await _run_validation_logic(full_request, store_id, org_id)


async def _run_validation_logic(data: PurchaseOrderValidationRequest, store_id: str, org_id: str):
    """
    Yeh wahi tera pura decision logic hai jo tu already likh chuka hai
    (damaged / returnable / inventory / loss logic).
    """

    # ✅ Case 1: Agar product damaged nahi hai
    if not data.is_product_damaged:
        if data.selected_action == "ReturnToVendor":
            if data.returnable:
                return {
                    "message": " Product undamaged hai par returnable true hai, ReturnToVendor me jayega.",
                    "collection": "ReturnToVendor",
                    "payload": data.dict(),
                    "store_id": store_id,
                    "org_id": org_id
                }
            else:
                raise HTTPException(
                    status_code=400,
                    detail="If the product is Undamaged and Not Returnable, so it cannot be sent to the Vendor."
                )

        elif data.selected_action in [None, "Inventory"]:
            return {
                "message": " Product undamaged hai, Inventory me jayega.",
                "collection": "Inventory",
                "payload": data.dict(),
                "store_id": store_id,
                "org_id": org_id
            }

        else:
            raise HTTPException(
                status_code=400,
                detail="Product is not damaged, so it cannot be sent to LossOrders."
            )

    # ✅ Case 2: Damaged + returnable
    if data.is_product_damaged and data.returnable:
        if data.selected_action in [None, "ReturnToVendor"]:
            return {
                "message": " Product damaged hai aur returnable true hai, ReturnToVendor me jayega.",
                "collection": "ReturnToVendor",
                "payload": data.dict(),
                "store_id": store_id,
                "org_id": org_id
            }
        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid selected action for Damaged product and Returnable product"
            )

    # ✅ Case 3: Damaged + not returnable
    if data.is_product_damaged and not data.returnable:
        if data.selected_action in [None, "LossOrders"]:
            return {
                "message": " Product damaged hai aur returnable false hai, LossOrders me jayega.",
                "collection": "LossOrders",
                "payload": data.dict(),
                "store_id": store_id,
                "org_id": org_id
            }
        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid selected action for Damaged product and Not Returnable product."
            )

    raise HTTPException(status_code=400, detail="Invalid payload / condition match nahi hui.")

def generate_id(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:6].upper()}"


async def submit_purchase_order(data: PurchaseOrderSubmitRequest, store_id: str, org_id: str):
    base_order = await db["PurchaseOrders"].find_one({"order_id": data.order_id})
    if not base_order:
        raise HTTPException(status_code=404, detail="Order not found")

    # --- INVENTORY CASE (includes semi-damaged items) ---
    if data.selected_action == "Inventory" or data.is_semi_damaged:
        # ✅ Use admin Product model structure
        from app.models.admin_model import Product
        from app.utils.raise_order import _next_id
        
        # ✅ Check if product already exists in inventory (case-insensitive)
        product_name = base_order.get("product_name")
        existing_product = await db.Inventory.find_one({
            "store_id": store_id,
            "product_name": {"$regex": f"^{product_name}$", "$options": "i"}
        })
        
        if existing_product:
            # Product exists - UPDATE it
            product_id = existing_product.get("product_id")
            
            # Calculate new quantity (existing + received)
            existing_quantity = existing_product.get("quantity", 0)
            new_quantity = existing_quantity + data.received_quantity
            
            # Update existing product (average_price will be calculated after items are added)
            await db.Inventory.update_one(
                {"product_id": product_id, "store_id": store_id},
                {
                    "$set": {
                        "quantity": new_quantity,
                        "min_stock": data.min_quantity or existing_product.get("min_stock", 4),
                        "status": "Stock-in",
                        "type": "order",  # ✅ Set to 'order' when validated and added to inventory
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            # Will update preorder sales orders after ProductItems are created
        else:
            # Product doesn't exist - CREATE new one
            product_id = await _next_id(db.Inventory, "product_id", "PROD", store_id)
            
            # Create Product using admin model (clean structure) 
            product_dict = {
                "org_id": org_id,
                "store_id": store_id,
                "product_id": product_id,
                "product_name": base_order.get("product_name"),
                "unit": base_order.get("unit"),
                "quantity": data.received_quantity,
                "average_price": 0.0,  # Will be calculated after items are added
                "category": base_order.get("category"),
                "sub_category": base_order.get("sub_category", ""),
                "tags": [],
                "tax": float(base_order.get("tax", 0)),
                "min_stock": data.min_quantity or 4,
                "status": "Stock-in",
                "type": "order",  # ✅ Set to 'order' when validated and added to inventory
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            # Insert product into Inventory
            await db.Inventory.insert_one(product_dict)
            
            # Will update preorder sales orders after ProductItems are created
        
        # ✅ Create individual ProductItems with user-edited details from frontend
        items_created = []
        damaged_items_for_loss = []
        damaged_items_for_return = []
        good_items_count = 0
        
        # Use items from frontend if provided, otherwise create default items
        items_to_create = data.items if data.items else []
        
        # If no items provided from frontend, create default items
        if not items_to_create:
            base_unit_price = str(base_order.get("unit_price", "0"))
            
            items_to_create = [
                {
                    "item_name": f"{base_order.get('product_name')}",
                    "serial_no": None,
                    "batch_number": None,
                    "unit_price": base_unit_price,
                    "is_damaged": False
                }
                for i in range(data.received_quantity)
            ]
        
        for i, item_detail in enumerate(items_to_create):
            # ✅ Check if item is damaged (for semi-damaged case)
            item_is_damaged = item_detail.get("is_damaged", False) if isinstance(item_detail, dict) else getattr(item_detail, "is_damaged", False)
            
            # ✅ Handle damaged items separately
            if data.is_semi_damaged and item_is_damaged:
                # Damaged item - check if returnable
                item_is_seller_returnable = item_detail.get("is_seller_returnable") if isinstance(item_detail, dict) else getattr(item_detail, "is_seller_returnable", base_order.get("returnable", False))
                
                if item_is_seller_returnable:
                    # Add to return to vendor list
                    damaged_items_for_return.append(item_detail)
                else:
                    # Add to loss orders list
                    damaged_items_for_loss.append(item_detail)
                continue  # Skip adding to inventory
            
            # ✅ Good items go to inventory
            item_id = await _next_id(db.ProductItems, "item_id", "ITEM", store_id)
            
            # ✅ Extract validation fields from item if available, else fallback to product-level
            if isinstance(item_detail, dict):
                # Dictionary format
                item_is_consumer_returnable = item_detail.get("is_consumer_returnable", data.is_consumer_returnable)
                item_consumer_return_conditions = item_detail.get("consumer_return_conditions", data.consumer_return_conditions or [])
                item_is_seller_returnable = item_detail.get("is_seller_returnable", base_order.get("returnable", False))
                item_seller_return_conditions = item_detail.get("seller_return_conditions", base_order.get("return_conditions", []))
            else:
                # Object format (Pydantic model)
                item_is_consumer_returnable = getattr(item_detail, "is_consumer_returnable", data.is_consumer_returnable)
                item_consumer_return_conditions = getattr(item_detail, "consumer_return_conditions", data.consumer_return_conditions or [])
                item_is_seller_returnable = getattr(item_detail, "is_seller_returnable", base_order.get("returnable", False))
                item_seller_return_conditions = getattr(item_detail, "seller_return_conditions", base_order.get("return_conditions", []))
            
            # Get unit_price for the item
            unit_price_value = item_detail.get("unit_price") if isinstance(item_detail, dict) else item_detail.unit_price
            
            # ✅ Calculate selling_price at item level: unit_price + 50
            try:
                unit_price_float = float(unit_price_value) if unit_price_value else 0.0
                item_selling_price = round(unit_price_float + 50, 2)
            except (ValueError, TypeError):
                item_selling_price = 50.0  # Default if conversion fails
            
            item_data = {
                "org_id": org_id,
                "store_id": store_id,
                "item_id": item_id,
                "product_id": product_id,
                "item_name": item_detail.get("item_name") if isinstance(item_detail, dict) else item_detail.item_name,
                "unit_price": unit_price_value,
                "selling_price": item_selling_price,  # Set at item level: unit_price + 50
                "vendor_id": base_order.get("vendor_id"),
                "vendor_name": base_order.get("vendor_name"),
                "serial_no": item_detail.get("serial_no") if isinstance(item_detail, dict) else item_detail.serial_no,
                "batch_number": item_detail.get("batch_number") if isinstance(item_detail, dict) else item_detail.batch_number,
                # ✅ NOW using item-level validation fields!
                "is_consumer_returnable": item_is_consumer_returnable,
                "consumer_return_conditions": item_consumer_return_conditions,
                "is_seller_returnable": item_is_seller_returnable,
                "seller_return_conditions": item_seller_return_conditions,
                "has_warranty": base_order.get("has_warranty", False) or (base_order.get("warranty_tenure", 0) > 0),
                "warranty_tenure": base_order.get("warranty_tenure", 0),
                "warranty_unit": base_order.get("warranty_unit", "months"),
                "status": "available",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            await db.ProductItems.insert_one(item_data)
            items_created.append(item_id)
            good_items_count += 1
        
        # ✅ Handle damaged items for Loss Orders - Create ProductItems with item_ids
        damaged_loss_item_ids = []
        if damaged_items_for_loss:
            for item_detail in damaged_items_for_loss:
                # Create ProductItem for damaged item going to loss
                loss_item_id = await _next_id(db.ProductItems, "item_id", "ITEM", store_id)
                
                # Extract item details
                if isinstance(item_detail, dict):
                    item_name = item_detail.get("item_name")
                    serial_no = item_detail.get("serial_no")
                    batch_number = item_detail.get("batch_number")
                    unit_price = item_detail.get("unit_price")
                    is_consumer_returnable = item_detail.get("is_consumer_returnable", data.is_consumer_returnable)
                    consumer_return_conditions = item_detail.get("consumer_return_conditions", data.consumer_return_conditions or [])
                    is_seller_returnable = item_detail.get("is_seller_returnable", False)
                    seller_return_conditions = item_detail.get("seller_return_conditions", [])
                else:
                    item_name = getattr(item_detail, "item_name", None)
                    serial_no = getattr(item_detail, "serial_no", None)
                    batch_number = getattr(item_detail, "batch_number", None)
                    unit_price = getattr(item_detail, "unit_price", None)
                    is_consumer_returnable = getattr(item_detail, "is_consumer_returnable", data.is_consumer_returnable)
                    consumer_return_conditions = getattr(item_detail, "consumer_return_conditions", data.consumer_return_conditions or [])
                    is_seller_returnable = getattr(item_detail, "is_seller_returnable", False)
                    seller_return_conditions = getattr(item_detail, "seller_return_conditions", [])
                
                # Create ProductItem with full vendor and warranty info
                loss_item_data = {
                    "org_id": org_id,
                    "store_id": store_id,
                    "item_id": loss_item_id,
                    "product_id": product_id,
                    "item_name": item_name,
                    "unit_price": unit_price,
                    "selling_price": None,  # Damaged items don't have selling price
                    "vendor_id": base_order.get("vendor_id"),
                    "vendor_name": base_order.get("vendor_name"),
                    "contract_id": base_order.get("contract_id"),
                    "serial_no": serial_no,
                    "batch_number": batch_number,
                    "is_consumer_returnable": is_consumer_returnable,
                    "consumer_return_conditions": consumer_return_conditions,
                    "is_seller_returnable": is_seller_returnable,
                    "seller_return_conditions": seller_return_conditions,
                    "has_warranty": base_order.get("has_warranty", False) or (base_order.get("warranty_tenure", 0) > 0),
                    "warranty_tenure": base_order.get("warranty_tenure", 0),
                    "warranty_unit": base_order.get("warranty_unit", "months"),
                    "status": "damaged",  # Mark as damaged
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
                
                await db.ProductItems.insert_one(loss_item_data)
                damaged_loss_item_ids.append(loss_item_id)
            
            # Create LossOrders entry with item_ids
            loss_doc = {
                "product_id": product_id,
                "org_id": org_id,
                "store_id": store_id,
                "product_name": base_order.get("product_name"),
                "category": base_order.get("category"),
                "date_reported": str(datetime.now().date()),
                "quantity_lost": len(damaged_items_for_loss),
                "damaged_item_ids": damaged_loss_item_ids,  # Track item IDs
                "unit": base_order.get("unit"),
                "unit_price": str(base_order.get("unit_price", "0")),
                "reason": "Damaged & Not Returnable (Semi-Damaged Batch)",
                "vendor_id": base_order.get("vendor_id"),
                "vendor_name": base_order.get("vendor_name"),
                "contract_id": base_order.get("contract_id"),
            }
            await db["LossOrders"].insert_one(loss_doc)
        
        # ✅ Handle damaged items for Return to Vendor - Create ProductItems with item_ids
        damaged_return_item_ids = []
        if damaged_items_for_return:
            for item_detail in damaged_items_for_return:
                # Create ProductItem for damaged item going to vendor
                return_item_id = await _next_id(db.ProductItems, "item_id", "ITEM", store_id)
                
                # Extract item details
                if isinstance(item_detail, dict):
                    item_name = item_detail.get("item_name")
                    serial_no = item_detail.get("serial_no")
                    batch_number = item_detail.get("batch_number")
                    unit_price = item_detail.get("unit_price")
                    is_consumer_returnable = item_detail.get("is_consumer_returnable", data.is_consumer_returnable)
                    consumer_return_conditions = item_detail.get("consumer_return_conditions", data.consumer_return_conditions or [])
                    is_seller_returnable = item_detail.get("is_seller_returnable", base_order.get("returnable", False))
                    seller_return_conditions = item_detail.get("seller_return_conditions", base_order.get("return_conditions", []))
                else:
                    item_name = getattr(item_detail, "item_name", None)
                    serial_no = getattr(item_detail, "serial_no", None)
                    batch_number = getattr(item_detail, "batch_number", None)
                    unit_price = getattr(item_detail, "unit_price", None)
                    is_consumer_returnable = getattr(item_detail, "is_consumer_returnable", data.is_consumer_returnable)
                    consumer_return_conditions = getattr(item_detail, "consumer_return_conditions", data.consumer_return_conditions or [])
                    is_seller_returnable = getattr(item_detail, "is_seller_returnable", base_order.get("returnable", False))
                    seller_return_conditions = getattr(item_detail, "seller_return_conditions", base_order.get("return_conditions", []))
                
                # Create ProductItem with full vendor and warranty info
                return_item_data = {
                    "org_id": org_id,
                    "store_id": store_id,
                    "item_id": return_item_id,
                    "product_id": product_id,
                    "item_name": item_name,
                    "unit_price": unit_price,
                    "selling_price": None,  # Return items don't have selling price
                    "vendor_id": base_order.get("vendor_id"),
                    "vendor_name": base_order.get("vendor_name"),
                    "contract_id": base_order.get("contract_id"),
                    "serial_no": serial_no,
                    "batch_number": batch_number,
                    "is_consumer_returnable": is_consumer_returnable,
                    "consumer_return_conditions": consumer_return_conditions,
                    "is_seller_returnable": is_seller_returnable,
                    "seller_return_conditions": seller_return_conditions,
                    "has_warranty": base_order.get("has_warranty", False) or (base_order.get("warranty_tenure", 0) > 0),
                    "warranty_tenure": base_order.get("warranty_tenure", 0),
                    "warranty_unit": base_order.get("warranty_unit", "months"),
                    "status": "return_to_vendor",  # Mark for vendor return
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
                
                await db.ProductItems.insert_one(return_item_data)
                damaged_return_item_ids.append(return_item_id)
            
            # Create ReturnToVendor entry with item_ids and item details
            # Collect batch numbers and serial numbers from items
            batch_numbers = []
            serial_numbers = []
            for item_detail in damaged_items_for_return:
                if isinstance(item_detail, dict):
                    batch_no = item_detail.get("batch_number")
                    serial_no = item_detail.get("serial_no")
                else:
                    batch_no = getattr(item_detail, "batch_number", None)
                    serial_no = getattr(item_detail, "serial_no", None)
                
                if batch_no:
                    batch_numbers.append(batch_no)
                if serial_no:
                    serial_numbers.append(serial_no)
            
            return_doc = {
                "return_id": generate_id("RTV"),
                "order_id": data.order_id,
                "product_id": product_id,
                "vendor_id": base_order.get("vendor_id"),
                "vendor_name": base_order.get("vendor_name"),
                "product_name": base_order.get("product_name"),
                "delivery_date": base_order.get("delivery_date"),
                "status": "pending",  # Default status
                "return_amount": str(len(damaged_items_for_return) * float(base_order.get("unit_price", 0))),
                "original_quantity": data.expected_quantity,
                "return_quantity": len(damaged_items_for_return),
                "returnable_item_ids": damaged_return_item_ids,  # Track item IDs
                "batch_numbers": batch_numbers,  # Batch numbers from items
                "serial_numbers": serial_numbers,  # Serial numbers from items
                "unit": base_order.get("unit"),
                "contract_id": base_order.get("contract_id"),
                "purchase_date": str(datetime.now().date()),
                "product_condition": "Damaged (Semi-Damaged Batch)",
                "total_price": int(len(damaged_items_for_return) * float(base_order.get("unit_price", 0))),
                "unit_price": int(base_order.get("unit_price", 0)),
                "return_reason": "Damaged on Delivery",
                "store_id": store_id,
                "org_id": org_id,
            }
            await db["ReturnToVendor"].insert_one(return_doc)
        
        # ✅ Calculate and update average_price and average_selling_price at product level
        from app.services.admin_inventory_service import calculate_average_price, calculate_average_selling_price
        average_price = await calculate_average_price(product_id, store_id)
        
        # ✅ Calculate average_selling_price from all items' selling_price
        average_selling_price = await calculate_average_selling_price(product_id, store_id)
        
        await db.Inventory.update_one(
            {"product_id": product_id, "store_id": store_id},
            {"$set": {"average_price": average_price, "average_selling_price": average_selling_price, "updated_at": datetime.utcnow()}}
        )
        
        # ✅ NOW Update preorder sales orders with actual unit_price and tax from base_order
        await update_sales_orders_on_inventory_change(
            base_order.get("product_name"), 
            product_id, 
            store_id,
            float(base_order.get("unit_price", 0)),
            float(base_order.get("tax", 0))
        )
        
        # Get updated product quantity
        updated_product = await db.Inventory.find_one({"product_id": product_id, "store_id": store_id})
        total_quantity = updated_product.get("quantity", 0) if updated_product else 0
        
        # ✅ Check for low stock and send notification if needed
        from app.services.admin_inventory_service import check_and_notify_low_stock
        await check_and_notify_low_stock(product_id, store_id)
        
        # ✅ Detailed message for semi-damaged
        if data.is_semi_damaged:
            message_parts = []
            if good_items_count > 0:
                message_parts.append(f"{good_items_count} good items added to Inventory")
            if damaged_items_for_loss:
                message_parts.append(f"{len(damaged_items_for_loss)} damaged items sent to Loss Orders")
            if damaged_items_for_return:
                message_parts.append(f"{len(damaged_items_for_return)} damaged items sent to Return to Vendor")
            
            final_message = " | ".join(message_parts)
        else:
            final_message = f"{'Product updated' if existing_product else 'Product added'} in inventory with {data.received_quantity} new items (Total: {total_quantity})"
        
        final_doc = {
            "product_id": product_id,
            "message": final_message,
            "items_created": items_created,
            "damaged_loss_item_ids": damaged_loss_item_ids,
            "damaged_return_item_ids": damaged_return_item_ids,
            "total_quantity": total_quantity,
            "average_price": average_price,
            "good_items_count": good_items_count,
            "damaged_items_loss": len(damaged_items_for_loss),
            "damaged_items_return": len(damaged_items_for_return),
            "was_update": bool(existing_product)
        }
        target_collection = None  # We already inserted above

    # --- LOSS ORDERS CASE ---
    elif data.selected_action == "LossOrders":
        from app.utils.raise_order import _next_id
        
        # Create product in inventory first (for tracking)
        product_id = await _next_id(db.Inventory, "product_id", "PROD", store_id)
        
        # Create ProductItems for each damaged item
        damaged_loss_item_ids = []
        base_unit_price = str(base_order.get("unit_price", "0"))
        
        for i in range(data.received_quantity):
            loss_item_id = await _next_id(db.ProductItems, "item_id", "ITEM", store_id)
            
            # Create ProductItem with vendor and warranty info
            loss_item_data = {
                "org_id": org_id,
                "store_id": store_id,
                "item_id": loss_item_id,
                "product_id": product_id,
                "item_name": base_order.get("product_name"),
                "unit_price": base_unit_price,
                "selling_price": None,  # Damaged items don't have selling price
                "vendor_id": base_order.get("vendor_id"),
                "vendor_name": base_order.get("vendor_name"),
                "contract_id": base_order.get("contract_id"),
                "serial_no": None,
                "batch_number": None,
                "is_consumer_returnable": data.is_consumer_returnable if hasattr(data, 'is_consumer_returnable') else False,
                "consumer_return_conditions": data.consumer_return_conditions if hasattr(data, 'consumer_return_conditions') else [],
                "is_seller_returnable": base_order.get("returnable", False),
                "seller_return_conditions": base_order.get("return_conditions", []),
                "has_warranty": base_order.get("has_warranty", False) or (base_order.get("warranty_tenure", 0) > 0),
                "warranty_tenure": base_order.get("warranty_tenure", 0),
                "warranty_unit": base_order.get("warranty_unit", "months"),
                "status": "damaged",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            await db.ProductItems.insert_one(loss_item_data)
            damaged_loss_item_ids.append(loss_item_id)
        
        # Create LossOrders entry with item_ids
        final_doc = {
            "product_id": product_id,
            "org_id": org_id,
            "store_id": store_id,
            "product_name": base_order.get("product_name"),
            "category": base_order.get("category"),
            "date_reported": str(datetime.now().date()),
            "quantity_lost": data.received_quantity,
            "damaged_item_ids": damaged_loss_item_ids,
            "unit": base_order.get("unit"),
            "unit_price": str(base_order.get("unit_price", "0")),
            "reason": "Damaged & Not Returnable",
            "vendor_id": base_order.get("vendor_id"),
            "vendor_name": base_order.get("vendor_name"),
            "contract_id": base_order.get("contract_id"),
        }
        target_collection = db["LossOrders"]

    # --- RETURN TO VENDOR CASE ---
    elif data.selected_action == "ReturnToVendor":
        from app.utils.raise_order import _next_id
        
        # Create product in inventory first (for tracking)
        product_id = await _next_id(db.Inventory, "product_id", "PROD", store_id)
        
        # Create ProductItems for each damaged returnable item
        damaged_return_item_ids = []
        batch_numbers = []
        serial_numbers = []
        
        # Use items from frontend if provided, otherwise create default items
        items_to_create = data.items if data.items else []
        
        if not items_to_create:
            # Create default items if not provided
            items_to_create = [{"batch_number": None, "serial_no": None} for _ in range(data.received_quantity)]
        
        for i, item_detail in enumerate(items_to_create):
            return_item_id = await _next_id(db.ProductItems, "item_id", "ITEM", store_id)
            
            # Extract batch and serial from item
            if isinstance(item_detail, dict):
                batch_no = item_detail.get("batch_number")
                serial_no = item_detail.get("serial_no")
                unit_price = item_detail.get("unit_price", str(base_order.get("unit_price", "0")))
            else:
                batch_no = getattr(item_detail, "batch_number", None)
                serial_no = getattr(item_detail, "serial_no", None)
                unit_price = getattr(item_detail, "unit_price", str(base_order.get("unit_price", "0")))
            
            # Collect batch and serial numbers
            if batch_no:
                batch_numbers.append(batch_no)
            if serial_no:
                serial_numbers.append(serial_no)
            
            # Create ProductItem with vendor and warranty info
            return_item_data = {
                "org_id": org_id,
                "store_id": store_id,
                "item_id": return_item_id,
                "product_id": product_id,
                "item_name": base_order.get("product_name"),
                "unit_price": unit_price,
                "selling_price": None,  # Return items don't have selling price
                "vendor_id": base_order.get("vendor_id"),
                "vendor_name": base_order.get("vendor_name"),
                "contract_id": base_order.get("contract_id"),
                "serial_no": serial_no,
                "batch_number": batch_no,
                "is_consumer_returnable": data.is_consumer_returnable if hasattr(data, 'is_consumer_returnable') else False,
                "consumer_return_conditions": data.consumer_return_conditions if hasattr(data, 'consumer_return_conditions') else [],
                "is_seller_returnable": base_order.get("returnable", False),
                "seller_return_conditions": base_order.get("return_conditions", []),
                "has_warranty": base_order.get("has_warranty", False) or (base_order.get("warranty_tenure", 0) > 0),
                "warranty_tenure": base_order.get("warranty_tenure", 0),
                "warranty_unit": base_order.get("warranty_unit", "months"),
                "status": "return_to_vendor",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            await db.ProductItems.insert_one(return_item_data)
            damaged_return_item_ids.append(return_item_id)
        
        # Create ReturnToVendor entry with item_ids and item details
        final_doc = {
            "return_id": generate_id("RTV"),
            "order_id": data.order_id,
            "product_id": product_id,
            "vendor_id": base_order.get("vendor_id"),
            "vendor_name": base_order.get("vendor_name"),
            "product_name": base_order.get("product_name"),
            "delivery_date": base_order.get("delivery_date"),
            "status": "pending",  # Default status
            "return_amount": str(data.received_quantity * float(base_order.get("unit_price", 0))),
            "original_quantity": data.expected_quantity,
            "return_quantity": data.received_quantity,
            "returnable_item_ids": damaged_return_item_ids,
            "batch_numbers": batch_numbers,  # Batch numbers from items
            "serial_numbers": serial_numbers,  # Serial numbers from items
            "unit": base_order.get("unit"),
            "contract_id": base_order.get("contract_id"),
            "purchase_date": str(datetime.now().date()),
            "product_condition": "Damaged",
            "total_price": int(data.received_quantity * float(base_order.get("unit_price", 0))),
            "unit_price": int(base_order.get("unit_price", 0)),
            "return_reason": "Damaged on Delivery",
            "store_id": store_id,
            "org_id": org_id,
        }
        target_collection = db["ReturnToVendor"]

    else:
        raise HTTPException(status_code=400, detail="Invalid selected_action")

    # Insert document into target collection (only for Loss and Return to Vendor)
    if target_collection is not None:
        result = await target_collection.insert_one(final_doc)
        final_doc["_id"] = str(result.inserted_id)

    # --- Update PurchaseOrder validation_status to "completed" ---
    await db["PurchaseOrders"].update_one(
        {"order_id": data.order_id},
        {"$set": {"validation_status": "Completed", "last_updated": str(datetime.now())}}
    )

    return final_doc
