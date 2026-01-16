from bson import ObjectId
from datetime import datetime


async def delete_by_object_id(collection, object_id: str) -> int:
    """
    Common function to delete a document from any collection by its ObjectId.
    
    Args:
        collection: MongoDB collection object (e.g., db.SalesOrders, db.Vendors)
        object_id: String representation of the ObjectId to delete
    
    Returns:
        int: deleted_count (0 if not found or invalid ObjectId, 1 if deleted successfully)
    
    Usage:
        from app.db import db
        await delete_by_object_id(db.SalesOrders, "507f1f77bcf86cd799439011")
        await delete_by_object_id(db.Vendors, vendor_id)
        await delete_by_object_id(db.ReturnToVendor, return_id)
    """
    if not ObjectId.is_valid(object_id):
        return 0  # Invalid ObjectId format

    result = await collection.delete_one({"_id": ObjectId(object_id)})
    return result.deleted_count


async def delete_by_store_id(collection, store_id: str) -> int:
    """
    Delete all documents from a collection that belong to a specific store.
    
    Args:
        collection: MongoDB collection object (e.g., db.SalesOrders, db.Inventory, db.PurchaseOrders)
        store_id: The store ID to filter by (e.g., "St258")
    
    Returns:
        int: deleted_count (number of documents deleted)
    
    Usage:
        from app.db import db
        # Delete all sales orders for store St258
        count = await delete_by_store_id(db.SalesOrders, "St258")
        
        # Delete all inventory items for store St100
        count = await delete_by_store_id(db.Inventory, "St100")
        
        # Delete all purchase orders for store St258
        count = await delete_by_store_id(db.PurchaseOrders, "St258")
    """
    result = await collection.delete_many({"store_id": store_id})
    return result.deleted_count

