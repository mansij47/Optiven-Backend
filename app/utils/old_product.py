from fastapi import HTTPException
from app.db import db
from datetime import datetime, timedelta
from bson import ObjectId

# ✅ Get old products (handles string date format)
async def get_old_products(store_id: str, month: int = None, older_than_months: int = None):
    try:
        query = {"store_id": store_id}
        cursor = db.SalesOrders.find(query)
        all_products = await cursor.to_list(length=None)

        filtered_products = []
        now = datetime.now()
        print("Filtered Products:", filtered_products)
        # ✅ Case 1: If no filter (just store_id), return all products
        if not month and not older_than_months:
            for product in all_products:
                product["_id"] = str(product.get("_id"))
            return {
                "filtered_count": len(all_products),
                "total_count": len(all_products),
                "products": all_products,
                "store_id": store_id,
                "filter_type": "none",
                "filter_value": None
            }

        # ✅ Case 2: Filter by month or age
        for product in all_products:
            product["_id"] = str(product.get("_id"))

            last_updated_str = product.get("last_updated")
            if not last_updated_str:
                continue

            # --- Flexible datetime parsing ---
            last_updated_dt = None
            date_formats = [
                "%Y-%m-%dT%H:%M:%S.%fZ",   # ISO format with Z
                "%Y-%m-%dT%H:%M:%S.%f",    # ISO format without Z
                "%Y-%m-%dT%H:%M:%S",       # ISO format without microseconds
                "%Y-%m-%d %H:%M:%S.%f",    # space-separated with microseconds
                "%Y-%m-%d %H:%M:%S"        # space-separated without microseconds
            ]

            for fmt in date_formats:
                try:
                    last_updated_dt = datetime.strptime(last_updated_str, fmt)
                    break
                except Exception:
                    continue

            if not last_updated_dt:
                continue  # skip if none of the formats matched

            # --- Filtering logic ---
            if month and last_updated_dt.month == month:
                filtered_products.append(product)
            elif older_than_months:
                threshold_date = now - timedelta(days=older_than_months * 30)
                if last_updated_dt < threshold_date:
                    filtered_products.append(product)

        # ✅ Prepare response
        response = {
            "filtered_count": len(filtered_products),
            "total_count": len(all_products),
            "products": filtered_products,
            "store_id": store_id,
            "filter_type": "month" if month else "older_than",
            "filter_value": month or older_than_months
        }

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving old products: {str(e)}")

# ✅ Delete old products (handles string date format)
async def delete_old_products(store_id: str, month: int = None, older_than_months: int = None):
    try:
        query = {"store_id": store_id}
        cursor = db.SalesOrders.find(query)
        all_products = await cursor.to_list(length=None)

        to_delete_ids = []
        now = datetime.now()

        # ✅ Case 1: If no filter — delete all products from this store

        if not month and not older_than_months:
            all_ids = [ObjectId(str(p["_id"])) for p in all_products if "_id" in p]
            if not all_ids:
                return {
                    "deleted_count": 0,
                    "total_count": len(all_products),
                    "message": "No products found for this store",
                    "filter_type": "none",
                    "filter_value": None
                }
            result = await db.SalesOrders.delete_many({"_id": {"$in": all_ids}})
            return {
                "deleted_count": result.deleted_count,
                "total_count": len(all_products),
                "message": "All products deleted for this store",
                "filter_type": "none",
                "filter_value": None
            }

        # ✅ Case 2: Filtered deletion (month or older_than)
        date_formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S"
        ]

        for product in all_products:
            last_updated_str = product.get("last_updated")
            if not last_updated_str:
                continue

            last_updated_dt = None
            for fmt in date_formats:
                try:
                    last_updated_dt = datetime.strptime(last_updated_str, fmt)
                    break
                except Exception:
                    continue

            if not last_updated_dt:
                continue

            product_id = str(product["_id"]) if "_id" in product else None
            if not product_id:
                continue

            # --- Apply same filter logic ---
            if month and last_updated_dt.month == month:
                to_delete_ids.append(ObjectId(product_id))
            elif older_than_months:
                threshold_date = now - timedelta(days=older_than_months * 30)
                if last_updated_dt < threshold_date:
                    to_delete_ids.append(ObjectId(product_id))

        # ✅ Delete matching products
        if not to_delete_ids:
            return {
                "deleted_count": 0,
                "total_count": len(all_products),
                "message": "No products found matching the filter criteria",
                "filter_type": "month" if month else "older_than",
                "filter_value": month or older_than_months
            }

        result = await db.SalesOrders.delete_many({"_id": {"$in": to_delete_ids}})

        return {
            "deleted_count": result.deleted_count,
            "total_count": len(all_products),
            "message": "Filtered products deleted successfully",
            "filter_type": "month" if month else "older_than",
            "filter_value": month or older_than_months
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting old products: {str(e)}")

# for the salesorder deletion 
# import re
# async def delete_old_products(store_id: str, month: int = None, older_than_months: int = None):
#     try:
#         query = {"store_id": store_id}
#         cursor = db.SalesOrders.find(query)
#         all_products = await cursor.to_list(length=None)

#         to_delete_ids = []
#         now = datetime.now()

#         # ✅ Case 1: No filters — delete all
#         if not month and not older_than_months:
#             all_ids = [ObjectId(str(p["_id"])) for p in all_products if "_id" in p]
#             if not all_ids:
#                 return {
#                     "deleted_count": 0,
#                     "total_count": len(all_products),
#                     "message": "No products found for this store",
#                     "filter_type": "none",
#                     "filter_value": None
#                 }

#             result = await db.SalesOrders.delete_many({"_id": {"$in": all_ids}})
#             return {
#                 "deleted_count": result.deleted_count,
#                 "total_count": len(all_products),
#                 "message": "All products deleted for this store",
#                 "filter_type": "none",
#                 "filter_value": None
#             }

#         # ✅ Case 2: Filtered deletion (month or older_than)
#         date_fields = ["order_date", "created_at", "last_updated", "date"]
#         pattern = r"(\.\d+)?(\+\d{2}:\d{2}|Z)?$"  # to remove microseconds + timezone

#         for product in all_products:
#             date_str = None
#             for field in date_fields:
#                 if field in product:
#                     date_str = str(product[field])
#                     break

#             if not date_str:
#                 continue

#             # 🔹 Clean timezone and microseconds from string
#             clean_date_str = re.sub(pattern, "", date_str)

#             parsed_date = None
#             # Try both precise and fallback formats
#             for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
#                 try:
#                     parsed_date = datetime.strptime(clean_date_str, fmt)
#                     break
#                 except Exception:
#                     continue

#             if not parsed_date:
#                 print(f"⚠️ Still failed to parse: {date_str}")
#                 continue

#             # --- Apply filters ---
#             if month and parsed_date.month == int(month):
#                 to_delete_ids.append(ObjectId(product["_id"]))
#                 print(f"✅ Matched month {month}: {product['_id']} ({parsed_date})")

#             elif older_than_months:
#                 threshold_date = now - timedelta(days=older_than_months * 30)
#                 if parsed_date < threshold_date:
#                     to_delete_ids.append(ObjectId(product["_id"]))
#                     print(f"✅ Matched old product: {product['_id']} ({parsed_date})")

#         # ✅ Perform deletion
#         if not to_delete_ids:
#             print("⚠️ No matching products found for deletion.")
#             return {
#                 "deleted_count": 0,
#                 "total_count": len(all_products),
#                 "message": "No products found matching the filter criteria",
#                 "filter_type": "month" if month else "older_than",
#                 "filter_value": month or older_than_months
#             }

#         result = await db.SalesOrders.delete_many({"_id": {"$in": to_delete_ids}})
#         print(f"✅ Deleted {result.deleted_count} products.")

#         return {
#             "deleted_count": result.deleted_count,
#             "total_count": len(all_products),
#             "message": f"{result.deleted_count} product(s) deleted successfully",
#             "filter_type": "month" if month else "older_than",
#             "filter_value": month or older_than_months
#         }

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error deleting old products: {str(e)}")
