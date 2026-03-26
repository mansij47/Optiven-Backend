from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import uuid
import secrets
import asyncio
import logging
import hashlib
from app.models.store_model import StoresResponse
from fastapi import HTTPException, Request
from bson import ObjectId
from pymongo import ReturnDocument

from app.db import db
from app.config import SET_PASSWORD_TOKEN_EXPIRE_MINUTES
from app.utils.auth import hash_password, verify_password, create_access_token
from app.models.super_admin_models import (
    SignupModel, StoreUpdate, SuperAdminSignupModel, UpdateProfileModel, ChangePasswordModel,
    CreateStoreModel, EditStoreModel, UpdateStoreStatusModel,
    AddCategoryModel, EditCategoryModel,
    AddSubcategoryModel, EditSubcategoryModel,
    StoreInvitationModel, HelpModel, UpdateUserModel, UserModel
)
from app.utils.email_utils import send_welcome_email

logger = logging.getLogger(__name__)

# ───────────────────────── ID helper
async def _next_id(col, field_: str, prefix: str) -> str:
    last = await col.find_one({field_: {"$regex": f"^{prefix}\\d+$"}}, sort=[(field_, -1)])
    if not last:
        return f"{prefix}001"
    next_num = int(last[field_][len(prefix):]) + 1
    return f"{prefix}{str(next_num).zfill(3)}"


async def _get_max_existing_admin_number() -> int:
    try:
        cursor = db.Users.aggregate(
            [
                {"$match": {"id": {"$regex": "^ADM\\d+$"}}},
                {
                    "$project": {
                        "num": {
                            "$toInt": {
                                "$substrBytes": [
                                    "$id",
                                    3,
                                    {"$subtract": [{"$strLenBytes": "$id"}, 3]},
                                ]
                            }
                        }
                    }
                },
                {"$group": {"_id": None, "max_num": {"$max": "$num"}}},
            ]
        )
        result = await cursor.to_list(length=1)
        if result and result[0].get("max_num") is not None:
            return int(result[0]["max_num"])
    except Exception:
        # Fallback path for older Mongo setups or unexpected data.
        users = await db.Users.find({"id": {"$regex": "^ADM\\d+$"}}, {"_id": 0, "id": 1}).to_list(length=100000)
        max_num = 0
        for user in users:
            user_id = str(user.get("id") or "")
            if not user_id.startswith("ADM"):
                continue
            try:
                num = int(user_id[3:])
                if num > max_num:
                    max_num = num
            except ValueError:
                continue
        return max_num

    return 0


async def _next_admin_id_global() -> str:
    counter_key = "admin_id_seq"

    existing_counter = await db.Counters.find_one({"_id": counter_key}, {"_id": 1})
    if not existing_counter:
        max_existing = await _get_max_existing_admin_number()
        await db.Counters.update_one(
            {"_id": counter_key},
            {"$setOnInsert": {"value": max_existing}},
            upsert=True,
        )

    counter = await db.Counters.find_one_and_update(
        {"_id": counter_key},
        {"$inc": {"value": 1}},
        return_document=ReturnDocument.AFTER,
    )

    next_num = int((counter or {}).get("value") or 1)
    return f"ADM{str(next_num).zfill(3)}"


def _setup_token_expiry_minutes() -> int:
    try:
        value = int(SET_PASSWORD_TOKEN_EXPIRE_MINUTES)
    except (TypeError, ValueError):
        return 15
    if value <= 0:
        return 15
    return value


def _hash_setup_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def _create_setup_token_record(email: str, admin_id: str, store_id: str, org_id: str) -> str:
    raw_token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(minutes=_setup_token_expiry_minutes())

    await db.PasswordSetupTokens.update_many(
        {
            "email": email,
            "admin_id": admin_id,
            "store_id": store_id,
            "org_id": org_id,
            "used": False,
        },
        {
            "$set": {
                "used": True,
                "used_at": datetime.utcnow(),
            }
        },
    )

    await db.PasswordSetupTokens.insert_one(
        {
            "token_hash": _hash_setup_token(raw_token),
            "email": email,
            "admin_id": admin_id,
            "store_id": store_id,
            "org_id": org_id,
            "used": False,
            "created_at": datetime.utcnow(),
            "expires_at": expires_at,
            "used_at": None,
        }
    )

    return raw_token

# ───────────────────────── AUTH
async def signup(data:SignupModel) -> Dict[str, Any]:
    if await db.Users.find_one({"email": data.email}, {"_id": 0}):
        return {"error": "Email already registered"}

    doc = data.model_dump()
    doc["password"] = hash_password(doc["password"])
    now = datetime.utcnow().strftime("%Y-%m-%d")
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
    users = await db.Users.find({"email": email}).to_list(length=20)
    if not users:
        return None

    matched_users = []
    for user_doc in users:
        try:
            if verify_password(password, user_doc["password"]):
                matched_users.append(user_doc)
        except Exception:
            continue

    if not matched_users:
        return None

    if len(matched_users) == 1:
        admin = matched_users[0]
    else:
        super_admin_matches = [u for u in matched_users if u.get("role") == "super_admin"]
        if len(super_admin_matches) == 1:
            admin = super_admin_matches[0]
        else:
            raise HTTPException(
                status_code=409,
                detail="Multiple accounts matched these credentials. Please contact Super Admin.",
            )

    role = admin.get("role")

    def _normalize_status(value: Any) -> int:
        if isinstance(value, bool):
            return 1 if value else 0
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            status_map = {
                "1": 1,
                "active": 1,
                "enabled": 1,
                "0": 0,
                "inactive": 0,
                "draft": 0,
                "2": 2,
                "disabled": 2,
                "3": 3,
                "deleted": 3,
            }
            return status_map.get(value.strip().lower(), 0)
        return 0

    store_status: int | None = None
    # Check if store is active (for non-super_admin users)
    if role != "super_admin":
        store_id = admin.get("store_id", "")
        if store_id:
            store = await db.Stores.find_one({"store_id": store_id})
            if not store:
                raise HTTPException(
                    status_code=403,
                    detail="Access denied. Your store is not active. Please contact Super Admin.",
                )
            store_status = _normalize_status(store.get("status", 0))
            if store_status != 1:
                raise HTTPException(
                    status_code=403,
                    detail="Access denied. Your store is not active. Please contact Super Admin.",
                )

    # Check if user is active. For store admins, self-heal stale status when store is active.
    user_status = _normalize_status(admin.get("status", 0))
    if user_status != 1:
        if role == "admin" and store_status == 1:
            await db.Users.update_one(
                {"_id": admin["_id"]},
                {"$set": {"status": 1, "updated_at": datetime.utcnow().strftime("%Y-%m-%d")}},
            )
            admin["status"] = 1
        else:
            raise HTTPException(status_code=403, detail="Account is inactive or disabled")

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

    email = user.get("email")
    role = user.get("role")
    store_id = user.get("store_id")
    org_id = user.get("org_id")

    if role == "super_admin":
        query = {"email": email}
    else:
        query = {
            "email": email,
            "store_id": store_id,
            "org_id": org_id,
        }

    res = await db.Users.find_one(query, {"_id": 0})
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
        {"$set": payload.model_dump(exclude_none=True) | {"updated_at": datetime.utcnow().strftime("%Y-%m-%d")}}
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


async def set_password_with_token(token: str, new_password: str) -> Dict[str, str]:
    token_hash = _hash_setup_token(str(token or ""))
    now = datetime.utcnow()

    token_doc = await db.PasswordSetupTokens.find_one_and_update(
        {
            "token_hash": token_hash,
            "used": False,
            "expires_at": {"$gt": now},
        },
        {
            "$set": {
                "used": True,
                "used_at": now,
            }
        },
        return_document=ReturnDocument.BEFORE,
    )

    if not token_doc:
        known_token = await db.PasswordSetupTokens.find_one(
            {"token_hash": token_hash},
            {"_id": 0, "used": 1, "expires_at": 1},
        )
        if known_token and known_token.get("used") is True:
            raise HTTPException(status_code=409, detail="This link has expired or already been used")
        raise HTTPException(status_code=401, detail="This link has expired or already been used")

    lookup_query = {
        "email": token_doc.get("email"),
        "store_id": token_doc.get("store_id"),
        "org_id": token_doc.get("org_id"),
    }
    if token_doc.get("admin_id"):
        lookup_query["id"] = token_doc.get("admin_id")

    user = await db.Users.find_one(lookup_query)
    if not user:
        raise HTTPException(status_code=404, detail="User not found for setup token")

    if user.get("first_login") is False:
        raise HTTPException(status_code=409, detail="This link has expired or already been used")

    await db.Users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "password": hash_password(new_password),
                "first_login": False,
                "updated_at": datetime.utcnow().isoformat(),
            }
        },
    )
    return {"message": "Password set successfully"}


async def get_set_password_token_status(token: str) -> Dict[str, str]:
    token_hash = _hash_setup_token(str(token or ""))
    now = datetime.utcnow()

    token_doc = await db.PasswordSetupTokens.find_one(
        {"token_hash": token_hash},
        {"_id": 0, "email": 1, "admin_id": 1, "store_id": 1, "org_id": 1, "used": 1, "expires_at": 1},
    )

    if not token_doc:
        return {
            "status": "invalid",
            "message": "This link has expired or already been used",
        }

    lookup_query = {
        "email": token_doc.get("email"),
        "store_id": token_doc.get("store_id"),
        "org_id": token_doc.get("org_id"),
    }
    if token_doc.get("admin_id"):
        lookup_query["id"] = token_doc.get("admin_id")

    user = await db.Users.find_one(lookup_query, {"_id": 1, "first_login": 1})
    if not user:
        return {
            "status": "invalid",
            "message": "This link has expired or already been used",
        }

    if token_doc.get("used") is True:
        if user.get("first_login") is False:
            return {
                "status": "already_set",
                "message": "Password is already set for this account.",
            }
        return {
            "status": "invalid",
            "message": "This link has expired or already been used",
        }

    if token_doc.get("expires_at") and token_doc.get("expires_at") <= now:
        return {
            "status": "invalid",
            "message": "This link has expired or already been used",
        }

    if user.get("first_login") is False:
        return {
            "status": "already_set",
            "message": "Password is already set for this account.",
        }

    return {
        "status": "ready",
        "message": "Setup link is valid.",
    }


async def resend_set_password_link(token: str) -> Dict[str, Any]:
    token_hash = _hash_setup_token(str(token or ""))
    token_doc = await db.PasswordSetupTokens.find_one(
        {"token_hash": token_hash},
        {"_id": 0, "email": 1, "admin_id": 1, "store_id": 1, "org_id": 1},
    )

    if not token_doc:
        raise HTTPException(status_code=404, detail="Setup link record not found")

    lookup_query = {
        "email": token_doc.get("email"),
        "store_id": token_doc.get("store_id"),
        "org_id": token_doc.get("org_id"),
    }
    if token_doc.get("admin_id"):
        lookup_query["id"] = token_doc.get("admin_id")

    user = await db.Users.find_one(lookup_query, {"_id": 0, "name": 1, "first_login": 1, "email": 1})
    if not user:
        raise HTTPException(status_code=404, detail="User not found for setup link")

    if user.get("first_login") is False:
        raise HTTPException(status_code=409, detail="Password is already set for this account")

    store = await db.Stores.find_one(
        {
            "store_id": token_doc.get("store_id"),
            "org_id": token_doc.get("org_id"),
        },
        {"_id": 0, "store_name": 1},
    )

    name_data = user.get("name") or {}
    admin_display_name = (
        f"{str(name_data.get('first_name') or '').strip()} {str(name_data.get('last_name') or '').strip()}"
    ).strip() or "Admin"

    new_token = await _create_setup_token_record(
        email=token_doc.get("email"),
        admin_id=token_doc.get("admin_id"),
        store_id=token_doc.get("store_id"),
        org_id=token_doc.get("org_id"),
    )

    email_sent = await asyncio.to_thread(
        send_welcome_email,
        token_doc.get("email"),
        None,
        new_token,
        admin_display_name,
        (store or {}).get("store_name"),
        token_doc.get("store_id"),
    )

    if not email_sent:
        raise HTTPException(status_code=502, detail="Unable to send setup email right now. Please try again.")

    return {
        "message": "A new set-password link has been sent to your email",
        "sent": True,
    }

# ───────────────────────── DASHBOARD
async def get_dashboard_overview(_: Dict[str, Any]):
    total = await db.Stores.count_documents({})
    active = await db.Stores.count_documents({"status": 1})
    disabled = await db.Stores.count_documents({"status": 2})
    draft = total - active - disabled
    return {"total": total, "active": active, "disabled": disabled, "draft": draft}

# ───────────────────────── STORE
async def get_storess():                        # list
    return await db.Stores.find({}, {"_id": 0}).to_list(1000)

async def get_stores(
    search: Optional[str] = None,
    status: Optional[str] = None,
    statuses: Optional[List[str]] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page: int = 1,
    page_size: int = 15
) -> StoresResponse:
    # Build MongoDB query
    query = {}
    
    # Search filter - improved to handle partial matches better
    if search and search.strip():
        search_term = search.strip()
        search_regex = {"$regex": f".*{search_term}.*", "$options": "i"}  # Case-insensitive partial match
        query["$or"] = [
            {"store_name": search_regex},
            {"admin_id": search_regex},
            {"store_email": search_regex},
            {"store_id": search_regex}
            # Add other searchable fields if needed
            # {"description": search_regex},
            # {"email": search_regex}
        ]

    # Status filter
    status_map = {"active": 1, "disabled": 2, "draft": 0, "deleted": 3}
    if status and status.lower() != "all":
        mapped_status = status_map.get(status.lower())
        if mapped_status is not None:  # Check for None to handle status 0 (draft)
            query["status"] = mapped_status
    elif statuses:
        valid_statuses = [status_map.get(s.lower()) for s in statuses if s.lower() in status_map]
        if valid_statuses:
            query["status"] = {"$in": valid_statuses}

    # Date range filter
    if date_from:
        try:
            query["created_at"] = {"$gte": datetime.fromisoformat(date_from.replace("Z", "+00:00"))}
        except ValueError:
            raise HTTPException(400, "Invalid date_from format")
    if date_to:
        try:
            if "created_at" not in query:
                query["created_at"] = {}
            query["created_at"]["$lte"] = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(400, "Invalid date_to format")

    # Debug: Print the query to see what's being searched
    # print(f"MongoDB Query: {query}")

    # Pagination
    skip = (page - 1) * page_size
    total = await db.Stores.count_documents(query)
    
    # Sort by created_at first, then _id as a deterministic tie-breaker for same-day records.
    stores = await db.Stores.find(query, {"_id": 0}).sort([("created_at", -1), ("_id", -1)]).skip(skip).limit(page_size).to_list(page_size)

    # Backfill admin_id for legacy store records where it may be missing.
    for store in stores:
        if store.get("admin_id"):
            continue

        admin_user = await db.Users.find_one(
            {
                "org_id": store.get("org_id"),
                "store_id": store.get("store_id"),
                "role": "admin",
            },
            {"_id": 0, "id": 1},
            sort=[("created_at", 1)],
        )

        if admin_user and admin_user.get("id"):
            store["admin_id"] = admin_user["id"]
   

    return StoresResponse(
        data=stores,
        total=total,
        page=page,
        page_size=page_size
    )

async def create_store(data: CreateStoreModel, send_email):
    doc = data.model_dump()
    org_id = uuid.uuid4()

    # Ensure store_id always exists and is unique.
    requested_store_id = str(doc.get("store_id") or "").strip()
    if not requested_store_id or await db.Stores.find_one({"store_id": requested_store_id}):
        store_id = await _next_id(db.Stores, "store_id", "ST")
    else:
        store_id = requested_store_id

    doc["store_id"] = store_id
    doc["org_id"] = str(org_id)

    now = datetime.utcnow().strftime("%Y-%m-%d")
    doc["created_at"] = now
    doc["updated_at"] = now

    # Never store or send plaintext passwords for newly created admin users.
    bootstrap_password = secrets.token_urlsafe(24)

    generated_admin_id = await _next_admin_id_global()
    while await db.Users.find_one(
        {"id": generated_admin_id}
    ):
        generated_admin_id = await _next_admin_id_global()

    user_model = UserModel(
        id=generated_admin_id,
        org_id=str(org_id),
        store_id=store_id,
        password=hash_password(bootstrap_password),
        phone=doc.get("address", {}).get("phone"),
        email=doc.get("store_email"),
        name=doc.get("admin_name"),
        joining_date=now,
        first_login=True,
        status=1
    )

    admin_name_data = doc.get("admin_name") or {}
    admin_display_name = (
        f"{str(admin_name_data.get('first_name') or '').strip()} {str(admin_name_data.get('last_name') or '').strip()}"
    ).strip()
    if not admin_display_name:
        admin_display_name = "Admin"

    # Check if user already exists
    existing_user = await db.Users.find_one({"email": user_model.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="User with this email already exists")

    # Send credentials email if requested, but do not block store creation on mail transport errors.
    welcome_email_sent = None
    if send_email:
        welcome_email_sent = False
        try:
            setup_token = await _create_setup_token_record(
                email=doc.get("store_email"),
                admin_id=generated_admin_id,
                store_id=store_id,
                org_id=str(org_id),
            )
            welcome_email_sent = await asyncio.to_thread(
                send_welcome_email,
                doc.get("store_email"),
                None,
                setup_token,
                admin_display_name,
                doc.get("store_name"),
                store_id,
            )
            if not welcome_email_sent:
                logger.warning(
                    "Welcome email could not be sent during store creation recipient=%s",
                    doc.get("store_email"),
                )
        except Exception as e:
            logger.warning(
                "Failed to dispatch credentials email recipient=%s error=%s",
                doc.get("store_email"),
                str(e),
            )

    # Insert user and store regardless of email delivery outcome.
    user_doc = user_model.model_dump()
    user_doc["created_at"] = now
    user_doc["updated_at"] = now

    # Store records should not persist credential fields.
    doc.pop("password", None)
    doc["admin_id"] = generated_admin_id

    await db.Users.insert_one(user_doc)
    await db.Stores.insert_one(doc)

    return {
        "store_id": store_id,
        "admin_id": generated_admin_id,
        "store_email": doc.get("store_email"),
        # "password": password,
        "welcome_email_sent": welcome_email_sent,
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
    update_data["updated_at"] = datetime.utcnow().strftime("%Y-%m-%d")

    update_query = {
        "$set": update_data  # ✅ Set everything including empty arrays
    }

    res = await db.Stores.update_one({"store_id": store_id}, update_query)
    return res.modified_count

async def delete_store(store_id: str) -> int:
    # Soft delete: Set store status to 3 (deleted)
    res = await db.Stores.update_one(
        {"store_id": store_id},
        {"$set": {"status": 3, "updated_at": datetime.utcnow().strftime("%Y-%m-%d")}}
    )
    
    # Also mark all users associated with this store as inactive/deleted
    if res.modified_count > 0:
        await db.Users.update_many(
            {"store_id": store_id},
            {"$set": {"status": 0, "updated_at": datetime.utcnow().strftime("%Y-%m-%d")}}
        )
    
    return res.modified_count

async def delete_multiple_stores(store_ids: List[str]) -> int:
    # Soft delete: Set status to 3 (deleted) for multiple stores
    res = await db.Stores.update_many(
        {"store_id": {"$in": store_ids}},
        {"$set": {"status": 3, "updated_at": datetime.utcnow().strftime("%Y-%m-%d")}}
    )
    
    # Also mark all users associated with these stores as inactive/deleted
    if res.modified_count > 0:
        await db.Users.update_many(
            {"store_id": {"$in": store_ids}},
            {"$set": {"status": 0, "updated_at": datetime.utcnow().strftime("%Y-%m-%d")}}
        )
    
    return res.modified_count

async def permanent_delete_store(store_id: str) -> int:
    """
    Permanently delete a store and all its related data.
    This is a hard delete - all data will be removed from the database.
    """
    # Delete the store
    store_res = await db.Stores.delete_one({"store_id": store_id})
    
    # Delete all users associated with this store
    await db.Users.delete_many({"store_id": store_id})
    
    # Delete all inventory items for this store
    await db.Inventory.delete_many({"store_id": store_id})
    
    # Delete all orders for this store
    await db.Orders.delete_many({"store_id": store_id})
    
    # Delete all sales for this store
    await db.Sales.delete_many({"store_id": store_id})
    
    # Delete all purchase orders for this store
    await db.PurchaseOrders.delete_many({"store_id": store_id})
    
    # Delete all notifications for this store
    await db.Notifications.delete_many({"store_id": store_id})
    
    return store_res.deleted_count

async def update_store_status(store_id: str, status: int)-> int:
    res = await db.Stores.update_one(
        {"store_id": store_id},
        {"$set": {"status": status, "updated_at": datetime.utcnow().strftime("%Y-%m-%d")}}
    )

    if res.matched_count == 0:
        return 0
    
    # When disabling a store (status=2), also disable all its users.
    # Use matched_count semantics so user status can be repaired even when store status is unchanged.
    if status == 2:
        await db.Users.update_many(
            {"store_id": store_id},
            {"$set": {"status": 0, "updated_at": datetime.utcnow().strftime("%Y-%m-%d")}}
        )
    # When re-activating a store (status=1), reactivate all its users
    elif status == 1:
        await db.Users.update_many(
            {"store_id": store_id},
            {"$set": {"status": 1, "updated_at": datetime.utcnow().strftime("%Y-%m-%d")}}
        )
    
    return 1

# ───────────────────────── CATEGORY / SUBCATEGORY

async def get_categories(store_id: str) -> Dict[str, Any]:
    store = await db.Stores.find_one({"store_id": store_id})
    if not store:
        return {
            "status": "success",
            "message": f"No store found with id {store_id}",
            "categories": []
        }

    # Extract category IDs from list of dicts
    category_dicts = store.get("category_ids", [])
    category_ids = [cat["id"] for cat in category_dicts if "id" in cat]

    if not category_ids:
        return {
            "status": "success",
            "message": f"No categories found for store {store_id}",
            "categories": []
        }

    # Query the categories collection
    categories = await db.Categories.find(
        {"category_id": {"$in": category_ids}},
        {"_id": 0}
    ).to_list(length=None)

    if not categories:
        return {
            "status": "success",
            "message": f"No categories found for store {store_id}",
            "categories": []
        }

    return {
        "status": "success",
        "message": "Categories fetched successfully",
        "categories": categories
    }


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
    ts = datetime.utcnow().strftime("%Y-%m-%d")
    doc["created_at"] = ts
    doc["updated_at"] = ts

    await db.Categories.insert_one(doc)
    return doc["category_id"]

async def edit_category(category_id: str, data: EditCategoryModel) -> int:
    update_data = data.model_dump(exclude_none=True)

    # ✅ Recalculate sub_category_count if sub_categories are being updated
    if "sub_categories" in update_data:
        update_data["sub_category_count"] = len(update_data["sub_categories"])

    update_data["updated_at"] = datetime.utcnow().strftime("%Y-%m-%d")

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
        "created_at": datetime.utcnow().strftime("%Y-%m-%d"),
        "updated_at": datetime.utcnow().strftime("%Y-%m-%d")
    }
    await db.Categories.update_one(
        {"category_id": category_id},
        {"$push": {"sub_categories": sub_doc},
         "$set": {"updated_at": sub_doc["updated_at"]}}
    )
    return sub_id

async def edit_subcategory(sub_id: str, data: EditSubcategoryModel) -> int:
    update_fields = {f"sub_categories.$.{k}": v for k, v in data.model_dump(exclude_none=True).items()}
    update_fields["sub_categories.$.updated_at"] = datetime.utcnow().strftime("%Y-%m-%d")
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
            "updated_at": datetime.utcnow().strftime("%Y-%m-%d")
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
async def submit_help(data: HelpModel, user) -> str:
    doc = data.model_dump()
    doc["submitted_at"] = datetime.now().strftime("%Y-%m-%d")

    # Automatically add requested_by from middleware user
    doc["requested_by"] = {
        "id": str(user["id"]),
        "email": str(user["email"]),
        "role": str(user["role"]),
    }

    saved = await db.Help.insert_one(doc)
    return str(saved.inserted_id)
 # get all requests help 
async def get_all_help():
    cursor = db.Help.find({})
    results = []
    async for doc in cursor:
        doc["id"] = str(doc["_id"])  # convert ObjectId to string
        doc.pop("_id", None)
        results.append(doc)
    return results
# get by id 
async def get_help_by_id(ticket_id: str):
    doc = await db.Help.find_one({"_id": ObjectId(ticket_id)})
    if doc is None:
        return None
    doc["id"] = str(doc["_id"])
    doc.pop("_id", None)
    return doc
