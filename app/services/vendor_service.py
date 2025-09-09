from app.models.procurement_models import VendorModel
from datetime import datetime
from uuid import uuid4
from app.db import db  # Mongo connection
from bson import ObjectId
from fastapi import Request, Query

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
async def get_all_vendors(
    request: Request,
    search: str = Query(None),
    status: str = Query(None),
    statuses: list[str] = Query(None),
    date_from: str = Query(None),
    date_to: str = Query(None),
    page: int = 1,
    page_size: int = 5
):
    user = request.state.user
    query = {
        "store_id": str(user.get("store_id")),
        "org_id": str(user.get("org_id")),
    }

    # 🔎 Search filter
    if search:
        query["$or"] = [
            {"vendor_name": {"$regex": search, "$options": "i"}},
            {"vendor_id": {"$regex": search, "$options": "i"}},
        ]

    # 📌 Single status filter
    if status and status != "all":
        query["status"] = status

    # 📌 Multiple statuses filter
    if statuses and isinstance(statuses, list) and len(statuses) > 0:
        query["status"] = {"$in": statuses}

    # 📅 Date range filter (safe parsing)
    if date_from or date_to:
        query["created_at"] = {}

        if date_from:
            if isinstance(date_from, str):
                try:
                    query["created_at"]["$gte"] = datetime.fromisoformat(date_from)
                except ValueError:
                    pass  # ignore invalid format
            elif isinstance(date_from, datetime):
                query["created_at"]["$gte"] = date_from

        if date_to:
            if isinstance(date_to, str):
                try:
                    query["created_at"]["$lte"] = datetime.fromisoformat(date_to)
                except ValueError:
                    pass
            elif isinstance(date_to, datetime):
                query["created_at"]["$lte"] = date_to

    # 📄 Pagination with sorting
    skip = (page - 1) * page_size
    cursor = (
        VENDOR_COLLECTION.find(query)
        .sort("created_at", -1)  # latest first
        .skip(skip)
        .limit(page_size)
    )
    vendors = await cursor.to_list(length=page_size)

    total_count = await VENDOR_COLLECTION.count_documents(query)

    return {
        "data": [serialize_vendor(v) for v in vendors],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total_count,
            "pages": (total_count + page_size - 1) // page_size
        }
    }



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


