from fastapi import HTTPException
from app.models.admin_model import Product
from app.db import db
import csv
import io
from fastapi.responses import StreamingResponse
from app.utils.raise_order import _next_id
from datetime import datetime, timedelta
from bson import ObjectId



# async def add_product_service(product: Product, store_id: str, org_id: str):
#     try:
        
#         # Check if the product already exists
#         new_product_id = await _next_id(db.Inventory, "product_id", "P", store_id)

#         # Build the final product document
#         product_dict = product.model_dump()
#         product_dict["product_id"] = new_product_id
#         product_dict["store_id"] = store_id
#         product_dict["org_id"] = org_id

#         # Insert the product into the collection
#         await db.Inventory.insert_one(product_dict)

#         return {
#             "message": "Product added successfully",
#             "product_id": new_product_id
#         }

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error adding product: {str(e)}")


# async def get_all_products(store_id: str):
#     try:
#         # Sort products in reverse order (latest added first)
#         products_cursor = (
#             db["Inventory"].find({"store_id": store_id}, {"_id": 0})
#             .sort("_id", -1)
#         )

#         products = []
#         async for product in products_cursor:
#             # Safely handle quantity
#             try:
#                 quantity = int(product.get("quantity", 0))
#             except (ValueError, TypeError):
#                 quantity = 0

#             # Add computed stock status
#             product["status"] = "Stock-in" if quantity > 0 else "Stock-out"

#             # Ensure _id is removed if somehow included
#             product.pop("_id", None)

#             products.append(product)

#         return products

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error retrieving products: {str(e)}")



# async def get_product_by_id(product_id: str, store_id: str):
#     try:
#         product_data = await db.Inventory.find_one(
#             {"product_id": product_id, "store_id": store_id},
#             {"_id": 0}
#         )

#         if not product_data:
#             raise HTTPException(status_code=404, detail="Product not found for this store.")


#         raw_quantity = product_data.get("quantity", 0)
#         try:
#             quantity = int(raw_quantity)
#         except (ValueError, TypeError):
#             quantity = 0

#         # Compute status without storing in DB
#         status = "Stock-in" if quantity > 0 else "Stock-out"

#         product = Product(**product_data)
#         product.status = status

#         # Remove _id if present
#         product_dict = product.model_dump()
#         if "_id" in product_dict:
#             del product_dict["_id"]
#         return {"product": product_dict}


#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error retrieving product: {str(e)}")
    

# async def update_product_by_id(product_id: str, update_data: dict):
    
#     product = await db["Inventory"].find_one({"product_id": product_id})

#     if not product:
#         raise HTTPException(status_code=404, detail="Product not found.")

#     await db["Inventory"].update_one(
#         {"product_id": product_id},
#         {"$set": update_data}
#     )

#     updated = await db["Inventory"].find_one({"product_id": product_id})
#     # Remove or convert _id before returning
#     if updated and "_id" in updated:
#         updated["_id"] = str(updated["_id"])
#     return {"message": "Product updated", "data": updated}



# async def delete_product_service(product_id: str):
#     try:
#         result = await db.Inventory.delete_one({"product_id": product_id})
#         if result.deleted_count == 0:
#             raise HTTPException(status_code=404, detail="Product not found.")
#         return True
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error deleting product: {str(e)}")
    

# #export my inventory sheet
# async def export_inventory_csv(store_id: str, org_id: str):
#     cursor = db.Inventory.find({
#         "store_id": store_id,
#         "org_id": org_id
#     })
#     output = io.StringIO()
#     writer = csv.writer(output)

#     # Write CSV headers
#     writer.writerow([
#         "org_id", "store_id", "product_id", "product_name", "is_consumer_returnable",
#         "consumer_return_conditions", "is_seller_returnable", "seller_return_conditions",
#         "unit_price", "unit", "quantity", "category", "sub_category", "tags",
#         "tax", "has_warranty", "warranty_tenure", "warranty_unit", "last_updated"
#     ])

#     async for doc in cursor:
#         writer.writerow([
#             doc.get("org_id", ""),
#             doc.get("store_id", ""),
#             doc.get("product_id", ""),
#             doc.get("product_name", ""),
#             doc.get("is_consumer_returnable", False),
#             "|".join(doc.get("consumer_return_conditions") or []),
#             doc.get("is_seller_returnable", False),
#             "|".join(doc.get("seller_return_conditions") or []),
#             doc.get("unit_price", "0"),
#             doc.get("unit", ""),
#             doc.get("quantity", 0),
#             doc.get("category", ""),
#             doc.get("sub_category", ""),
#             "|".join(doc.get("tags") or []),
#             doc.get("tax", 0.0),
#             doc.get("has_warranty", False),
#             doc.get("warranty_tenure", 0),
#             doc.get("warranty_unit", ""),
#             str(doc.get("last_updated", "")),  # convert datetime to string
#         ])

#     output.seek(0)
#     return StreamingResponse(output, media_type="text/csv", headers={
#         "Content-Disposition": "attachment; filename=inventory_export.csv"
    # })
    #new add product service start here

# ✅ Helper to generate readable timestamp
def current_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ✅ 1. Add or Update Product
async def add_product_service(product: Product, store_id: str, org_id: str):
    try:
        product_dict = product.model_dump()

        # Check if product already exists in same store
        existing_product = await db.Inventory.find_one({
            "store_id": store_id,
            "product_name": product_dict["product_name"]
        })

        # ✅ If product exists — Update its quantity
        if existing_product:
            new_quantity = existing_product.get("quantity", 0) + product_dict.get("quantity", 0)

            await db.Inventory.update_one(
                {"_id": existing_product["_id"]},
                {
                    "$set": {
                        "quantity": new_quantity,
                        "last_updated": current_timestamp()  # 👈 formatted date
                    }
                }
            )

            return {
                "message": f"Existing product '{product_dict['product_name']}' updated successfully",
                "product_id": existing_product["product_id"],
                "updated_quantity": new_quantity
            }

        # ✅ If new product — Create new one
        new_product_id = await _next_id(db.Inventory, "product_id", "P", store_id)

        product_dict["product_id"] = new_product_id
        product_dict["store_id"] = store_id
        product_dict["org_id"] = org_id
        product_dict["last_updated"] = current_timestamp()  # 👈 formatted date

        await db.Inventory.insert_one(product_dict)

        return {
            "message": "New product added successfully",
            "product_id": new_product_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding product: {str(e)}")


# ✅ 2. Get All Products
async def get_all_products(store_id: str):
    try:
        products_cursor = (
            db["Inventory"].find({"store_id": store_id}, {"_id": 0})
            .sort("last_updated", -1)
        )

        products = []
        async for product in products_cursor:
            try:
                quantity = int(product.get("quantity", 0))
            except (ValueError, TypeError):
                quantity = 0

            product["status"] = "Stock-in" if quantity > 0 else "Stock-out"
            product["last_updated"] = product.get("last_updated", current_timestamp())
            product.pop("_id", None)

            products.append(product)

        return {
            "total_count": len(products),
            "store_id": store_id,
            "products": products,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving products: {str(e)}")


# ✅ 3. Get Product by ID
async def get_product_by_id(product_id: str, store_id: str):
    try:
        product_data = await db.Inventory.find_one(
            {"product_id": product_id, "store_id": store_id},
            {"_id": 0}
        )

        if not product_data:
            raise HTTPException(status_code=404, detail="Product not found for this store.")

        try:
            quantity = int(product_data.get("quantity", 0))
        except (ValueError, TypeError):
            quantity = 0

        status = "Stock-in" if quantity > 0 else "Stock-out"
        product_data["status"] = status
        product_data["last_updated"] = product_data.get("last_updated", current_timestamp())

        product = Product(**product_data)
        product_dict = product.model_dump()
        product_dict.pop("_id", None)

        return {"product": product_dict}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving product: {str(e)}")


# ✅ 4. Update Product by ID
async def update_product_by_id(product_id: str, update_data: dict, store_id: str = None):
    try:
        query = {"product_id": product_id}
        if store_id:
            query["store_id"] = store_id

        product = await db["Inventory"].find_one(query)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found.")

        update_data["last_updated"] = current_timestamp()  # 👈 formatted date
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


# ✅ 5. Delete Product
async def delete_product_service(product_id: str, store_id: str = None):
    try:
        query = {"product_id": product_id}
        if store_id:
            query["store_id"] = store_id

        result = await db.Inventory.delete_one(query)
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Product not found.")

        return {
            "message": "Product deleted successfully",
            "deleted_product_id": product_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting product: {str(e)}")


# ✅ 6. Export Inventory CSV
async def export_inventory_csv(store_id: str, org_id: str):
    try:
        cursor = db.Inventory.find({
            "store_id": store_id,
            "org_id": org_id
        })

        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow([
            "org_id", "store_id", "product_id", "product_name", "is_consumer_returnable",
            "consumer_return_conditions", "is_seller_returnable", "seller_return_conditions",
            "unit_price", "unit", "quantity", "category", "sub_category", "tags",
            "tax", "has_warranty", "warranty_tenure", "warranty_unit",
            "status", "last_updated"
        ])

        async for doc in cursor:
            quantity = int(doc.get("quantity", 0)) if doc.get("quantity") else 0
            status = "Stock-in" if quantity > 0 else "Stock-out"

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
                quantity,
                doc.get("category", ""),
                doc.get("sub_category", ""),
                "|".join(doc.get("tags") or []),
                doc.get("tax", 0.0),
                doc.get("has_warranty", False),
                doc.get("warranty_tenure", 0),
                doc.get("warranty_unit", ""),
                status,
                doc.get("last_updated", current_timestamp()),  # 👈 formatted date
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
