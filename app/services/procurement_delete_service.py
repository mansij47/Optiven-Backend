from bson import ObjectId
from app.db import db

ReturnToVendor = db.ReturnToVendor

class ReturnToVendorServices:
    async def delete_return_to_vendor(self, _id: str) -> int:
        """
        Delete a ReturnToVendor document by its ObjectId.
        Returns deleted_count (0 if not found, 1 if deleted).
        """
        if not ObjectId.is_valid(_id):
            return 0  # Invalid ObjectId format

        result = await ReturnToVendor.delete_one({"_id": ObjectId(_id)})
        return result.deleted_count

# Service instance
return_to_vendor_services = ReturnToVendorServices()
# ab sales wali delete karni hai
# from bson import ObjectId
# from app.db import db

# SalesOrders = db.SalesOrders  # point to SalesOrders collection

# class SalesOrderServices:
#     async def delete_sales_order(self, _id: str) -> int:
#         """
#         Delete a SalesOrder document by its ObjectId.
#         Returns deleted_count (0 if not found, 1 if deleted).
#         """
#         if not ObjectId.is_valid(_id):
#             return 0  # Invalid ObjectId format

#         result = await SalesOrders.delete_one({"_id": ObjectId(_id)})
#         return result.deleted_count

# # Service instance
# sales_order_services = SalesOrderServices()
