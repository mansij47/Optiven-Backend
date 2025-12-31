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

