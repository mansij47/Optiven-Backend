from typing import List
from fastapi import APIRouter, HTTPException, Query, Request

from app.models.super_admin_models import (
    SignupModel, LoginModel, StoreIdsModel, StoreUpdate, UpdateProfileModel, ChangePasswordModel,
    CreateStoreModel, EditStoreModel, UpdateStoreStatusModel,
    AddCategoryModel, EditCategoryModel,
    AddSubcategoryModel, EditSubcategoryModel,
    StoreInvitationModel, HelpModel
)
from app.services import super_admin_service as svc
from app.services.super_admin_dashboard import get_dashboard_overview

router = APIRouter()

# ── AUTH ──────────────────────────────────
@router.post("/auth/signup")
async def signup(signup_data: SignupModel):
    result = await svc.signup(signup_data)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result

# @router.post("/auth/login")   #super admin login
# async def login(login_data: LoginModel):
#     res = await svc.login(login_data.email, login_data.password)
#     if res is None:
#         raise HTTPException(401, "Invalid email or password")
#     return res

# @router.get("/auth/me")
# async def get_me(request: Request):
#     user = request.state.user
#     user_id = user.get("id")
#     email = user.get("email")

#     if not user_id or not email:
#         raise HTTPException(400, "Invalid token or missing user data")

#     result = await svc.get_me_from_users(user_id, email)

#     if not result:
#         raise HTTPException(404, "User not found")
#     if "error" in result:
#         raise HTTPException(500, result["error"])
    
#     return result

# @router.get("/auth/me") #super admin login
# async def login_route(request: Request):
#     res = await svc.fetch_user(request)
#     if not res:
#         raise HTTPException(401, "User not authenticated")
#     res.pop("password", None) #Remove password from response

#     if res is None:
#         raise HTTPException(401, "Invalid email or password")
#     return res

# ── PROFILE ───────────────────────────────
@router.get("/profile")
async def get_profile(request: Request):
    user =  request.state.user
    if not user.get("role") == "super_admin":
        raise HTTPException(403, "Access denied")
    profile = await svc.get_profile(user.get("email"))
    if not profile:
        raise HTTPException(404, "Profile not found")
    return profile

@router.put("/profile")
async def update_profile(request: Request, profile_update: UpdateProfileModel):
    updated = await svc.update_profile(request.state.user["email"], profile_update)
    if updated == 0:
        raise HTTPException(404, "No update performed")
    return {"message": "Profile updated"}

@router.put("/profile/password")
async def change_password(request: Request, pw: ChangePasswordModel):
    res = await svc.change_password(request.state.user["email"], pw.old_password, pw.new_password)
    if "error" in res:
        raise HTTPException(400, res["error"])
    return res

# ── DASHBOARD ─────────────────────────────

@router.get("/overview")
async def dashboard_overview(request: Request):
    """
    Get dashboard overview with:
    - Total admins count
    - Total stores count (all statuses)
    - Total categories count
    - Total subcategories count
    - Store growth chart by creation date
    - Active/Inactive store ratio
    - Category/Subcategory ratio
    """
    try:
        # Call the service function to get the overview data
        overview_data = await get_dashboard_overview(request)
        return overview_data
    except Exception as e:
        print(f"[DASHBOARD ERROR] {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate dashboard data: {str(e)}")

# ── STORE CRUD ────────────────────────────
@router.get("/stores")
async def list_stores(request: Request):
    user = request.state.user
    if not user.get("role") == "super_admin":
        raise HTTPException(403, "Access denied")
    return {"stores": await svc.get_stores()}

@router.post("/store")
async def create_store(store_data: CreateStoreModel , send_email: bool = Query(False)):
    new_id = await svc.create_store(store_data, send_email)
    return {"message": "Store created", "store": new_id}

@router.get("/store/{store_id}")
async def get_store(store_id: str):
    store = await svc.get_store_by_id(store_id)
    if not store:
        raise HTTPException(404, "Store not found")
    return store

@router.put("/store/{store_id}")
async def edit_store(store_id: str, store_update: StoreUpdate):
    upd = await svc.edit_store(store_id, store_update)
    if upd == 0:
        raise HTTPException(404, "Store not found or no changes")
    return {"message": "Store updated"}

@router.delete("/store/{store_id}")
async def remove_store(store_id: str):
    deleted = await svc.delete_store(store_id)
    if deleted == 0:
        raise HTTPException(404, "Store not found")
    return {"message": "Store deleted"}

@router.delete("/stores/delete-multiple")
async def delete_multiple_stores(store_ids_model: StoreIdsModel, request: Request):
    user = request.state.user
    if user.get("role") != "super_admin":
        raise HTTPException(403, "Access denied")

    deleted_count = await svc.delete_multiple_stores(store_ids_model.store_ids)
    if deleted_count == 0:
        raise HTTPException(404, "No stores deleted. Check the store IDs.")
    return {"message": f"{deleted_count} store(s) deleted successfully."}

@router.patch("/store/{store_id}/status")
async def update_status(store_id: str, status_update: UpdateStoreStatusModel):
    upd = await svc.update_store_status(store_id, status_update.status)
    if upd == 0:
        raise HTTPException(404, "Store not found or status unchanged")
    return {"message": "Status updated"}

# ── CATEGORY / SUBCATEGORY ───────────────
@router.get("/stores/{store_id}/categories")
async def list_categories(store_id: str):
    categories = await svc.get_categories(store_id)
    if not categories:
        raise HTTPException(status_code=404, detail="No categories found for this store")
    return {"categories": categories}

@router.get("/categories/{category_id}")
async def get_category(category_id: str):
    category = await svc.get_category_by_id(category_id)
    if not category:
        raise HTTPException(404, "Category not found")
    return category

# @router.get("/categories")
# async def get_all_categories():
#     return {"categories": await svc.get_all_categories()}

@router.get("/categories", response_model=List[AddCategoryModel])
async def get_all_categories():
    return await svc.get_all_categories()


# @router.post("/stores/{store_id}/categories")
# async def add_category(store_id: str, cat_data: AddCategoryModel):
#     cid = await svc.add_category(store_id, cat_data)
#     return {"message": "Category added", "category_id": cid}

@router.post("/categories")
async def create_category(cat_data: AddCategoryModel):
    cid = await svc.create_category(cat_data)
    return {"message": "Category created", "category_id": cid}

@router.put("/categories/{category_id}")
async def edit_category(category_id: str, cat_update: EditCategoryModel):
    upd = await svc.edit_category(category_id, cat_update)
    if upd == 0:
        raise HTTPException(404, "Category not found or no changes")
    return {"message": "Category updated"}

@router.delete("/categories/{category_id}")
async def remove_category(category_id: str):
    deleted = await svc.delete_category(category_id)
    if deleted == 0:
        raise HTTPException(404, "Category not found")
    return {"message": "Category deleted"}

@router.post("/categories/{category_id}/subcategories")
async def add_subcategory(category_id: str, sub_data: AddSubcategoryModel):
    sid = await svc.add_subcategory(category_id, sub_data)
    return {"message": "Subcategory added", "sub_category_id": sid}

@router.put("/subcategories/{sub_id}")
async def edit_subcategory(sub_id: str, sub_update: EditSubcategoryModel):
    upd = await svc.edit_subcategory(sub_id, sub_update)
    if upd == 0:
        raise HTTPException(404, "Subcategory not found or no changes")
    return {"message": "Subcategory updated"}

@router.delete("/subcategories/{sub_id}")
async def remove_subcategory(sub_id: str):
    deleted = await svc.delete_subcategory(sub_id)
    if deleted == 0:
        raise HTTPException(404, "Subcategory not found")
    return {"message": "Subcategory deleted"}

@router.delete("/categories/{category_id}/subcategories/{sub_category_id}")
async def remove_subcategory(category_id: str, sub_category_id: str):
    result = await svc.delete_subcategory_from_category(category_id, sub_category_id)
    if not result:
        raise HTTPException(status_code=404, detail="Sub-category not found or already deleted")
    return {"message": "Sub-category deleted successfully"}

# ── CREDENTIALS ───────────────────────────
# @router.post("/stores/{store_id}/send-credentials")
# async def send_credentials(store_id: str, invitation_data: StoreInvitationModel):
#     inv_id = await svc.send_store_credentials(store_id, invitation_data)
#     return {"message": "Credentials sent", "invitation_id": inv_id}

# ── HELP ──────────────────────────────────
@router.post("/help")
async def submit_help(help_data: HelpModel):
    ticket = await svc.submit_help(help_data)
    return {"message": "Help ticket created", "ticket_id": ticket}