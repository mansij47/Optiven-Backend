from app.models.procurement_models import VendorModel
from datetime import datetime
from uuid import uuid4
from app.db import db  # Mongo connection
from bson import ObjectId
from fastapi import Request

VENDOR_COLLECTION = db.Vendors


def serialize_vendor(vendor: dict) -> dict:
    """Convert MongoDB ObjectId and datetime into serializable formats"""
    if not vendor:
        return None

    if "_id" in vendor and isinstance(vendor["_id"], ObjectId):
        vendor["_id"] = str(vendor["_id"])

    if "created_at" in vendor and isinstance(vendor["created_at"], datetime):
        vendor["created_at"] = vendor["created_at"].isoformat()

    if "updated_at" in vendor and isinstance(vendor["updated_at"], datetime):
        vendor["updated_at"] = vendor["updated_at"].isoformat()

    return vendor


# -------- CREATE ----------
async def create_vendor(vendor_data: VendorModel, request: Request):
    """Create vendor and auto-attach store_id, org_id, role from logged-in user"""
    user = request.state.user  # this assumes middleware sets request.state.user
    if not user:
        raise ValueError("User context missing. Ensure auth middleware is working.")

    vendor_dict = vendor_data.dict()
    vendor_dict["vendor_id"] = str(uuid4())  # or custom VEN001 pattern
    vendor_dict["created_at"] = datetime.utcnow()
    vendor_dict["updated_at"] = datetime.utcnow()

    # Auto attach values from logged-in user
    vendor_dict["store_id"] = str(user.get("store_id"))
    vendor_dict["org_id"] = str(user.get("org_id"))
    vendor_dict["role"] = user.get("role")

    await VENDOR_COLLECTION.insert_one(vendor_dict)
    return vendor_dict["vendor_id"]


# -------- READ ----------
async def get_all_vendors(request: Request):
    user = request.state.user
    query = {
        "store_id": str(user.get("store_id")),
        "org_id": str(user.get("org_id")),
    }
    vendors = await VENDOR_COLLECTION.find(query).to_list(100)
    return [serialize_vendor(v) for v in vendors]


async def get_vendor_by_id(vendor_id: str, request: Request):
    user = request.state.user
    vendor = await VENDOR_COLLECTION.find_one({
        "vendor_id": vendor_id,
        "store_id": str(user.get("store_id")),
        "org_id": str(user.get("org_id")),
    })
    return serialize_vendor(vendor)


# -------- UPDATE ----------
async def update_vendor(vendor_id: str, update_data: dict, request: Request):
    user = request.state.user
    update_data["updated_at"] = datetime.utcnow()

    result = await VENDOR_COLLECTION.update_one(
        {
            "vendor_id": vendor_id,
            "store_id": str(user.get("store_id")),
            "org_id": str(user.get("org_id")),
        },
        {"$set": update_data}
    )
    return result.modified_count


# -------- DELETE ----------
async def delete_vendor(vendor_id: str, request: Request):
    user = request.state.user
    result = await VENDOR_COLLECTION.delete_one({
        "vendor_id": vendor_id,
        "store_id": str(user.get("store_id")),
        "org_id": str(user.get("org_id")),
    })
    return result.deleted_count


#delete by objectId of vendor
# async def delete_vendor(vendor_id: str):
#     result = await VENDOR_COLLECTION.delete_one({"_id": ObjectId(vendor_id)})
#     return result.deleted_count
#     result = await VENDOR_COLLECTION.delete_one({"_id": ObjectId(vendor_id)})
#     return result.deleted_count
