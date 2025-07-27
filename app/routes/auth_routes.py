from fastapi import APIRouter, HTTPException, Request

from app.models.super_admin_models import LoginModel, UpdateUserModel
from app.models.admin_login_model import LoginModel
from app.models.sales_model import LoginModel
from app.models.procurement_models import LoginModel
from app.services.dept_example_service import fetch_user, login
from app.services import super_admin_service as svc


router = APIRouter()

@router.get("/")
def root():
    return {"message": "Welcome to Optiven Admin APIs"}


@router.post("/login")   #super admin login
async def login_route(login_data: LoginModel):
    res = await login(login_data.email, login_data.password)
    if res is None:
        raise HTTPException(401, "Invalid email or password")
    return res

@router.get("/me")   #super admin login
async def login_route(request: Request):
    res = await fetch_user(request)
    if not res:
        raise HTTPException(401, "User not authenticated")
    return res


@router.put("/users/{user_id}")
async def update_user(user_id: str, user_data: UpdateUserModel):
    updated = await svc.update_user_by_id(user_id, user_data)
    if not updated:
        raise HTTPException(status_code=404, detail="User not found or update failed")
    return {"message": "User updated successfully"}