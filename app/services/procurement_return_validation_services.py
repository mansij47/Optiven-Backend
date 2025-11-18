from fastapi import HTTPException
from datetime import datetime
from app.db import db
from app.models.procurement_models import ReturnValidationRequest
from app.utils.raise_order import _next_id
from app.services.admin_inventory_service import handle_customer_return

# MongoDB collections
return_orders_collection = db["ReturnOrders"]
loss_orders_collection = db["LossOrders"]
return_to_vendor_collection = db["ReturnToVendor"]
inventory_collection = db["Inventory"]

# Validation of Return Orders (ReturnToVendor, Loss & Inventory)
async def validate_return_order(data: ReturnValidationRequest, store_id: str, org_id: str = None):
    # Find return order by return_id and store_id
    return_order = await return_orders_collection.find_one({
        "return_id": data.return_id,
        "store_id": store_id
    })

    if not return_order:
        raise HTTPException(status_code=404, detail="Return order not found for given return_id and store_id")

    # Access the first product (adjust if handling multiple in future)
    product = return_order["product"][0]

    reason = return_order.get("reason", "")
    is_seller_returnable = return_order.get("is_seller_returnable", False)
    order_id = return_order.get("order_id")
    
    # ✅ CHECK: Is this a customer return of sold items?
    # If order_id exists, check if items were sold from this order
    is_customer_return = False
    if order_id:
        sold_items_count = await db.ProductItems.count_documents({
            "product_id": product.get("product_id"),
            "store_id": store_id,
            "sold_order_id": order_id,
            "status": "sold"
        })
        is_customer_return = sold_items_count > 0
    
    # ✅ If this is a customer return, use item-based return logic
    if is_customer_return:
        result = await handle_customer_return(
            order_id=order_id,
            product_id=product.get("product_id"),
            return_quantity=product.get("return_quantity", 1),
            return_reason=reason,
            store_id=store_id,
            is_seller_returnable=is_seller_returnable
        )
        
        # Update status to completed after processing
        await return_orders_collection.update_one(
            {
                "return_id": data.return_id,
                "store_id": store_id
            },
            {
                "$set": {
                    "status": "completed",
                    "processed_at": datetime.now()
                }
            }
        )
        
        # ✅ Create detailed message based on destination
        destination = result.get("destination", "Unknown")
        product_name = product.get("product_name", "Product")
        return_qty = product.get("return_quantity", 1)
        
        if destination == "Inventory":
            message = f"Customer return processed: {return_qty} unit(s) of {product_name} returned to Inventory (Available for resale)"
        elif destination == "LossOrders":
            message = f" Customer return processed: {return_qty} unit(s) of {product_name} marked as Loss (Damaged & Not Returnable to Vendor)"
        elif destination == "ReturnToVendor":
            message = f" Customer return processed: {return_qty} unit(s) of {product_name} marked for Return to Vendor (Damaged & Returnable)"
        else:
            message = f"Customer return processed successfully with item tracking"
        
        return {
            "message": message,
            "details": result
        }

    # ✅ CASE 1: Product Damage & Seller Returnable → ReturnToVendor
    if reason == "Damage on arrival" and not is_seller_returnable:
        # Get vendor_id from the product's vendor_name
        vendor_name = product.get("vendor_name", "Unknown")
        vendor_id = None
        
        if vendor_name != "Unknown":
            # Try to find vendor_id from Vendors collection
            vendor = await db.Vendors.find_one(
                {"vendor_name": vendor_name},
                {"vendor_id": 1, "_id": 0}
            )
            if vendor:
                vendor_id = vendor.get("vendor_id")
        
        await return_to_vendor_collection.update_one(
            {"product_id": product["product_id"], "store_id": store_id, "org_id": org_id},
            {
                "$inc": {"return_quantity": product["return_quantity"]},
                "$setOnInsert": {
                    "return_id": return_order["return_id"],
                    "order_id": return_order["order_id"],
                    "vendor_id": vendor_id,  # Add vendor_id
                    "vendor_name": vendor_name,
                    "product_name": product["product_name"],
                    "delivery_date": product.get("delivery_date", datetime.now().strftime("%Y-%m-%d")),
                    "status": "0",
                    "return_amount": str(product.get("return_amount", "0.0")),
                    "original_quantity": product.get("original_quantity", product["return_quantity"]),
                    "unit": product.get("unit", "pcs"),
                    "contract_id": product.get("contract_id", "UNKNOWN"),
                    "purchase_date": product.get("purchase_date", datetime.now().strftime("%Y-%m-%d")),
                    "product_condition": "Damaged and returnable",
                    "total_price": product.get("total_price", product["return_quantity"] * product.get("unit_price", 0)),
                    "unit_price": product.get("unit_price", 0),
                    "return_reason": return_order.get("seller_return_conditions", ["Unknown"])[0]
                }
            },
            upsert=True
        )
        action = f" Return to Vendor: {product['return_quantity']} unit(s) of {product['product_name']} marked for vendor return (Damaged & Returnable)"

    # ✅ CASE 2: Product Damage & NOT Seller Returnable → LossOrders
    elif reason == "Damage on arrival" and is_seller_returnable:
        await loss_orders_collection.update_one(
            {"product_id": product["product_id"], "store_id": store_id, "org_id": org_id},
            {
                "$inc": {"quantity_lost": product["return_quantity"]},
                "$setOnInsert": {
                    "product_name": product["product_name"],
                    "category": product.get("category", "stationery"),
                    "date_reported": datetime.now().strftime("%Y-%m-%d"),
                    "unit": product.get("unit", "pcs"),
                    "unit_price": str(product.get("unit_price", "0")),
                    "reason": "Damaged and not returnable"
                }
            },
            upsert=True
        )
        action = f" Loss Orders: {product['return_quantity']} unit(s) of {product['product_name']} added to Loss Sheet (Damaged & Not Returnable)"

    # ✅ CASE 3: Not Product Damage → Inventory (with hierarchical structure)
    else:
        product_name = product["product_name"]
        return_quantity = product["return_quantity"]
        product_id = product.get("product_id")
        unit_price = str(product.get("unit_price", "0.0"))
        
        # Get vendor details
        vendor_name = product.get("vendor_name", "Unknown")
        vendor_id = None
        if vendor_name != "Unknown":
            vendor = await db.Vendors.find_one(
                {"vendor_name": vendor_name},
                {"vendor_id": 1, "_id": 0}
            )
            if vendor:
                vendor_id = vendor.get("vendor_id")
        
        # Check if product exists in Inventory
        existing_product = await inventory_collection.find_one({
            "product_id": product_id,
            "store_id": store_id
        })
        
        if existing_product:
            # Update existing product quantity
            new_quantity = existing_product.get("quantity", 0) + return_quantity
            
            await inventory_collection.update_one(
                {"_id": existing_product["_id"]},
                {
                    "$set": {
                        "quantity": new_quantity,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
        else:
            # Create new product
            if not product_id:
                product_id = await _next_id(inventory_collection, "product_id", "PROD", store_id)
            
            product_data = {
                "product_id": product_id,
                "org_id": org_id,
                "store_id": store_id,
                "product_name": product_name,
                "quantity": return_quantity,
                "unit": product.get("unit", "pcs"),
                "category": product.get("category", "stationery"),
                "sub_category": product.get("sub_category", "misc"),
                "tags": product.get("tags", []),
                "tax": product.get("tax", 0),
                "min_stock": 5,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "status": "Stock-in"
            }
            
            await inventory_collection.insert_one(product_data)
        
        # ✅ Create individual ProductItems for each quantity
        items_created = []
        for i in range(return_quantity):
            item_id = await _next_id(db.ProductItems, "item_id", "ITEM", store_id)
            
            item_data = {
                "org_id": org_id,
                "store_id": store_id,
                "item_id": item_id,
                "product_id": product_id,
                "item_name": product_name,
                "unit_price": unit_price,
                "vendor_id": vendor_id,
                "vendor_name": vendor_name,
                "serial_no": None,
                "batch_number": product.get("batch_number"),
                "is_consumer_returnable": return_order.get("is_customer_returnable", False),
                "consumer_return_conditions": return_order.get("consumer_return_conditions", []),
                "is_seller_returnable": return_order.get("is_seller_returnable", False),
                "seller_return_conditions": return_order.get("seller_return_conditions", []),
                "has_warranty": product.get("has_warranty", False) or (product.get("warranty_tenure", 0) > 0),
                "warranty_tenure": product.get("warranty_tenure", 0),
                "warranty_unit": product.get("warranty_unit", "months"),
                "status": "available",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            await db.ProductItems.insert_one(item_data)
            items_created.append(item_id)
        
        action = f" Added to Inventory: {len(items_created)} item(s) of {product_name} added to Inventory (Available for sale)"

    # ✅ Update status to completed after processing
    await return_orders_collection.update_one(
        {
            "return_id": data.return_id,
            "store_id": store_id
        },
        {
            "$set": {
                "status": "completed",
                "processed_at": datetime.now()
            }
        }
    )

    return {"message": f"Validation successful. {action}"}
