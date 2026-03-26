from fastapi import APIRouter, HTTPException, Request

from app.models.super_admin_models import LoginModel, UpdateUserModel, SetPasswordRequest, SetPasswordStatusRequest, SetPasswordResendRequest
from app.services import super_admin_service as svc


router = APIRouter()

@router.get("/")
def root():
    return {"message": "Welcome to Optiven Admin APIs"}


@router.post("/login")   #super admin login
async def login_route(login_data: LoginModel):
    res = await svc.login(login_data.email, login_data.password)
    if res is None:
        raise HTTPException(401, "Invalid email or password")
    return res

@router.get("/me")   #super admin login
async def login_route(request: Request):
    res = await svc.fetch_user(request)
    if not res:
        raise HTTPException(401, "User not authenticated")
    return res


@router.put("/users/{user_id}")
async def update_user(user_id: str, user_data: UpdateUserModel):
    updated = await svc.update_user_by_id(user_id, user_data)
    if not updated:
        raise HTTPException(status_code=404, detail="User not found or update failed")
    return {"message": "User updated successfully"}


@router.post("/set-password")
async def set_password(payload: SetPasswordRequest):
    return await svc.set_password_with_token(payload.token, payload.new_password)


@router.post("/set-password-status")
async def set_password_status(payload: SetPasswordStatusRequest):
    return await svc.get_set_password_token_status(payload.token)


@router.post("/resend-set-password-link")
async def resend_set_password_link(payload: SetPasswordResendRequest):
    return await svc.resend_set_password_link(payload.token)