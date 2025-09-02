from datetime import datetime
from fastapi import HTTPException, Request
from uuid import uuid4
from bson import ObjectId
from app.db import db  # Mongo connection

INVENTORY_COLLECTION = db.NewInventory  # set this from your db in main.py


async def create_inventory(inventory_data: dict, request: Request):
    """Create inventory record with unique sku_id and auto-attach org/store/role"""
    user = request.state.user
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    doc = inventory_data
    doc["sku_id"] = str(uuid4())   # unique ID for this product family
    doc["created_at"] = datetime.utcnow()
    doc["updated_at"] = datetime.utcnow()

    # auto attach from logged-in user
    doc["store_id"] = str(user.get("store_id"))
    doc["org_id"] = str(user.get("org_id"))
    doc["role"] = user.get("role")

    await INVENTORY_COLLECTION.insert_one(doc)
    return doc["sku_id"]


async def update_inventory(sku_id: str, update_data: dict, request: Request):
    """Update inventory item by sku_id"""
    user = request.state.user
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    update_data["updated_at"] = datetime.utcnow()
    result = await INVENTORY_COLLECTION.update_one(
        {"sku_id": sku_id, "org_id": user.get("org_id"), "store_id": user.get("store_id")},
        {"$set": update_data}
    )
    return result.modified_count


async def get_all_inventory(request: Request):
    """Fetch all inventory items for the org/store of logged-in user"""
    user = request.state.user
    cursor = INVENTORY_COLLECTION.find({"org_id": user.get("org_id"), "store_id": user.get("store_id")})
    items = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        items.append(doc)
    return items


async def get_inventory_by_id(sku_id: str, request: Request):
    """Fetch single inventory item by sku_id"""
    user = request.state.user
    doc = await INVENTORY_COLLECTION.find_one(
        {"sku_id": sku_id, "org_id": user.get("org_id"), "store_id": user.get("store_id")}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    doc["_id"] = str(doc["_id"])
    return doc


async def delete_inventory(sku_id: str, request: Request):
    """Delete inventory item by sku_id"""
    user = request.state.user
    result = await INVENTORY_COLLECTION.delete_one(
        {"sku_id": sku_id, "org_id": user.get("org_id"), "store_id": user.get("store_id")}
    )
    return result.deleted_count
