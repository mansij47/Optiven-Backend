
# from fastapi import HTTPException
# from app.models.admin_model import Product, ProductItem  # Use Admin models for hierarchical structure
# from app.utils.auth import verify_password, create_access_token
# from app.db import db  
# from bson.objectid import ObjectId
# from datetime import datetime
# from app.utils.raise_order import _next_id


# async def add_product_service(product: Product):
#     try:
        
#         # Check if the product already exists
#         existing = await db.Inventory.find_one({"product_id": product.product_id})
#         if existing:
#             raise HTTPException(status_code=400, detail="Product with this ID already exists.")

#         # Insert the product into Inventory collection
#         product_dict = product.model_dump()
#         product_dict["created_at"] = datetime.utcnow()
#         product_dict["updated_at"] = datetime.utcnow()
        
#         await db.Inventory.insert_one(product_dict)

#         # Create ProductItems for each quantity unit (hierarchical structure)
#         quantity = product.quantity or 0
#         for i in range(quantity):
#             item_id = await _next_id(db.ProductItems, "item_id", "ITEM", product.store_id)
#             item_data = {
#                 "org_id": product.org_id,
#                 "store_id": product.store_id,
#                 "item_id": item_id,
#                 "product_id": product.product_id,
#                 "item_name": product.product_name,
#                 "unit_price": "0",  # Default, can be updated later
#                 "vendor_id": None,
#                 "vendor_name": None,
#                 "serial_no": None,
#                 "batch_number": None,
#                 "is_consumer_returnable": False,
#                 "consumer_return_conditions": [],
#                 "is_seller_returnable": False,
#                 "seller_return_conditions": [],
#                 "has_warranty": False,
#                 "warranty_tenure": 0,
#                 "warranty_unit": "months",
#                 "status": "available",
#                 "created_at": datetime.utcnow(),
#                 "updated_at": datetime.utcnow()
#             }
#             await db.ProductItems.insert_one(item_data)

#         return {
#             "message": "Product added successfully with items created",
#             "product_id": product.product_id,
#             "items_created": quantity
#         }

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error adding product: {str(e)}")
    


# async def get_all_products(store_id: str):
#     try:
#         products_cursor = db.Inventory.find({"store_id": store_id}, {"_id": 0})
#         products = []
#         async for product in products_cursor:
#             product_id = product.get("product_id")
            
#             # Count total items and available items from ProductItems collection
#             total_items = await db.ProductItems.count_documents({"product_id": product_id})
#             available_items = await db.ProductItems.count_documents({
#                 "product_id": product_id,
#                 "status": "available"
#             })
            
#             product["total_items"] = total_items
#             product["available_items"] = available_items
            
#             # Update quantity to match available items
#             product["quantity"] = available_items
            
#             # Calculate status based on available items
#             product["status"] = "Stock-in" if available_items > 0 else "Stock-out"
#             products.append(product)

#         return products
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error retrieving products: {str(e)}")
    

# async def get_product_by_id(product_id: str):
#     try:
#         product_data = await db.Inventory.find_one(
#             {"product_id": product_id},
#             {"_id": 0}  # Exclude MongoDB _id
#         )

#         if not product_data:
#             raise HTTPException(status_code=404, detail="Product not found")

#         # Get all items for this product from ProductItems collection
#         items_cursor = db.ProductItems.find({"product_id": product_id}, {"_id": 0})
#         items = await items_cursor.to_list(length=None)
        
#         # Count available items
#         available_items = sum(1 for item in items if item.get("status") == "available")
        
#         # Update product data with item counts
#         product_data["total_items"] = len(items)
#         product_data["available_items"] = available_items
#         product_data["quantity"] = available_items
#         product_data["status"] = "Stock-in" if available_items > 0 else "Stock-out"

#         return {
#             "product": product_data,
#             "items": items
#         }

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error retrieving product: {str(e)}")
    
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
    
# async def delete_product_service(product_id: str):
#     try:
#         result = await db.Inventory.delete_one({"product_id": product_id})
#         if result.deleted_count == 0:
#             raise HTTPException(status_code=404, detail="Product not found.")
#         return True
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error deleting product: {str(e)}")
    