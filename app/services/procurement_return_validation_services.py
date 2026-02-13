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
    seller_return_conditions = return_order.get("seller_return_conditions", [])
    order_id = return_order.get("order_id")
    
    # ✅ If is_seller_returnable is False but seller_return_conditions exist, check product from inventory
    if not is_seller_returnable and not seller_return_conditions:
        # Get product from inventory to check actual seller returnability
        product_id = product.get("product_id")
        if product_id:
            inventory_product = await db.Inventory.find_one({
                "product_id": product_id,
                "store_id": store_id
            })
            
            if inventory_product:
                # Get seller returnability from inventory product
                inv_seller_conditions = inventory_product.get("seller_return_conditions", [])
                if inv_seller_conditions and len(inv_seller_conditions) > 0:
                    is_seller_returnable = True
                    seller_return_conditions = inv_seller_conditions
                    # print(f"[DEBUG] Updated is_seller_returnable from inventory: True")
                    print(f"[DEBUG] Seller conditions from inventory: {inv_seller_conditions}")
    
    # ✅ Auto-correct: If seller_return_conditions exist but is_seller_returnable is False, set it to True
    if seller_return_conditions and len(seller_return_conditions) > 0 and not is_seller_returnable:
        is_seller_returnable = True
        print(f"[DEBUG] Auto-corrected is_seller_returnable to True based on conditions: {seller_return_conditions}")
    
    # ✅ Debug logging
    print(f"[DEBUG] Processing return: {data.return_id}")
    print(f"[DEBUG] Reason: '{reason}'")
    print(f"[DEBUG] Is seller returnable (final): {is_seller_returnable}")
    print(f"[DEBUG] Seller return conditions: {seller_return_conditions}")
    
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
        
        destination = result.get("destination", "Unknown")
        product_name = product.get("product_name", "Product")
        return_qty = product.get("return_quantity", 1)
        product_id = product.get("product_id")
        
        print(f"[DEBUG] Customer return destination: {destination}")
        
        # ✅ Create entries in LossOrders or ReturnToVendor collections based on destination
        if destination == "LossOrders":
            # Get damaged items for this return
            damaged_items = await db.ProductItems.find({
                "product_id": product_id,
                "store_id": store_id,
                "status": "damaged",
                "sold_order_id": order_id
            }).limit(return_qty).to_list(return_qty)
            
            damaged_item_ids = [item.get("item_id") for item in damaged_items]
            
            # Check if loss entry exists
            existing_loss = await loss_orders_collection.find_one({
                "product_id": product_id,
                "store_id": store_id,
                "org_id": org_id
            })
            
            unit_price = float(product.get("unit_price", 0))
            
            if existing_loss:
                # Update existing loss entry
                new_quantity = existing_loss.get("quantity_lost", 0) + return_qty
                new_loss_amount = unit_price * new_quantity
                existing_damaged_ids = existing_loss.get("damaged_item_ids", [])
                
                await loss_orders_collection.update_one(
                    {"_id": existing_loss["_id"]},
                    {
                        "$set": {
                            "quantity_lost": new_quantity,
                            "loss_amount": str(new_loss_amount),
                            "damaged_item_ids": existing_damaged_ids + damaged_item_ids,
                            "updated_at": datetime.now()
                        }
                    }
                )
                loss_id = existing_loss.get("loss_id", "UNKNOWN")
            else:
                # Create new loss entry
                loss_id = await _next_id(loss_orders_collection, "loss_id", "LOSS", store_id)
                loss_amount = unit_price * return_qty
                
                loss_data = {
                    "loss_id": loss_id,
                    "product_id": product_id,
                    "store_id": store_id,
                    "org_id": org_id,
                    "product_name": product_name,
                    "category": product.get("category", "stationery"),
                    "sub_category": product.get("sub_category", "misc"),
                    "date_reported": datetime.now().strftime("%Y-%m-%d"),
                    "unit": product.get("unit", "pcs"),
                    "unit_price": str(unit_price),
                    "quantity_lost": return_qty,
                    "loss_amount": str(loss_amount),
                    "reason": f"Customer return - {reason}",
                    "damaged_item_ids": damaged_item_ids,
                    "vendor_id": product.get("vendor_id"),
                    "vendor_name": product.get("vendor_name", "Unknown"),
                    "damage_condition": reason,
                    "return_order_id": return_order["return_id"],
                    "original_order_id": order_id,
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                }
                await loss_orders_collection.insert_one(loss_data)
            
            message = f"Customer return processed: {return_qty} unit of {product_name} added to Loss Sheet ( ID: {loss_id})"
            
        elif destination == "ReturnToVendor":
            # Get items marked for vendor return
            vendor_return_items = await db.ProductItems.find({
                "product_id": product_id,
                "store_id": store_id,
                "status": "return_to_vendor",
                "sold_order_id": order_id
            }).limit(return_qty).to_list(return_qty)
            
            returnable_item_ids = [item.get("item_id") for item in vendor_return_items]
            
            # Get vendor info
            vendor_name = product.get("vendor_name", "Unknown")
            vendor_id = None
            if vendor_name != "Unknown":
                vendor = await db.Vendors.find_one(
                    {"vendor_name": vendor_name},
                    {"vendor_id": 1, "_id": 0}
                )
                if vendor:
                    vendor_id = vendor.get("vendor_id")
            
            # Check if return to vendor entry exists
            existing_return = await return_to_vendor_collection.find_one({
                "product_id": product_id,
                "store_id": store_id,
                "org_id": org_id
            })
            
            unit_price = float(product.get("unit_price", 0))
            
            if existing_return:
                # Update existing return entry
                new_quantity = existing_return.get("return_quantity", 0) + return_qty
                new_return_amount = unit_price * new_quantity
                existing_item_ids = existing_return.get("returnable_item_ids", [])
                
                await return_to_vendor_collection.update_one(
                    {"_id": existing_return["_id"]},
                    {
                        "$set": {
                            "return_quantity": new_quantity,
                            "return_amount": str(new_return_amount),
                            "returnable_item_ids": existing_item_ids + returnable_item_ids,
                            "updated_at": datetime.now()
                        }
                    }
                )
            else:
                # Create new return to vendor entry
                return_data = {
                    "return_id": return_order["return_id"],
                    "order_id": order_id,
                    "product_id": product_id,
                    "store_id": store_id,
                    "org_id": org_id,
                    "vendor_id": vendor_id,
                    "vendor_name": vendor_name,
                    "product_name": product_name,
                    "category": product.get("category", "stationery"),
                    "sub_category": product.get("sub_category", "misc"),
                    "status": "pending",
                    "return_quantity": return_qty,
                    "return_amount": str(product.get("return_amount", unit_price * return_qty)),
                    "unit": product.get("unit", "pcs"),
                    "unit_price": unit_price,
                    "return_reason": f"Customer return - {reason}",
                    "returnable_item_ids": returnable_item_ids,
                    "return_order_id": return_order["return_id"],
                    "original_order_id": order_id,
                    "created_at": datetime.now(),
                    "updated_at": datetime.now()
                }
                await return_to_vendor_collection.insert_one(return_data)
            
            message = f"Customer return processed: {return_qty} unit of {product_name} marked for Return to Vendor"
        else:
            # Inventory destination
            message = f"Customer return processed:{return_qty} unit of {product_name} restocked and available for resale"
        
        # Update return order status to completed with destination tracking
        await return_orders_collection.update_one(
            {
                "return_id": data.return_id,
                "store_id": store_id
            },
            {
                "$set": {
                    "status": "completed",
                    "destination": destination,  # ✅ Save destination for future reference
                    "processed_at": datetime.now()
                }
            }
        )
        
        return {
            "message": message,
            "status": "completed",
            "destination": destination,
            "details": result
        }

    # ✅ CASE 1: Product Damage & Seller Returnable → ReturnToVendor
    print(f"[DEBUG] Checking CASE 1: damage={'damage' in reason.lower()}, returnable={is_seller_returnable}")
    if "damage" in reason.lower() and is_seller_returnable:
        print(f"[DEBUG] CASE 1 MATCHED: Return to Vendor")
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
        
        # ✅ Get available product items to mark as returnable to vendor
        available_items = await db.ProductItems.find({
            "product_id": product["product_id"],
            "store_id": store_id,
            "status": "available"
        }).limit(product["return_quantity"]).to_list(length=None)
        
        if len(available_items) < product["return_quantity"]:
            raise HTTPException(
                status_code=400, 
                detail=f"Not enough available items to return to vendor. Available: {len(available_items)}, Requested: {product['return_quantity']}"
            )
        
        # ✅ Extract item IDs and mark them as returnable to vendor
        returnable_item_ids = []
        for item in available_items:
            item_id = item.get("item_id")
            returnable_item_ids.append(item_id)
            
            # Update ProductItem status to 'return_to_vendor'
            await db.ProductItems.update_one(
                {"_id": item["_id"]},
                {
                    "$set": {
                        "status": "return_to_vendor",
                        "return_reason": "Damaged and returnable to vendor",
                        "return_initiated_at": datetime.now(),
                        "updated_at": datetime.now()
                    }
                }
            )
        
        # ✅ Check if return to vendor entry already exists
        existing_return = await return_to_vendor_collection.find_one({
            "product_id": product["product_id"],
            "store_id": store_id,
            "org_id": org_id
        })
        
        if existing_return:
            # Update existing return entry - increment quantity, add new item IDs
            existing_item_ids = existing_return.get("returnable_item_ids", [])
            updated_item_ids = existing_item_ids + returnable_item_ids
            new_quantity = existing_return.get("return_quantity", 0) + product["return_quantity"]
            unit_price = float(existing_return.get("unit_price", 0))
            new_return_amount = unit_price * new_quantity
            
            await return_to_vendor_collection.update_one(
                {"_id": existing_return["_id"]},
                {
                    "$set": {
                        "return_quantity": new_quantity,
                        "return_amount": str(new_return_amount),
                        "returnable_item_ids": updated_item_ids,  # Store all returnable item IDs
                        "total_price": existing_return.get("total_price", 0) + product.get("total_price", product["return_quantity"] * unit_price),
                        "updated_at": datetime.now()
                    }
                }
            )
            action = f" Return to Vendor: {product['return_quantity']} unit(s) of {product['product_name']} added to existing vendor return (Total: {new_quantity} units, Items: {returnable_item_ids}, Returnable to Vendor)"
            destination = "ReturnToVendor"
        else:
            # Create new return to vendor entry with complete details
            return_data = {
                "return_id": return_order["return_id"],
                "order_id": return_order.get("order_id"),
                "product_id": product["product_id"],
                "store_id": store_id,
                "org_id": org_id,
                "vendor_id": vendor_id,
                "vendor_name": vendor_name,
                "product_name": product["product_name"],
                "category": product.get("category", "stationery"),
                "sub_category": product.get("sub_category", "misc"),
                "delivery_date": product.get("delivery_date", datetime.now().strftime("%Y-%m-%d")),
                "status": "pending",  # Default status for new vendor returns
                "return_quantity": product["return_quantity"],
                "return_amount": str(product.get("return_amount", "0.0")),
                "original_quantity": product.get("original_quantity", product["return_quantity"]),
                "unit": product.get("unit", "pcs"),
                "unit_price": product.get("unit_price", 0),
                "contract_id": product.get("contract_id", "UNKNOWN"),
                "purchase_date": product.get("purchase_date", datetime.now().strftime("%Y-%m-%d")),
                "product_condition": "Damaged and returnable",
                "total_price": product.get("total_price", product["return_quantity"] * product.get("unit_price", 0)),
                "return_reason": return_order.get("seller_return_conditions", ["Unknown"])[0],
                "returnable_item_ids": returnable_item_ids,  # Store specific item IDs for vendor return
                # ✅ Store complete vendor and purchase information
                "batch_number": product.get("batch_number"),
                # ✅ Store return conditions and warranty information
                "is_consumer_returnable": return_order.get("is_customer_returnable", False),
                "consumer_return_conditions": return_order.get("consumer_return_conditions", []),
                "is_seller_returnable": return_order.get("is_seller_returnable", False),
                "seller_return_conditions": return_order.get("seller_return_conditions", []),
                "has_warranty": product.get("has_warranty", False) or (product.get("warranty_tenure", 0) > 0),
                "warranty_tenure": product.get("warranty_tenure", 0),
                "warranty_unit": product.get("warranty_unit", "months"),
                # ✅ Store return specific information
                "return_condition": "Damage on arrival - Returnable to vendor",
                "return_order_id": return_order["return_id"],
                "original_order_id": return_order.get("order_id"),
                "tags": product.get("tags", []),
                "tax": product.get("tax", 0),
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            
            await return_to_vendor_collection.insert_one(return_data)
            action = f" Return to Vendor: {product['return_quantity']} unit(s) of {product['product_name']} marked for vendor return (Items: {returnable_item_ids}, Damaged & Returnable)"
            destination = "ReturnToVendor"

    # ✅ CASE 2: Product Damage & NOT Seller Returnable → LossOrders
    elif "damage" in reason.lower() and not is_seller_returnable:
        print(f"[DEBUG] CASE 2 MATCHED: Loss Orders")
        # Get available product items to mark as damaged
        available_items = await db.ProductItems.find({
            "product_id": product["product_id"],
            "store_id": store_id,
            "status": "available"
        }).limit(product["return_quantity"]).to_list(length=None)
        
        if len(available_items) < product["return_quantity"]:
            raise HTTPException(
                status_code=400, 
                detail=f"Not enough available items to mark as damaged. Available: {len(available_items)}, Requested: {product['return_quantity']}"
            )
        
        # Extract item IDs and mark them as damaged
        damaged_item_ids = []
        for item in available_items:
            item_id = item.get("item_id")
            damaged_item_ids.append(item_id)
            
            # Update ProductItem status to 'damaged'
            await db.ProductItems.update_one(
                {"_id": item["_id"]},
                {
                    "$set": {
                        "status": "damaged",
                        "damage_reason": "Damaged and not returnable",
                        "damaged_at": datetime.now(),
                        "updated_at": datetime.now()
                    }
                }
            )
        
        # Check if loss entry already exists for this product_id
        existing_loss = await loss_orders_collection.find_one({
            "product_id": product["product_id"],
            "store_id": store_id,
            "org_id": org_id
        })
        
        if existing_loss:
            # Update existing loss entry - increment quantity, add new item IDs, and recalculate loss_amount
            existing_item_ids = existing_loss.get("damaged_item_ids", [])
            updated_item_ids = existing_item_ids + damaged_item_ids
            new_quantity = existing_loss.get("quantity_lost", 0) + product["return_quantity"]
            unit_price = float(existing_loss.get("unit_price", 0))
            new_loss_amount = unit_price * new_quantity
            
            # ✅ Update with complete vendor and item information
            await loss_orders_collection.update_one(
                {"_id": existing_loss["_id"]},
                {
                    "$set": {
                        "quantity_lost": new_quantity,
                        "loss_amount": str(new_loss_amount),
                        "damaged_item_ids": updated_item_ids,  # Store all damaged item IDs
                        "total_price": existing_loss.get("total_price", 0) + product.get("total_price", product["return_quantity"] * unit_price),
                        # ✅ Update vendor information if not already present
                        "vendor_id": vendor_id if not existing_loss.get("vendor_id") else existing_loss.get("vendor_id"),
                        "vendor_name": vendor_name if not existing_loss.get("vendor_name") else existing_loss.get("vendor_name"),
                        # ✅ Update return conditions information
                        "is_consumer_returnable": return_order.get("is_customer_returnable", existing_loss.get("is_consumer_returnable", False)),
                        "consumer_return_conditions": return_order.get("consumer_return_conditions", existing_loss.get("consumer_return_conditions", [])),
                        "is_seller_returnable": return_order.get("is_seller_returnable", existing_loss.get("is_seller_returnable", False)),
                        "seller_return_conditions": return_order.get("seller_return_conditions", existing_loss.get("seller_return_conditions", [])),
                        # ✅ Update damage condition
                        "damage_condition": "Semi-damage" if reason != "Damage on arrival" else "Damage on arrival",
                        "updated_at": datetime.now()
                    }
                }
            )
            loss_id = existing_loss.get("loss_id", "UNKNOWN")
            action = f" Loss Orders: {product['return_quantity']} unit(s) of {product['product_name']} added to existing Loss Sheet entry {loss_id} (Total: {new_quantity} units, Damaged Items: {damaged_item_ids}, Not Returnable)"
            destination = "LossOrders"
        else:
            # Generate new loss_id for tracking
            loss_id = await _next_id(loss_orders_collection, "loss_id", "LOSS", store_id)
            
            # Calculate loss_amount
            unit_price = float(product.get("unit_price", 0))
            quantity_lost = product["return_quantity"]
            loss_amount = unit_price * quantity_lost
            
            # Create new loss entry with loss_id and damaged item IDs and complete vendor/item details
            loss_data = {
                "loss_id": loss_id,  # Custom tracking ID
                "product_id": product["product_id"],  # Original product reference
                "store_id": store_id,
                "org_id": org_id,
                "product_name": product["product_name"],
                "category": product.get("category", "stationery"),
                "sub_category": product.get("sub_category", "misc"),
                "date_reported": datetime.now().strftime("%Y-%m-%d"),
                "unit": product.get("unit", "pcs"),
                "unit_price": str(unit_price),
                "quantity_lost": quantity_lost,
                "loss_amount": str(loss_amount),
                "reason": "Damaged and not returnable",
                "damaged_item_ids": damaged_item_ids,  # Store specific item IDs that are damaged
                # ✅ Store complete vendor and purchase information
                "vendor_id": vendor_id,
                "vendor_name": vendor_name,
                "batch_number": product.get("batch_number"),
                "purchase_date": product.get("purchase_date", datetime.now().strftime("%Y-%m-%d")),
                "delivery_date": product.get("delivery_date", datetime.now().strftime("%Y-%m-%d")),
                "contract_id": product.get("contract_id", "UNKNOWN"),
                "total_price": product.get("total_price", quantity_lost * unit_price),
                # ✅ Store return conditions and warranty information
                "is_consumer_returnable": return_order.get("is_customer_returnable", False),
                "consumer_return_conditions": return_order.get("consumer_return_conditions", []),
                "is_seller_returnable": return_order.get("is_seller_returnable", False),
                "seller_return_conditions": return_order.get("seller_return_conditions", []),
                "has_warranty": product.get("has_warranty", False) or (product.get("warranty_tenure", 0) > 0),
                "warranty_tenure": product.get("warranty_tenure", 0),
                "warranty_unit": product.get("warranty_unit", "months"),
                # ✅ Store damage specific information
                "damage_condition": "Semi-damage" if reason != "Damage on arrival" else "Damage on arrival",
                "return_order_id": return_order["return_id"],
                "original_order_id": return_order.get("order_id"),
                "tags": product.get("tags", []),
                "tax": product.get("tax", 0),
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }
            
            await loss_orders_collection.insert_one(loss_data)
            action = f" Loss Orders: {product['return_quantity']} unit(s) of {product['product_name']} added to Loss Sheet with tracking ID: {loss_id} (Damaged Items: {damaged_item_ids}, Not Returnable)"
            destination = "LossOrders"

    # ✅ CASE 3: Not Product Damage → Inventory (with hierarchical structure)
    else:
        print(f"[DEBUG] CASE 3 MATCHED: Inventory (no damage detected)")
        product_name = product["product_name"]
        return_quantity = product["return_quantity"]
        product_id = product.get("product_id")
        order_id = return_order.get("order_id")
        
        # ✅ CHECK: If order_id exists, these are sold items that need to be updated back to available
        if order_id and product_id:
            # Find sold items from this order
            sold_items = await db.ProductItems.find({
                "product_id": product_id,
                "store_id": store_id,
                "sold_order_id": order_id,
                "status": "sold"
            }).limit(return_quantity).to_list(length=None)
            
            if len(sold_items) >= return_quantity:
                # ✅ Update sold items back to available status
                items_updated = []
                for item in sold_items[:return_quantity]:
                    await db.ProductItems.update_one(
                        {"item_id": item["item_id"], "store_id": store_id},
                        {
                            "$set": {
                                "status": "available",
                                "updated_at": datetime.utcnow()
                            },
                            "$unset": {
                                "sold_order_id": "",
                                "sold_at": ""
                            }
                        }
                    )
                    items_updated.append(item["item_id"])
                
                # ✅ Update product quantity (count available items)
                available_count = await db.ProductItems.count_documents({
                    "product_id": product_id,
                    "store_id": store_id,
                    "status": "available"
                })
                
                await inventory_collection.update_one(
                    {"product_id": product_id, "store_id": store_id},
                    {
                        "$set": {
                            "quantity": available_count,
                            "updated_at": datetime.utcnow()
                        }
                    }
                )
                
                action = f" Returned to Inventory: {len(items_updated)} item(s) of {product_name} updated back to Available status"
                destination = "Inventory"
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Not enough sold items found. Required: {return_quantity}, Found: {len(sold_items)}"
                )
        else:
            # ✅ No order_id or product_id - create new items (old flow for non-sale returns)
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
                    "selling_price": None,  # Will be set when item is sold
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
            destination = "Inventory"

    # ✅ Update status to completed after processing with destination tracking
    await return_orders_collection.update_one(
        {
            "return_id": data.return_id,
            "store_id": store_id
        },
        {
            "$set": {
                "status": "completed",
                "destination": destination,  # ✅ Save destination for future reference
                "processed_at": datetime.now()
            }
        }
    )

    return {"message": f"Validation successful. {action}", "status": "completed", "destination": destination}
