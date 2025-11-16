from fastapi import HTTPException
from app.models.admin_model import Product, ProductItem, ProductItemUpdateModel
from app.db import db
import csv
import io
from fastapi.responses import StreamingResponse
from app.utils.raise_order import _next_id
from datetime import datetime, timedelta
from bson import ObjectId

    #new add product service start here

# ✅ Helper to generate readable timestamp
def current_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ✅ Helper to calculate average price from all items of a product
async def calculate_average_price(product_id: str, store_id: str) -> float:
    """
    Calculate average price from all items belonging to a product.
    Returns 0.0 if no items found or all items have 0 price.
    """
    try:
        items_cursor = db.ProductItems.find(
            {"product_id": product_id, "store_id": store_id},
            {"unit_price": 1, "_id": 0}
        )
        
        items = await items_cursor.to_list(length=None)
        
        if not items:
            return 0.0
        
        # Convert unit_price to float and calculate average
        prices = []
        for item in items:
            unit_price = item.get("unit_price", "0")
            try:
                price = float(unit_price)
                prices.append(price)
            except (ValueError, TypeError):
                prices.append(0.0)
        
        if not prices or sum(prices) == 0:
            return 0.0
        
        average = sum(prices) / len(prices)
        return round(average, 2)
    
    except Exception as e:
        print(f"⚠️ Error calculating average price for {product_id}: {str(e)}")
        return 0.0


# ✅ Helper to check and send low stock notification
async def check_and_notify_low_stock(product_id: str, store_id: str):
    """
    Check if product quantity is at or below min_stock threshold.
    If yes, send notification to admin and procurement, and update status to 'running-out'.
    """
    try:
        product = await db.Inventory.find_one({"product_id": product_id, "store_id": store_id})
        if not product:
            return
        
        quantity = product.get("quantity", 0)
        min_stock = product.get("min_stock", 4)
        
        # Check if quantity has reached or dropped below min_stock threshold
        if quantity <= min_stock:
            from app.services.notification_service import create_notification
            from app.models.notification_model import NotificationBase, Sender
            
            # Update product status to "running-out"
            await db.Inventory.update_one(
                {"product_id": product_id, "store_id": store_id},
                {"$set": {"status": "running-out", "updated_at": datetime.utcnow()}}
            )
            
            # Send notification to admin and procurement
            notification_data = NotificationBase(
                title="⚠️ Low Stock Alert",
                description=f"Product '{product.get('product_name')}' is running out of stock! Current quantity: {quantity}, Minimum threshold: {min_stock}. Please restock immediately.",
                sender=Sender(
                    role="system",
                    id="inventory_monitor",
                    store_id=store_id,
                    email="system@optiven.com"
                ),
                emails=[]  # Will send to all admin and procurement users
            )
            
            await create_notification(
                notification=notification_data,
                admin=True,
                procurement=True
            )
            
            print(f"✅ Low stock alert sent for product {product_id}. Quantity: {quantity}, Min: {min_stock}")
    
    except Exception as e:
        print(f"⚠️ Failed to check/notify low stock for {product_id}: {str(e)}")


# ✅ 1. Add Product with Items (Hierarchical Structure)
async def add_product_service(product: Product, store_id: str, org_id: str):
    """
    Creates a Product and automatically generates ProductItems based on quantity.
    Product → ProductItem relationship (1 product can have multiple items)
    """
    try:
        product_dict = product.model_dump()
        quantity = product_dict.get("quantity", 0)

        # Check if product already exists in same store
        existing_product = await db.Inventory.find_one({
            "store_id": store_id,
            "product_name": product_dict["product_name"]
        })

        # ✅ If product exists — Update its quantity and create new items
        if existing_product:
            new_quantity = existing_product.get("quantity", 0) + quantity
            product_id = existing_product["product_id"]

            # Create new items for the additional quantity
            items_created = await create_product_items(product_id, quantity, product_dict, store_id, org_id)
            
            # ✅ Calculate average price from all items
            average_price = await calculate_average_price(product_id, store_id)

            # Update product quantity and average_price
            await db.Inventory.update_one(
                {"_id": existing_product["_id"]},
                {
                    "$set": {
                        "quantity": new_quantity,
                        "average_price": average_price,
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            return {
                "message": f"Existing product '{product_dict['product_name']}' updated successfully",
                "product_id": product_id,
                "updated_quantity": new_quantity,
                "average_price": average_price,
                "items_created": items_created
            }

        # ✅ If new product — Create new one with items
        new_product_id = await _next_id(db.Inventory, "product_id", "PROD", store_id)

        product_dict["product_id"] = new_product_id
        product_dict["store_id"] = store_id
        product_dict["org_id"] = org_id
        product_dict["created_at"] = datetime.utcnow()
        product_dict["updated_at"] = datetime.utcnow()
        product_dict["status"] = "Stock-in" if quantity > 0 else "Stock-out"
        product_dict["average_price"] = 0.0  # Will be updated after items are created

        # Insert product
        await db.Inventory.insert_one(product_dict)

        # Create individual items for this product
        items_created = await create_product_items(new_product_id, quantity, product_dict, store_id, org_id)
        
        # ✅ Calculate and update average price after items are created
        average_price = await calculate_average_price(new_product_id, store_id)
        await db.Inventory.update_one(
            {"product_id": new_product_id, "store_id": store_id},
            {"$set": {"average_price": average_price}}
        )

        return {
            "message": "New product added successfully with items",
            "product_id": new_product_id,
            "total_quantity": quantity,
            "average_price": average_price,
            "items_created": items_created
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding product: {str(e)}")


# ✅ Helper function to create product items
async def create_product_items(product_id: str, quantity: int, product_data: dict, store_id: str, org_id: str):
    """
    Creates individual ProductItem entries for each quantity unit of a product.
    Each item represents one unit with its own tracking details.
    """
    try:
        items_created = []
        
        for i in range(quantity):
            # Generate unique item ID
            item_id = await _next_id(db.ProductItems, "item_id", "ITEM", store_id)
            
            item_dict = {
                "org_id": org_id,
                "store_id": store_id,
                "item_id": item_id,
                "product_id": product_id,
                "item_name": product_data.get('product_name', ''),
                "unit_price": "0",  # Can be set later or from product data
                "vendor_id": None,
                "vendor_name": None,
                "serial_no": None,
                "batch_number": None,
                "is_consumer_returnable": False,
                "consumer_return_conditions": [],
                "is_seller_returnable": False,
                "seller_return_conditions": [],
                "has_warranty": False,
                "warranty_tenure": 0,
                "warranty_unit": "",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "status": "available"  # available, sold, returned, damaged, etc.
            }
            
            await db.ProductItems.insert_one(item_dict)
            items_created.append(item_id)
        
        return items_created
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating product items: {str(e)}")


# ✅ 2. Get All Products with Items Count
async def get_all_products(store_id: str):
    """
    Retrieves all products with their item count.
    Shows hierarchical structure: Product → Items
    Product quantity is always synced with actual item count.
    """
    try:
        products_cursor = (
            db["Inventory"].find({"store_id": store_id}, {"_id": 0})
            .sort("updated_at", -1)
        )

        products = []
        async for product in products_cursor:
            # Get total items count for this product (this is the real quantity)
            items_count = await db.ProductItems.count_documents({
                "product_id": product.get("product_id"),
                "store_id": store_id
            })

            # Get available items count (not sold/damaged)
            available_items = await db.ProductItems.count_documents({
                "product_id": product.get("product_id"),
                "store_id": store_id,
                "status": "available"
            })
            
            # ✅ Calculate average price from all items
            average_price = await calculate_average_price(product.get("product_id"), store_id)

            # Update product quantity to match actual item count
            product["quantity"] = items_count
            product["status"] = "Stock-in" if available_items > 0 else "Stock-out"
            product["average_price"] = average_price
            product["total_items"] = items_count
            product["available_items"] = available_items
            product.pop("_id", None)

            products.append(product)

        return {
            "total_count": len(products),
            "store_id": store_id,
            "products": products,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving products: {str(e)}")


# ✅ 3. Get Product by ID with All Items
async def get_product_by_id(product_id: str, store_id: str):
    """
    Retrieves a specific product with all its items.
    Shows complete hierarchical data: Product + all ProductItems
    Product quantity is always synced with actual item count.
    """
    try:
        product_data = await db.Inventory.find_one(
            {"product_id": product_id, "store_id": store_id},
            {"_id": 0}
        )

        if not product_data:
            raise HTTPException(status_code=404, detail="Product not found for this store.")

        # Get all items for this product
        items_cursor = db.ProductItems.find(
            {"product_id": product_id, "store_id": store_id},
            {"_id": 0}
        )
        
        items = []
        async for item in items_cursor:
            items.append(item)

        # Calculate available quantity
        available_items = sum(1 for item in items if item.get("status") == "available")
        
        # ✅ Calculate average price from all items
        average_price = await calculate_average_price(product_id, store_id)
        
        # Update product quantity to match actual item count
        product_data["quantity"] = len(items)
        product_data["status"] = "Stock-in" if available_items > 0 else "Stock-out"
        product_data["average_price"] = average_price
        product_data["total_items"] = len(items)
        product_data["available_items"] = available_items

        return {
            "product": product_data,
            "items": items
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving product: {str(e)}")


# ✅ 4. Update Product by ID
async def update_product_by_id(product_id: str, update_data: dict, store_id: str = None):
    """
    Updates product information. 
    Note: Quantity changes should be handled by adding/removing items, not directly updating quantity.
    """
    try:
        query = {"product_id": product_id}
        if store_id:
            query["store_id"] = store_id

        product = await db["Inventory"].find_one(query)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found.")

        # If quantity is being updated, handle item creation/deletion
        if "quantity" in update_data:
            old_quantity = product.get("quantity", 0)
            new_quantity = update_data["quantity"]
            quantity_diff = new_quantity - old_quantity

            if quantity_diff > 0:
                # Create new items
                await create_product_items(product_id, quantity_diff, product, store_id, product.get("org_id"))
            elif quantity_diff < 0:
                # Remove items (mark as removed or delete)
                items_to_remove = abs(quantity_diff)
                available_items = await db.ProductItems.find(
                    {"product_id": product_id, "status": "available"}
                ).limit(items_to_remove).to_list(items_to_remove)
                
                for item in available_items:
                    await db.ProductItems.update_one(
                        {"item_id": item["item_id"]},
                        {"$set": {"status": "removed", "updated_at": datetime.utcnow()}}
                    )

        update_data["updated_at"] = datetime.utcnow()
        await db["Inventory"].update_one(query, {"$set": update_data})

        updated = await db["Inventory"].find_one(query)
        if updated and "_id" in updated:
            updated["_id"] = str(updated["_id"])

        return {
            "message": "Product updated successfully",
            "product_id": product_id,
            "updated_data": updated
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating product: {str(e)}")


# ✅ 5. Delete Product (and all its items)
async def delete_product_service(product_id: str, store_id: str = None):
    """
    Deletes a product and all its associated items.
    Cascading delete: Product → ProductItems
    """
    try:
        query = {"product_id": product_id}
        if store_id:
            query["store_id"] = store_id

        # Delete all associated items first
        items_deleted = await db.ProductItems.delete_many({"product_id": product_id})
        
        # Then delete the product
        result = await db.Inventory.delete_one(query)
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Product not found.")

        return {
            "message": "Product and all associated items deleted successfully",
            "deleted_product_id": product_id,
            "items_deleted": items_deleted.deleted_count
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting product: {str(e)}")


# ✅ 6. Export Inventory CSV (Products with Items)
async def export_inventory_csv(store_id: str, org_id: str):
    """
    Exports inventory with hierarchical structure.
    Can export both products summary and detailed items.
    """
    try:
        cursor = db.Inventory.find({
            "store_id": store_id,
            "org_id": org_id
        })

        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow([
            "org_id", "store_id", "product_id", "product_name", "unit", 
            "total_quantity", "available_items", "category", "sub_category", 
            "tags", "tax", "min_stock", "status", "created_at", "updated_at"
        ])

        async for doc in cursor:
            # Get available items count
            available_items = await db.ProductItems.count_documents({
                "product_id": doc.get("product_id"),
                "status": "available"
            })
            
            quantity = int(doc.get("quantity", 0)) if doc.get("quantity") else 0
            status = "Stock-in" if available_items > 0 else "Stock-out"

            writer.writerow([
                doc.get("org_id", ""),
                doc.get("store_id", ""),
                doc.get("product_id", ""),
                doc.get("product_name", ""),
                doc.get("unit", ""),
                quantity,
                available_items,
                doc.get("category", ""),
                doc.get("sub_category", ""),
                "|".join(doc.get("tags") or []),
                doc.get("tax", 0.0),
                doc.get("min_stock", 5),
                status,
                str(doc.get("created_at", "")),
                str(doc.get("updated_at", ""))
            ])

        output.seek(0)
        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=inventory_export.csv"
            },
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error exporting inventory: {str(e)}")


# ========================================
# PRODUCT ITEM MANAGEMENT FUNCTIONS
# ========================================

# ✅ 7. Get All Items for a Product
async def get_product_items(product_id: str, store_id: str):
    """
    Get all items belonging to a specific product.
    Shows the detailed breakdown of individual units.
    """
    try:
        items_cursor = db.ProductItems.find(
            {"product_id": product_id, "store_id": store_id},
            {"_id": 0}
        ).sort("created_at", -1)
        
        items = []
        async for item in items_cursor:
            items.append(item)
        
        return {
            "product_id": product_id,
            "total_items": len(items),
            "items": items
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving product items: {str(e)}")


# ✅ 8. Get Single Item by ID
async def get_item_by_id(item_id: str, store_id: str):
    """
    Get details of a specific item.
    """
    try:
        item = await db.ProductItems.find_one(
            {"item_id": item_id, "store_id": store_id},
            {"_id": 0}
        )
        
        if not item:
            raise HTTPException(status_code=404, detail="Item not found.")
        
        return {"item": item}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving item: {str(e)}")


# ✅ 9. Update Item Details
async def update_item_by_id(item_id: str, update_data: ProductItemUpdateModel, store_id: str = None):
    """
    Update specific item details like serial number, vendor, warranty, etc.
    If unit_price is updated, recalculates product's average_price.
    """
    try:
        query = {"item_id": item_id}
        if store_id:
            query["store_id"] = store_id
        
        item = await db.ProductItems.find_one(query)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found.")
        
        # Convert model to dict and remove None values
        update_dict = {k: v for k, v in update_data.model_dump().items() if v is not None}
        update_dict["updated_at"] = datetime.utcnow()
        
        # Check if unit_price is being updated
        unit_price_updated = "unit_price" in update_dict
        
        await db.ProductItems.update_one(query, {"$set": update_dict})
        
        # ✅ If unit_price was updated, recalculate product's average_price
        if unit_price_updated:
            product_id = item.get("product_id")
            item_store_id = item.get("store_id")
            if product_id and item_store_id:
                average_price = await calculate_average_price(product_id, item_store_id)
                await db.Inventory.update_one(
                    {"product_id": product_id, "store_id": item_store_id},
                    {"$set": {"average_price": average_price, "updated_at": datetime.utcnow()}}
                )
        
        updated_item = await db.ProductItems.find_one(query, {"_id": 0})
        
        return {
            "message": "Item updated successfully",
            "item_id": item_id,
            "updated_data": updated_item
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating item: {str(e)}")


# ✅ 10. Delete Single Item
async def delete_item_by_id(item_id: str, store_id: str = None):
    """
    Delete a single item and update product quantity.
    """
    try:
        query = {"item_id": item_id}
        if store_id:
            query["store_id"] = store_id
        
        item = await db.ProductItems.find_one(query)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found.")
        
        product_id = item.get("product_id")
        
        # Delete the item
        await db.ProductItems.delete_one(query)
        
        # Update product quantity
        remaining_items = await db.ProductItems.count_documents({
            "product_id": product_id,
            "store_id": store_id
        })
        
        await db.Inventory.update_one(
            {"product_id": product_id},
            {
                "$set": {
                    "quantity": remaining_items,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        return {
            "message": "Item deleted successfully",
            "deleted_item_id": item_id,
            "product_id": product_id,
            "remaining_items": remaining_items
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting item: {str(e)}")


# ✅ 11. Mark Item as Sold (and auto-update product quantity)
async def mark_item_as_sold(item_id: str, store_id: str, order_id: str = None):
    """
    Mark an item as sold and automatically update product quantity.
    This is the correct approach - we sell ITEMS, not products!
    """
    try:
        # Get item details first
        item = await db.ProductItems.find_one(
            {"item_id": item_id, "store_id": store_id}
        )
        
        if not item:
            raise HTTPException(status_code=404, detail="Item not found.")
        
        if item.get("status") == "sold":
            raise HTTPException(status_code=400, detail="Item is already sold.")
        
        product_id = item.get("product_id")
        
        # Mark item as sold
        await db.ProductItems.update_one(
            {"item_id": item_id, "store_id": store_id},
            {
                "$set": {
                    "status": "sold",
                    "sold_order_id": order_id,
                    "sold_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        # ✅ Auto-update product quantity (count remaining available items)
        remaining_available = await db.ProductItems.count_documents({
            "product_id": product_id,
            "store_id": store_id,
            "status": "available"
        })
        
        # Update product quantity in Inventory
        await db.Inventory.update_one(
            {"product_id": product_id, "store_id": store_id},
            {
                "$set": {
                    "quantity": remaining_available,
                    "updated_at": datetime.utcnow(),
                    "status": "Stock-in" if remaining_available > 0 else "Stock-out"
                }
            }
        )
        
        # ✅ Check if stock is low and send notification
        await check_and_notify_low_stock(product_id, store_id)
        
        return {
            "message": "Item marked as sold and inventory updated",
            "item_id": item_id,
            "product_id": product_id,
            "remaining_quantity": remaining_available
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error marking item as sold: {str(e)}")


# ✅ 11b. Mark Multiple Items as Sold (for bulk operations)
async def mark_items_as_sold_bulk(product_id: str, quantity: int, store_id: str, order_id: str = None):
    """
    Mark multiple items of a product as sold at once.
    Example: Sell 2 iPhones - this marks 2 iPhone items as sold
    """
    try:
        # Find available items for this product
        available_items = await db.ProductItems.find(
            {
                "product_id": product_id,
                "store_id": store_id,
                "status": "available"
            }
        ).limit(quantity).to_list(quantity)
        
        if len(available_items) < quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Not enough items available. Requested: {quantity}, Available: {len(available_items)}"
            )
        
        # Mark each item as sold
        items_sold = []
        for item in available_items:
            await db.ProductItems.update_one(
                {"item_id": item["item_id"]},
                {
                    "$set": {
                        "status": "sold",
                        "sold_order_id": order_id,
                        "sold_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            items_sold.append(item["item_id"])
        
        # ✅ Auto-update product quantity
        remaining_available = await db.ProductItems.count_documents({
            "product_id": product_id,
            "store_id": store_id,
            "status": "available"
        })
        
        await db.Inventory.update_one(
            {"product_id": product_id, "store_id": store_id},
            {
                "$set": {
                    "quantity": remaining_available,
                    "updated_at": datetime.utcnow(),
                    "status": "Stock-in" if remaining_available > 0 else "Stock-out"
                }
            }
        )
        
        # ✅ Check if stock is low and send notification
        await check_and_notify_low_stock(product_id, store_id)
        
        return {
            "message": f"{len(items_sold)} items marked as sold",
            "product_id": product_id,
            "items_sold": items_sold,
            "remaining_quantity": remaining_available
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error marking items as sold: {str(e)}")


# ✅ 11c. Handle Customer Return of Sold Items
async def handle_customer_return(
    order_id: str,
    product_id: str,
    return_quantity: int,
    return_reason: str,
    store_id: str,
    is_seller_returnable: bool = False
):
    """
    Handle customer returns of sold items.
    Based on the reason and returnability:
    - If damaged & seller returnable → Mark items as 'return_to_vendor'
    - If damaged & NOT seller returnable → Mark items as 'damaged' (loss)
    - Otherwise → Mark items as 'available' (back to inventory)
    
    Automatically updates product quantity in Inventory collection.
    """
    try:
        # ✅ 1. Find sold items from this order
        sold_items = await db.ProductItems.find(
            {
                "product_id": product_id,
                "store_id": store_id,
                "sold_order_id": order_id,
                "status": "sold"
            }
        ).limit(return_quantity).to_list(return_quantity)
        
        if len(sold_items) < return_quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Not enough sold items found for this order. Requested: {return_quantity}, Found: {len(sold_items)}"
            )
        
        # ✅ 2. Determine item destination based on return reason
        if return_reason == "Damage on arrival":
            if is_seller_returnable:
                # Damaged & returnable to vendor → Mark for vendor return
                new_status = "return_to_vendor"
                destination = "ReturnToVendor"
            else:
                # Damaged & NOT returnable → Mark as damaged (loss)
                new_status = "damaged"
                destination = "LossOrders"
        else:
            # Not damaged → Return to inventory as available
            new_status = "available"
            destination = "Inventory"
        
        # ✅ 3. Update each returned item's status
        items_returned = []
        for item in sold_items:
            update_fields = {
                "status": new_status,
                "returned_at": datetime.utcnow(),
                "return_reason": return_reason,
                "updated_at": datetime.utcnow()
            }
            
            # Clear sold tracking if returning to inventory
            if new_status == "available":
                update_fields["sold_order_id"] = None
                update_fields["sold_at"] = None
            
            await db.ProductItems.update_one(
                {"item_id": item["item_id"]},
                {"$set": update_fields}
            )
            items_returned.append({
                "item_id": item["item_id"],
                "new_status": new_status,
                "destination": destination
            })
        
        # ✅ 4. Auto-update product quantity based on available items
        available_count = await db.ProductItems.count_documents({
            "product_id": product_id,
            "store_id": store_id,
            "status": "available"
        })
        
        await db.Inventory.update_one(
            {"product_id": product_id, "store_id": store_id},
            {
                "$set": {
                    "quantity": available_count,
                    "updated_at": datetime.utcnow(),
                    "status": "Stock-in" if available_count > 0 else "Stock-out"
                }
            }
        )
        
        # ✅ 5. Get counts by status for summary
        damaged_count = await db.ProductItems.count_documents({
            "product_id": product_id,
            "store_id": store_id,
            "status": "damaged"
        })
        
        return_to_vendor_count = await db.ProductItems.count_documents({
            "product_id": product_id,
            "store_id": store_id,
            "status": "return_to_vendor"
        })
        
        return {
            "message": f"{len(items_returned)} items returned and processed",
            "product_id": product_id,
            "return_reason": return_reason,
            "destination": destination,
            "items_returned": items_returned,
            "inventory_updated": {
                "available_quantity": available_count,
                "damaged_count": damaged_count,
                "return_to_vendor_count": return_to_vendor_count
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error handling customer return: {str(e)}")


# ✅ 12. Get Items by Status
async def get_items_by_status(store_id: str, status: str):
    """
    Get all items filtered by status (available, sold, damaged, returned, etc.)
    """
    try:
        items_cursor = db.ProductItems.find(
            {"store_id": store_id, "status": status},
            {"_id": 0}
        ).sort("updated_at", -1)
        
        items = []
        async for item in items_cursor:
            items.append(item)
        
        return {
            "status": status,
            "total_items": len(items),
            "items": items
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving items by status: {str(e)}")


# ✅ 13. Export Product Items CSV
async def export_product_items_csv(product_id: str, store_id: str):
    """
    Export all items of a specific product to CSV.
    """
    try:
        cursor = db.ProductItems.find({
            "product_id": product_id,
            "store_id": store_id
        })

        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow([
            "item_id", "product_id", "item_name", "unit_price", "vendor_id", 
            "vendor_name", "serial_no", "batch_number", "status", 
            "has_warranty", "warranty_tenure", "warranty_unit",
            "is_consumer_returnable", "is_seller_returnable", 
            "created_at", "updated_at"
        ])

        async for item in cursor:
            writer.writerow([
                item.get("item_id", ""),
                item.get("product_id", ""),
                item.get("item_name", ""),
                item.get("unit_price", "0"),
                item.get("vendor_id", ""),
                item.get("vendor_name", ""),
                item.get("serial_no", ""),
                item.get("batch_number", ""),
                item.get("status", ""),
                item.get("has_warranty", False),
                item.get("warranty_tenure", 0),
                item.get("warranty_unit", ""),
                item.get("is_consumer_returnable", False),
                item.get("is_seller_returnable", False),
                str(item.get("created_at", "")),
                str(item.get("updated_at", ""))
            ])

        output.seek(0)
        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=product_{product_id}_items.csv"
            },
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error exporting product items: {str(e)}")
