from fastapi import HTTPException
from app.db import db
from datetime import datetime


async def delete_store_data_only(store_id: str, user_info: dict):
    """
    Delete all data associated with a store but keep the store itself.
    
    This function deletes:
    - All inventory products
    - All product items
    - All sales orders (received, sold, requested)
    - All profit orders
    - All loss orders
    - All return orders
    - All purchase orders
    - All notifications
    - All vendor data
    - All contracts
    
    BUT keeps:
    - The Store document
    - All users (admin, sales, procurement)
    
    Args:
        store_id: The store ID whose data should be deleted
        user_info: Admin user information from JWT token
    
    Returns:
        dict: Summary of deleted records from each collection
    """
    
    # Verify admin role
    if user_info.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden: Only admins can delete store data")
    
    # Verify the store exists
    store = await db.Stores.find_one({"store_id": store_id})
    if not store:
        raise HTTPException(status_code=404, detail=f"Store {store_id} not found")
    
    # Verify the admin belongs to this store
    if user_info.get("store_id") != store_id:
        raise HTTPException(status_code=403, detail="Forbidden: You can only delete data from your own store")
    
    # Track deletion summary
    deletion_summary = {
        "store_id": store_id,
        "store_name": store.get("store_name", "Unknown"),
        "deleted_at": datetime.utcnow().isoformat(),
        "collections_affected": {},
        "store_preserved": True
    }
    
    try:
        # 1. Keep all users (admin, sales, procurement) - DO NOT DELETE
        deletion_summary["collections_affected"]["Users"] = 0  # Users are preserved
        
        # 2. Delete all inventory products
        inventory_result = await db.Inventory.delete_many({"store_id": store_id})
        deletion_summary["collections_affected"]["Inventory"] = inventory_result.deleted_count
        
        # 3. Delete all product items
        items_result = await db.ProductItems.delete_many({"store_id": store_id})
        deletion_summary["collections_affected"]["ProductItems"] = items_result.deleted_count
        
        # 4. Delete all sales orders (received and sold)
        sales_orders_result = await db.SalesOrders.delete_many({"store_id": store_id})
        deletion_summary["collections_affected"]["SalesOrders"] = sales_orders_result.deleted_count
        
        # 5. Delete all profit orders
        profit_orders_result = await db.ProfitOrders.delete_many({"store_id": store_id})
        deletion_summary["collections_affected"]["ProfitOrders"] = profit_orders_result.deleted_count
        
        # 6. Delete all loss orders
        loss_orders_result = await db.LossOrders.delete_many({"store_id": store_id})
        deletion_summary["collections_affected"]["LossOrders"] = loss_orders_result.deleted_count
        
        # 7. Delete all return orders
        return_orders_result = await db.ReturnOrders.delete_many({"store_id": store_id})
        deletion_summary["collections_affected"]["ReturnOrders"] = return_orders_result.deleted_count
        
        # 8. Delete all requested orders
        requested_orders_result = await db.RequestedOrders.delete_many({"store_id": store_id})
        deletion_summary["collections_affected"]["RequestedOrders"] = requested_orders_result.deleted_count
        
        # 9. Delete all purchase orders
        try:
            purchase_orders_result = await db.PurchaseOrders.delete_many({"store_id": store_id})
            deletion_summary["collections_affected"]["PurchaseOrders"] = purchase_orders_result.deleted_count
        except Exception:
            deletion_summary["collections_affected"]["PurchaseOrders"] = 0
        
        # 10. Delete all notifications for this store
        notifications_result = await db.Notifications.delete_many({"sender.store_id": store_id})
        deletion_summary["collections_affected"]["Notifications"] = notifications_result.deleted_count
        
        # 11. Delete all vendors
        vendors_result = await db.Vendors.delete_many({"store_id": store_id})
        deletion_summary["collections_affected"]["Vendors"] = vendors_result.deleted_count
        
        # 12. Delete all contracts
        try:
            contracts_result = await db.Contracts.delete_many({"store_id": store_id})
            deletion_summary["collections_affected"]["Contracts"] = contracts_result.deleted_count
        except Exception:
            deletion_summary["collections_affected"]["Contracts"] = 0
        
        # 13. Delete all new inventory items
        try:
            new_inventory_result = await db.NewInventory.delete_many({"store_id": store_id})
            deletion_summary["collections_affected"]["NewInventory"] = new_inventory_result.deleted_count
        except Exception:
            deletion_summary["collections_affected"]["NewInventory"] = 0
        
        # Calculate total records deleted
        total_deleted = sum(deletion_summary["collections_affected"].values())
        deletion_summary["total_records_deleted"] = total_deleted
        
        return {
            "message": f"All data from store {store_id} deleted successfully. Store preserved.",
            "summary": deletion_summary
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error during store data deletion: {str(e)}"
        )


async def delete_store_and_data(store_id: str, user_info: dict):
    """
    Cascading delete: Removes a store and all associated data across all collections.
    
    This function deletes:
    - Store document from Stores collection
    - All users associated with the store
    - All inventory products
    - All product items
    - All sales orders (received, sold, requested)
    - All profit orders
    - All loss orders
    - All return orders
    - All purchase orders
    - All notifications
    - All vendor data
    - All contracts
    - Any other store-specific data
    
    Args:
        store_id: The store ID to delete
        user_info: Admin user information from JWT token
    
    Returns:
        dict: Summary of deleted records from each collection
    """
    
    # Verify admin role
    if user_info.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden: Only admins can delete stores")
    
    # Verify the store exists
    store = await db.Stores.find_one({"store_id": store_id})
    if not store:
        raise HTTPException(status_code=404, detail=f"Store {store_id} not found")
    
    # Track deletion summary
    deletion_summary = {
        "store_id": store_id,
        "store_name": store.get("store_name", "Unknown"),
        "deleted_at": datetime.utcnow().isoformat(),
        "collections_affected": {}
    }
    
    try:
        # 1. Delete all users associated with the store
        users_result = await db.Users.delete_many({"store_id": store_id})
        deletion_summary["collections_affected"]["Users"] = users_result.deleted_count
        
        # 2. Delete all inventory products
        inventory_result = await db.Inventory.delete_many({"store_id": store_id})
        deletion_summary["collections_affected"]["Inventory"] = inventory_result.deleted_count
        
        # 3. Delete all product items
        items_result = await db.ProductItems.delete_many({"store_id": store_id})
        deletion_summary["collections_affected"]["ProductItems"] = items_result.deleted_count
        
        # 4. Delete all sales orders (received and sold)
        sales_orders_result = await db.SalesOrders.delete_many({"store_id": store_id})
        deletion_summary["collections_affected"]["SalesOrders"] = sales_orders_result.deleted_count
        
        # 5. Delete all profit orders
        profit_orders_result = await db.ProfitOrders.delete_many({"store_id": store_id})
        deletion_summary["collections_affected"]["ProfitOrders"] = profit_orders_result.deleted_count
        
        # 6. Delete all loss orders
        loss_orders_result = await db.LossOrders.delete_many({"store_id": store_id})
        deletion_summary["collections_affected"]["LossOrders"] = loss_orders_result.deleted_count
        
        # 7. Delete all return orders
        return_orders_result = await db.ReturnOrders.delete_many({"store_id": store_id})
        deletion_summary["collections_affected"]["ReturnOrders"] = return_orders_result.deleted_count
        
        # 8. Delete all requested orders
        requested_orders_result = await db.RequestedOrders.delete_many({"store_id": store_id})
        deletion_summary["collections_affected"]["RequestedOrders"] = requested_orders_result.deleted_count
        
        # 9. Delete all purchase orders (if collection exists)
        try:
            purchase_orders_result = await db.PurchaseOrders.delete_many({"store_id": store_id})
            deletion_summary["collections_affected"]["PurchaseOrders"] = purchase_orders_result.deleted_count
        except Exception:
            deletion_summary["collections_affected"]["PurchaseOrders"] = 0
        
        # 10. Delete all notifications for this store
        notifications_result = await db.Notifications.delete_many({"sender.store_id": store_id})
        deletion_summary["collections_affected"]["Notifications"] = notifications_result.deleted_count
        
        # 11. Delete all vendors
        vendors_result = await db.Vendors.delete_many({"store_id": store_id})
        deletion_summary["collections_affected"]["Vendors"] = vendors_result.deleted_count
        
        # 12. Delete all contracts
        try:
            contracts_result = await db.Contracts.delete_many({"store_id": store_id})
            deletion_summary["collections_affected"]["Contracts"] = contracts_result.deleted_count
        except Exception:
            deletion_summary["collections_affected"]["Contracts"] = 0
        
        # 13. Delete all new inventory items
        try:
            new_inventory_result = await db.NewInventory.delete_many({"store_id": store_id})
            deletion_summary["collections_affected"]["NewInventory"] = new_inventory_result.deleted_count
        except Exception:
            deletion_summary["collections_affected"]["NewInventory"] = 0
        
        # 14. Finally, delete the store itself
        store_result = await db.Stores.delete_one({"store_id": store_id})
        deletion_summary["collections_affected"]["Stores"] = store_result.deleted_count
        
        # Calculate total records deleted
        total_deleted = sum(deletion_summary["collections_affected"].values())
        deletion_summary["total_records_deleted"] = total_deleted
        
        return {
            "message": f"Store {store_id} and all associated data deleted successfully",
            "summary": deletion_summary
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error during store deletion: {str(e)}"
        )
