from bson import ObjectId
from app.db import db  # adjust import to your project
from app.models.category_model import CategoryCreate, CategoryUpdate
from fastapi import HTTPException

categories_collection = db.Categories  # your MongoDB collection

async def create_category(data: CategoryCreate):
    existing = await categories_collection.find_one({"category_id": data.category_id})
    if existing:
        raise HTTPException(status_code=400, detail="Category ID already exists")
    
    category_dict = data.dict()
    result = await categories_collection.insert_one(category_dict)
    return { "message": "Category created", "id": str(result.inserted_id) }

async def get_all_categories():
    cursor = categories_collection.find()
    categories = []
    async for cat in cursor:
        cat["_id"] = str(cat["_id"])
        categories.append(cat)
    return categories

async def get_category_by_id(category_id: str):
    cat = await categories_collection.find_one({"category_id": category_id})
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    cat["_id"] = str(cat["_id"])
    return cat

async def update_category_by_id(category_id: str, update_data: CategoryUpdate):
    result = await categories_collection.update_one(
        {"category_id": category_id},
        {"$set": update_data.dict(exclude_unset=True)}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Category not found")
    return { "message": "Category updated successfully" }

async def delete_category_by_id(category_id: str):
    result = await categories_collection.delete_one({"category_id": category_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Category not found")
    return { "message": "Category deleted successfully" }