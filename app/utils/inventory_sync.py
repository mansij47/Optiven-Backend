"""
Inventory Synchronization Utility
Handles all inventory calculations and updates in one place.
Called only when inventory changes (event-driven).
"""
from datetime import datetime
from app.db import db
from app.services.notification_service import create_notification
from app.models.notification_model import NotificationBase, UserInfo


async def sync_inventory_on_change(product_id: str, store_id: str, background_tasks=None):
    """
    Centralized inventory sync function.
    Called whenever inventory changes (procurement, sales, returns, damage).
    
    Performs:
    1. Calculate available quantity from ProductItems
    2. Calculate average price from items
    3. Calculate average vendor tax from items  
    4. Calculate average selling price from items
    5. Update Inventory collection in ONE operation
    6. Check and trigger low-stock notification (background)
    
    Args:
        product_id: Product to sync
        store_id: Store context
        background_tasks: FastAPI BackgroundTasks (optional, for async notifications)
    """
    
    # ✅ 1. Get all available items for this product
    items_cursor = db.ProductItems.find(
        {"product_id": product_id, "store_id": store_id, "status": "available"},
        {"unit_price": 1, "vendor_tax": 1, "selling_price": 1, "_id": 0}
    )
    items = await items_cursor.to_list(length=None)
    
    # ✅ 2. Calculate metrics
    available_quantity = len(items)
    
    # Calculate average price (from unit_price)
    prices = [float(item.get("unit_price", 0)) for item in items if item.get("unit_price")]
    average_price = round(sum(prices) / len(prices), 2) if prices else 0.0
    
    # Calculate average vendor tax
    taxes = [float(item.get("vendor_tax", 0)) for item in items if item.get("vendor_tax") is not None]
    average_vendor_tax = round(sum(taxes) / len(taxes), 2) if taxes else None
    
    # Calculate average selling price
    selling_prices = [float(item.get("selling_price", 0)) for item in items if item.get("selling_price")]
    average_selling_price = round(sum(selling_prices) / len(selling_prices), 2) if selling_prices else 0.0
    
    # ✅ 3. Get product to determine status and check low stock
    product = await db.Inventory.find_one(
        {"product_id": product_id, "store_id": store_id},
        {"min_stock": 1, "product_name": 1, "status": 1, "_id": 0}
    )
    
    if not product:
        return  # Product doesn't exist
    
    min_stock = product.get("min_stock", 0)
    current_status = product.get("status", "Stock-out")
    
    # Determine new status based on quantity
    # quantity == 0 → Stock-out
    # quantity > 0 AND quantity < min_stock → Low Stock
    # quantity >= min_stock → Stock-in
    if available_quantity == 0:
        new_status = "Stock-out"
    elif available_quantity < min_stock:
        new_status = "Low Stock"
    else:
        new_status = "Stock-in"
    
    # ✅ 4. Update Inventory in ONE operation
    await db.Inventory.update_one(
        {"product_id": product_id, "store_id": store_id},
        {
            "$set": {
                "quantity": available_quantity,
                "average_price": average_price,
                "vendor_tax": average_vendor_tax,
                "average_selling_price": average_selling_price,
                "status": new_status,
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    # ✅ 5. Check low-stock notification (background task)
    # Only notify if status changed TO "Low Stock" to avoid spam
    if new_status == "Low Stock" and current_status != "Low Stock":
        if background_tasks:
            # Use FastAPI BackgroundTasks
            background_tasks.add_task(
                send_low_stock_notification,
                product_id=product_id,
                product_name=product.get("product_name"),
                available_quantity=available_quantity,
                min_stock=min_stock,
                store_id=store_id
            )
        else:
            # Fallback: send immediately (not recommended for production)
            await send_low_stock_notification(
                product_id=product_id,
                product_name=product.get("product_name"),
                available_quantity=available_quantity,
                min_stock=min_stock,
                store_id=store_id
            )


async def send_low_stock_notification(product_id: str, product_name: str, available_quantity: int, min_stock: int, store_id: str):
    """
    Send low-stock notification to admin and procurement.
    Runs in background to not block API response.
    """
    try:
        notification = NotificationBase(
            sender=UserInfo(
                role="system",
                id="inventory_monitor",
                store_id=store_id
            ),
            type_of_notification="Inventory Alert",
            title="⚠️ Low Stock Alert",
            message=f"Product '{product_name}' is running low. Available: {available_quantity}, Minimum: {min_stock}",
            emails=[]
        )
        
        await create_notification(
            notification=notification,
            admin=True,
            procurement=True
        )
        
        print(f"✅ Low-stock notification sent for {product_name}")
    except Exception as e:
        print(f"❌ Failed to send low-stock notification: {str(e)}")


async def bulk_sync_inventory(product_ids: list, store_id: str, background_tasks=None):
    """
    Sync multiple products at once.
    Useful for batch operations (e.g., bulk procurement validation).
    
    Args:
        product_ids: List of product IDs to sync
        store_id: Store context
        background_tasks: FastAPI BackgroundTasks (optional)
    """
    for product_id in product_ids:
        await sync_inventory_on_change(product_id, store_id, background_tasks)
