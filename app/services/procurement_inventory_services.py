
from fastapi import HTTPException
from app.models.procurement_models import Product
from app.utils.auth import verify_password, create_access_token
from app.db import db  
from bson.objectid import ObjectId


async def add_product_service(product: Product):
    try:
        
        # Check if the product already exists
        existing = await db.Inventory.find_one({"product_id": product.product_id})
        if existing:
            raise HTTPException(status_code=400, detail="Product with this ID already exists.")

        # Insert the product into the collection
        # product = product.model_dump()  
        # product["store_id"] = store_id
        await db.Inventory.insert_one(product.model_dump())

        return {
            "message": "Product added successfully",
            "product_id": product.product_id
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
            products.append(product)

        return products
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving products: {str(e)}")
    

async def get_product_by_id(product_id: str):
    try:
        product_data = await db.Inventory.find_one(
            {"product_id": product_id},
            {"_id": 0}  # Exclude MongoDB _id
        )

        raw_quantity = product_data.get("quantity", 0)
        try:
            quantity = int(raw_quantity)
        except (ValueError, TypeError):
            quantity = 0

        # Compute status without storing in DB
        status = "Stock-in" if quantity > 0 else "Stock-out"

        product = Product(**product_data)
        product.status = status

        return {"product": product.model_dump()}


    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving product: {str(e)}")
    
async def update_product_by_id(product_id: str, data: Product):
    try:
        update_data = {k: v for k, v in data.model_dump().items() if v is not None}

        if not update_data:
            raise HTTPException(status_code=400, detail="No update fields provided.")

        result = await db.Inventory.update_one(
            {"product_id": product_id},
            {"$set": update_data}
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Product not found.")

        return {"message": "Product updated successfully."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating product: {str(e)}")
    
async def delete_product_service(product_id: str):
    try:
        result = await db.Inventory.delete_one({"product_id": product_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Product not found.")
        return True
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting product: {str(e)}")
    