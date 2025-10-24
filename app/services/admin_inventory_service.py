from fastapi import HTTPException
from app.models.admin_model import Product
from app.db import db
import csv
import io
from fastapi.responses import StreamingResponse
from app.utils.raise_order import _next_id
from datetime import datetime, timedelta
from bson import ObjectId



async def add_product_service(product: Product, store_id: str, org_id: str):
    try:
        
        # Check if the product already exists
        new_product_id = await _next_id(db.Inventory, "product_id", "P", store_id)

        # Build the final product document
        product_dict = product.model_dump()
        product_dict["product_id"] = new_product_id
        product_dict["store_id"] = store_id
        product_dict["org_id"] = org_id

        # Insert the product into the collection
        await db.Inventory.insert_one(product_dict)

        return {
            "message": "Product added successfully",
            "product_id": new_product_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding product: {str(e)}")


async def get_all_products(store_id: str):
    try:
        # Sort products in reverse order (latest added first)
        products_cursor = (
            db["Inventory"].find({"store_id": store_id}, {"_id": 0})
            .sort("_id", -1)
        )

        products = []
        async for product in products_cursor:
            # Safely handle quantity
            try:
                quantity = int(product.get("quantity", 0))
            except (ValueError, TypeError):
                quantity = 0

            # Add computed stock status
            product["status"] = "Stock-in" if quantity > 0 else "Stock-out"

            # Ensure _id is removed if somehow included
            product.pop("_id", None)

            products.append(product)

        return products

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving products: {str(e)}")



async def get_product_by_id(product_id: str, store_id: str):
    try:
        product_data = await db.Inventory.find_one(
            {"product_id": product_id, "store_id": store_id},
            {"_id": 0}
        )

        if not product_data:
            raise HTTPException(status_code=404, detail="Product not found for this store.")


        raw_quantity = product_data.get("quantity", 0)
        try:
            quantity = int(raw_quantity)
        except (ValueError, TypeError):
            quantity = 0

        # Compute status without storing in DB
        status = "Stock-in" if quantity > 0 else "Stock-out"

        product = Product(**product_data)
        product.status = status

        # Remove _id if present
        product_dict = product.model_dump()
        if "_id" in product_dict:
            del product_dict["_id"]
        return {"product": product_dict}


    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving product: {str(e)}")
    

async def update_product_by_id(product_id: str, update_data: dict):
    
    product = await db["Inventory"].find_one({"product_id": product_id})

    if not product:
        raise HTTPException(status_code=404, detail="Product not found.")

    await db["Inventory"].update_one(
        {"product_id": product_id},
        {"$set": update_data}
    )

    updated = await db["Inventory"].find_one({"product_id": product_id})
    # Remove or convert _id before returning
    if updated and "_id" in updated:
        updated["_id"] = str(updated["_id"])
    return {"message": "Product updated", "data": updated}



async def delete_product_service(product_id: str):
    try:
        result = await db.Inventory.delete_one({"product_id": product_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Product not found.")
        return True
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting product: {str(e)}")
    

#export my inventory sheet
async def export_inventory_csv(store_id: str, org_id: str):
    cursor = db.Inventory.find({
        "store_id": store_id,
        "org_id": org_id
    })
    output = io.StringIO()
    writer = csv.writer(output)

    # Write CSV headers
    writer.writerow([
        "org_id", "store_id", "product_id", "product_name", "is_consumer_returnable",
        "consumer_return_conditions", "is_seller_returnable", "seller_return_conditions",
        "unit_price", "unit", "quantity", "category", "sub_category", "tags",
        "tax", "has_warranty", "warranty_tenure", "warranty_unit", "last_updated"
    ])

    async for doc in cursor:
        writer.writerow([
            doc.get("org_id", ""),
            doc.get("store_id", ""),
            doc.get("product_id", ""),
            doc.get("product_name", ""),
            doc.get("is_consumer_returnable", False),
            "|".join(doc.get("consumer_return_conditions") or []),
            doc.get("is_seller_returnable", False),
            "|".join(doc.get("seller_return_conditions") or []),
            doc.get("unit_price", "0"),
            doc.get("unit", ""),
            doc.get("quantity", 0),
            doc.get("category", ""),
            doc.get("sub_category", ""),
            "|".join(doc.get("tags") or []),
            doc.get("tax", 0.0),
            doc.get("has_warranty", False),
            doc.get("warranty_tenure", 0),
            doc.get("warranty_unit", ""),
            str(doc.get("last_updated", "")),  # convert datetime to string
        ])

    output.seek(0)
    return StreamingResponse(output, media_type="text/csv", headers={
        "Content-Disposition": "attachment; filename=inventory_export.csv"
    })
    
# ✅ Fetch old products based on month or “older than” filter
# ✅ Get old products (handles string date format)
async def get_old_products(store_id: str, month: int = None, older_than_months: int = None):
    try:
        query = {"store_id": store_id}
        cursor = db.Inventory.find(query)
        all_products = await cursor.to_list(length=None)

        filtered_products = []
        now = datetime.now()

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
        cursor = db.Inventory.find(query)
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

            result = await db.Inventory.delete_many({"_id": {"$in": all_ids}})
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

        result = await db.Inventory.delete_many({"_id": {"$in": to_delete_ids}})

        return {
            "deleted_count": result.deleted_count,
            "total_count": len(all_products),
            "message": "Filtered products deleted successfully",
            "filter_type": "month" if month else "older_than",
            "filter_value": month or older_than_months
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting old products: {str(e)}")