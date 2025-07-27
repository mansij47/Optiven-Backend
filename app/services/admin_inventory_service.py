from fastapi import HTTPException
from app.models.admin_model import Product
from app.db import db
import csv
import io
from fastapi.responses import StreamingResponse
from app.utils.raise_order import _next_id


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
        products_cursor = db.Inventory.find({"store_id": store_id}, {"_id": 0})
        products = []
        async for product in products_cursor:
           
            # product["_id"] = str(product["_id"])  # Convert ObjectId to string
            
            try:
                quantity = int(product.get("quantity", 0))
            except (ValueError, TypeError):
                quantity = 0

            product["status"] = "Stock-in" if quantity > 0 else "Stock-out"
            # Remove _id if present
            if "_id" in product:
                del product["_id"]
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
    

# async def update_product_by_id(product_id: str, data: Product):
#     try:
#         update_data = {k: v for k, v in data.model_dump().items() if v is not None}

#         if not update_data:
#             raise HTTPException(status_code=400, detail="No update fields provided.")

#         result = await db.Inventory.update_one(
#             {"product_id": product_id},
#             {"$set": update_data}
#         )

#         if result.matched_count == 0:
#             raise HTTPException(status_code=404, detail="Product not found.")

#         return {"message": "Product updated successfully."}

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error updating product: {str(e)}")
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