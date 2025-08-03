from datetime import datetime
from typing import Dict, Any, Optional, List
import uuid
from fastapi import HTTPException, Request
from bson import ObjectId

from app.db import db
from app.utils.auth import hash_password, verify_password, create_access_token
from app.models.super_admin_models import (
    SignupModel, StoreUpdate, SuperAdminSignupModel, UpdateProfileModel, ChangePasswordModel,
    CreateStoreModel, EditStoreModel, UpdateStoreStatusModel,
    AddCategoryModel, EditCategoryModel,
    AddSubcategoryModel, EditSubcategoryModel,
    StoreInvitationModel, HelpModel, UpdateUserModel, UserModel
)
from app.utils.email_utils import send_welcome_email

# ───────────────────────── ID helper
async def _next_id(col, field_: str, prefix: str) -> str:
    last = await col.find_one({field_: {"$regex": f"^{prefix}\\d+$"}}, sort=[(field_, -1)])
    if not last:
        return f"{prefix}001"
    next_num = int(last[field_][len(prefix):]) + 1
    return f"{prefix}{str(next_num).zfill(3)}"

# ───────────────────────── AUTH
async def signup(data:SignupModel) -> Dict[str, Any]:
    if await db.Users.find_one({"email": data.email}, {"_id": 0}):
        return {"error": "Email already registered"}

    doc = data.model_dump()
    doc["password"] = hash_password(doc["password"])
    now = datetime.utcnow().isoformat()
    doc["created_at"] = now
    doc["updated_at"] = now

    saved = await db.Users.insert_one(doc)

    token = create_access_token({
        "email": doc["email"],
        "id": str(saved.inserted_id),
        "role": "super_admin"
    })

    return {
        "message": "Signup successful",
        "id": str(saved.inserted_id),
        "access_token": token,
        "token_type": "bearer"
    }

async def login(email: str, password: str) -> Optional[Dict[str, Any]]:
    admin = await db.Users.find_one({"email": email})
    role= admin.get("role") if admin else None
    if not admin or not verify_password(password, admin["password"]):
        return None

    token = create_access_token({
        "email": email,
        "id": str(admin["_id"]),
        "role": role,
        "store_id": admin.get("store_id", ""),
        "org_id": admin.get("org_id", "")
    })
    return {"access_token": token, "token_type": "bearer"}
    
# async def get_me_from_users(user_id: str, email: str):
#     try:
#         user = await db.Users.find_one(
#             {"id": user_id, "email": email},
#             {"password": 0, "_id": 0}  # hiding sensitive fields
#         )
#         return user
#     except Exception as e:
#         return {"error": f"Failed to fetch user: {str(e)}"}

async def fetch_user(request):
    user = request.state.user
    user_id = user.get("email")
    res = await db.Users.find_one({"email": user_id}, {"_id":0})
    if not res:
        return HTTPException(401, "User not zFound")
    res.pop("password", None)  #Remove password from response
    if not res:
        return None
    return res

async def update_user_by_id(user_id: str, data: UpdateUserModel) -> bool:
    update_doc = data.model_dump(exclude_none=True)
    update_doc["updated_at"] = datetime.utcnow().isoformat()
    if not update_doc:
        return False
    result = await db.Users.update_one(
        {"id": user_id},
        {"$set": update_doc}
    )
    return result.modified_count > 0

# ───────────────────────── PROFILE
async def get_profile(email: str):
    return await db.Users.find_one({"email": email}, {"password": 0, "_id": 0})

async def update_profile(email: str, payload: UpdateProfileModel) -> int:
    res = await db.Users.update_one(
        {"email": email},
        {"$set": payload.model_dump(exclude_none=True) | {"updated_at": datetime.utcnow().isoformat()}}
    )
    return res.modified_count

async def change_password(email: str, old_pw: str, new_pw: str) -> Dict[str, str]:
    admin = await db.Users.find_one({"email": email})
    if not admin or not verify_password(old_pw, admin["password"]):
        return {"error": "Incorrect current password"}
    await db.Users.update_one(
        {"email": email},
        {"$set": {"password": hash_password(new_pw), "updated_at": datetime.utcnow().isoformat()}}
    )
    return {"message": "Password updated"}

# ───────────────────────── DASHBOARD
async def get_dashboard_overview(_: Dict[str, Any]):
    total = await db.Stores.count_documents({})
    active = await db.Stores.count_documents({"status": 1})
    disabled = await db.Stores.count_documents({"status": 2})
    draft = total - active - disabled
    return {"total": total, "active": active, "disabled": disabled, "draft": draft}

# ───────────────────────── STORE
async def get_stores():                        # list
    return await db.Stores.find({}, {"_id": 0}).to_list(1000)

# async def create_store(data: CreateStoreModel) -> str:
#     doc = data.model_dump()
#     if await db.Stores.find_one({"store_id": doc["store_id"]}):
#         doc["store_id"] = await _next_id(db.Stores, "store_id", "ST")
#     now = datetime.utcnow().isoformat()
#     doc["created_at"] = now
#     doc["updated_at"] = now
#     result = await db.Stores.insert_one(doc)
#     store_id = doc["store_id"]

#     # Adding to users collection
#     user_doc = {
#         "id": doc.get("admin_id"),
#         "org_id": doc.get("org_id"),
#         "store_id": [store_id],
#         "password": hash_password(doc.get("password", "")),
#         "email": doc.get("email"),
#         "role": "admin",
#         "name": doc.get("admin_name"),
#         "joining_date": now,
#         "termination_date": now,
#         "status": 0  # 0: active, 1: disabled, 2: draft
#     }
#     await db.Users.insert_one(user_doc)
#     # print("User document to be inserted:", user_doc)
#     return store_id

async def create_store(data: CreateStoreModel, send_email) :
    doc = data.model_dump()
    org_id = uuid.uuid4()
    # Ensure unique store_id
    if await db.Stores.find_one({"store_id": doc["store_id"]}):
        doc["store_id"] = await _next_id(db.Stores, "store_id", "ST")
        doc["org_id"] = str(org_id)  # Generate a new org_id if store_id is new
    # now = datetime.utcnow().isoformat()
    now = datetime.utcnow()
    doc["created_at"] = now
    doc["updated_at"] = now
    result = await db.Stores.insert_one(doc)
    store_id = doc["store_id"]
    password = doc.get("password", "")

    user_model = UserModel(
        id=doc.get("admin_id"),
        org_id=str(org_id) ,
        store_id=store_id,
        password=hash_password(password),
        phone=doc.get("address", {}).get("phone"),  # ✅ Fix,
        email=doc.get("store_email"),
        name=doc.get("admin_name"),
        joining_date=now
    )

    await db.Users.insert_one(user_model.model_dump())

    # If email is True, send credentials
    if send_email:
        try:
            res = send_welcome_email(to_email=doc.get("store_email"), password=doc.get("password"))
            print("Email sent status:", res)
            if not res:
                raise HTTPException(status_code=500, detail="Failed to send welcome email")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to send credentials: {str(e)}")
    
    return {
        "store_id": store_id,
        "store_email": doc.get("store_email"),
        "password": password
    }

# async def get_store_by_id(store_id: str):
#     return await db.Stores.find_one({"store_id": store_id}, {"_id": 0})

# async def get_store_by_id(store_id: str):
#     store = await db.Stores.find_one({"store_id": store_id}, {"_id": 0})
#     if not store:
#         return None

#     # Get category and subcategory IDs from store
#     category_ids = store.get("category_ids", [])
#     subcategory_ids = store.get("subcategory_ids", [])

#     # Fetch matching documents from Categories collection
#     all_matches = []
#     if category_ids or subcategory_ids:
#         all_matches_cursor = db.Categories.find({
#             "$or": [
#                 {"category_id": {"$in": category_ids}},
#                 {"sub_category_id": {"$in": subcategory_ids}}
#             ]
#         }, {"_id": 0})
#         all_matches = await all_matches_cursor.to_list(length=None)

#     # Separate categories and subcategories
#     categories = []
#     subcategories = []
#     for doc in all_matches:
#         if "sub_category_id" in doc:
#             subcategories.append(doc)
#         else:
#             categories.append(doc)

#     # Attach to store
#     store["categories"] = categories
#     store["subcategories"] = subcategories

    # return store

async def get_store_by_id(store_id: str):
    store = await db.Stores.find_one({"store_id": store_id}, {"_id": 0})
    if not store:
        return None

    category_ids = store.get("category_ids", [])
    subcategory_ids = store.get("subcategory_ids", [])

    # Fetch relevant category documents
    categories_cursor = db.Categories.find(
        {"category_id": {"$in": category_ids}}, {"_id": 0, "sub_categories": 1, "category_name": 1, "category_id": 1}
    )
    categories = await categories_cursor.to_list(length=None)

    # Extract only matching subcategories
    filtered_subcategories = []
    filtered_categories = []
    for cat in categories:
        filtered_categories.append({
            "category_id": cat["category_id"],
            "category_name": cat["category_name"]
        })
        for sub in cat.get("sub_categories", []):
            if sub["sub_category_id"] in subcategory_ids:
                filtered_subcategories.append(sub)

    # Add full category objects + filtered subcategories to response
    store["categories"] = filtered_categories
    store["subcategories"] = filtered_subcategories

    return store


async def edit_store(store_id: str, data: StoreUpdate) -> int:
    update_data = data.model_dump(exclude_none=True)
    update_data["updated_at"] = datetime.utcnow().isoformat()

    update_query = {
        "$set": update_data  # ✅ Set everything including empty arrays
    }

    res = await db.Stores.update_one({"store_id": store_id}, update_query)
    return res.modified_count

async def delete_store(store_id: str) -> int:
    res = await db.Stores.delete_one({"store_id": store_id})
    return res.deleted_count

async def delete_multiple_stores(store_ids: List[str]) -> int:
    res = await db.Stores.delete_many({"store_id": {"$in": store_ids}})
    return res.deleted_count

async def update_store_status(store_id: str, status: int)-> int:
    res = await db.Stores.update_one({"store_id": store_id}, {"$set": {"status": status}})
    return res.modified_count

# ───────────────────────── CATEGORY / SUBCATEGORY
async def get_categories(store_id: str) -> List[Dict[str, Any]]:
    store = await db.Stores.find_one({"store_id": store_id})
    if not store:
        return []

    # Extract category IDs from list of dicts
    category_dicts = store.get("category_ids", [])
    category_ids = [cat["id"] for cat in category_dicts if "id" in cat]

    if not category_ids:
        return []

    # Query the categories collection
    categories = await db.Categories.find(
        {"category_id": {"$in": category_ids}},
        {"_id": 0}
    ).to_list(length=None)

    return categories

async def get_category_by_id(category_id: str) -> Optional[Dict[str, Any]]:
    return await db.Categories.find_one({"category_id": category_id}, {"_id": 0})

async def get_all_categories() -> List[Dict[str, Any]]:
    categories = await db.Categories.find({}, {"_id": 0}).to_list(1000)

    for category in categories:
        category["sub_category_count"] = len(category.get("sub_categories", []))
    
    return categories

# async def add_category(store_id: str, data: AddCategoryModel) -> str:
#     doc = data.model_dump()
#     if await db.Categories.find_one({"category_id": doc["category_id"]}):
#         doc["category_id"] = await _next_id(db.Categories, "category_id", "CAT")
#     ts = datetime.utcnow().isoformat()
#     doc |= {"store_id": store_id, "created_at": ts, "updated_at": ts}
#     await db.Categories.insert_one(doc)
#     return doc["category_id"]

# async def create_category(data: AddCategoryModel) -> str:
#     doc = data.model_dump()
#     if await db.Categories.find_one({"category_id": doc["category_id"]}):
#         doc["category_id"] = await _next_id(db.Categories, "category_id", "CAT")
#     ts = datetime.utcnow().isoformat()
#     doc |= {"created_at": ts, "updated_at": ts}
#     await db.Categories.insert_one(doc)
#     return doc["category_id"]

async def create_category(data: AddCategoryModel) -> str:
    doc = data.model_dump(exclude_unset=True)

    # If category_id is not provided or already exists, generate a new one
    if not doc.get("category_id") or await db.Categories.find_one({"category_id": doc.get("category_id")}):
        doc["category_id"] = await _next_id(db.Categories, "category_id", "CAT")

    # Auto-calculate sub_category_count
    doc["sub_category_count"] = len(doc.get("sub_categories", []))

    # Add timestamps
    ts = datetime.utcnow().isoformat()
    doc["created_at"] = ts
    doc["updated_at"] = ts

    await db.Categories.insert_one(doc)
    return doc["category_id"]

async def edit_category(category_id: str, data: EditCategoryModel) -> int:
    update_data = data.model_dump(exclude_none=True)

    # ✅ Recalculate sub_category_count if sub_categories are being updated
    if "sub_categories" in update_data:
        update_data["sub_category_count"] = len(update_data["sub_categories"])

    update_data["updated_at"] = datetime.utcnow().isoformat()

    res = await db.Categories.update_one(
        {"category_id": category_id},
        {"$set": update_data}
    )
    return res.modified_count

# async def edit_category(category_id: str, data: EditCategoryModel) -> int:
#     res = await db.Categories.update_one(
#         {"category_id": category_id},
#         {"$set": data.model_dump(exclude_none=True) | {"updated_at": datetime.utcnow().isoformat()}}
#     )
#     return res.modified_count

async def delete_category(category_id: str) -> int:
    res = await db.Categories.delete_one({"category_id": category_id})
    return res.deleted_count

async def add_subcategory(category_id: str, data: AddSubcategoryModel) -> str:
    cat = await db.Categories.find_one({"category_id": category_id}, {"sub_categories": 1})
    existing = {sc["sub_category_id"] for sc in cat.get("sub_categories", [])}
    sub_id = data.sub_category_id
    if sub_id in existing:
        nums = [int(i[3:]) for i in existing if i.startswith("SUB") and i[3:].isdigit()]
        sub_id = f"SUB{str(max(nums)+1 if nums else 1).zfill(3)}"
    sub_doc = data.model_dump() | {
        "sub_category_id": sub_id,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }
    await db.Categories.update_one(
        {"category_id": category_id},
        {"$push": {"sub_categories": sub_doc},
         "$set": {"updated_at": sub_doc["updated_at"]}}
    )
    return sub_id

async def edit_subcategory(sub_id: str, data: EditSubcategoryModel) -> int:
    update_fields = {f"sub_categories.$.{k}": v for k, v in data.model_dump(exclude_none=True).items()}
    update_fields["sub_categories.$.updated_at"] = datetime.utcnow().isoformat()
    res = await db.Categories.update_one(
        {"sub_categories.sub_category_id": sub_id},
        {"$set": update_fields}
    )
    return res.modified_count

async def delete_subcategory(sub_id: str) -> int:
    res = await db.Categories.update_one(
        {}, {"$pull": {"sub_categories": {"sub_category_id": sub_id}}}
    )
    return res.modified_count

async def delete_subcategory_from_category(category_id: str, sub_category_id: str) -> bool:
    category = await db.Categories.find_one({"category_id": category_id})
    if not category:
        return False

    original_count = len(category.get("sub_categories", []))
    updated_subcategories = [
        sub for sub in category["sub_categories"]
        if sub["sub_category_id"] != sub_category_id
    ]

    if len(updated_subcategories) == original_count:
        return False  # No subcategory removed

    await db.Categories.update_one(
        {"category_id": category_id},
        {
            "$set": {
            "sub_categories": updated_subcategories,
            "sub_category_count": len(updated_subcategories),  # ✅ update count
            "updated_at": datetime.utcnow().isoformat()
            }
        }
    )

    return True

# ───────────────────────── CREDENTIALS
# async def send_store_credentials(store_id: str, data: StoreInvitationModel) -> str:
#     doc = data.model_dump()
#     doc |= {
#         "store_id": store_id,
#         "temp_password": hash_password(doc["temp_password"]),
#         "sent_at": datetime.utcnow().isoformat()
#     }
#     saved = await db.StoreInvitations.insert_one(doc)
#     # (email logic would go here)
#     return str(saved.inserted_id)

# async def send_store_credentials(store_id: str, data: StoreInvitationModel) -> str:
#     try:
#         doc = data.model_dump()
#         temp_password = doc["temp_password"]  # Keep original before hashing

#         doc |= {
#             "store_id": store_id,
#             "temp_password": hash_password(temp_password),
#             "sent_at": datetime.utcnow().isoformat()
#         }

#         # 1. Save to DB
#         saved = await db.StoreInvitations.insert_one(doc)

#         # 2. Send Email with HTML template
#         email_success = send_welcome_email(to_email=doc["email"], password=temp_password)

#         if not email_success:
#             raise RuntimeError("Email sending failed")

#         return str(saved.inserted_id)

#     except Exception as e:
#         raise RuntimeError(f"Failed to send credentials: {str(e)}")

# ───────────────────────── HELP
async def submit_help(data: HelpModel) -> str:
    doc = data.model_dump() | {"submitted_at": datetime.utcnow().isoformat()}
    saved = await db.Help.insert_one(doc)
    return str(saved.inserted_id)