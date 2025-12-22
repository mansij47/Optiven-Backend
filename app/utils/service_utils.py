from bson import ObjectId
from app.db import db
from datetime import datetime

ReturnToVendor = db.ReturnToVendor
SalesOrders = db.SalesOrders  # point to SalesOrders collection
VENDOR_COLLECTION = db.Vendors  # point to Vendors collection


# Delete ReturnToVendor by ObjectId
async def delete_return_to_vendor(_id: str) -> int:
    """
    Delete a ReturnToVendor document by its ObjectId.
    Returns deleted_count (0 if not found, 1 if deleted).
    """
    if not ObjectId.is_valid(_id):
        return 0  # Invalid ObjectId format

    result = await ReturnToVendor.delete_one({"_id": ObjectId(_id)})
    return result.deleted_count


# Delete SalesOrder by ObjectId
async def delete_sales_order(_id: str) -> int:
    """
    Delete a SalesOrder document by its ObjectId.
    Returns deleted_count (0 if not found, 1 if deleted).
    """
    if not ObjectId.is_valid(_id):
        return 0  # Invalid ObjectId format

    result = await SalesOrders.delete_one({"_id": ObjectId(_id)})
    return result.deleted_count


# Delete Vendor by ObjectId
async def delete_vendor(vendor_id: str) -> int:
    """
    Delete a Vendor document by its ObjectId.
    Returns deleted_count (0 if not found, 1 if deleted).
    """
    if not ObjectId.is_valid(vendor_id):
        return 0  # Invalid ObjectId format
    
    result = await VENDOR_COLLECTION.delete_one({"_id": ObjectId(vendor_id)})
    return result.deleted_count

