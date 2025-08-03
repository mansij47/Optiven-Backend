from fastapi import APIRouter, Body, HTTPException, Query, Request

# from app.models.super_admin_models import HTTPException, Request, Query, Body
from app.models.admin_login_model import LoginModel
from app.services import admin_login_service as svc
from typing import Optional,List
from app import db
import traceback
from jose import jwt, JWTError
from bson import ObjectId
import os
from app.models.admin_model import DepartmentUserCreate, EditOrderModel, LoginModel, NewRaiseOrderRequest, Product, RaiseRequestOrderModel, ResetPasswordRequest, SalesOrderModel ,ProductUpdate
from app.services import notification_service
from app.services.admin_inventory_service import delete_product_service, update_product_by_id, export_inventory_csv, get_product_by_id, get_all_products, add_product_service 
from app.services.admin_lossOrders_service import export_loss_orders_csv, get_all_loss_orders_with_metrics 
from app.services.admin_receivedOrders_service import delete_order_by_id, get_all_sales_orders, update_sales_order
from app.services.admin_requested_order_service import get_all_requested_orders, raise_order_request_service, raise_request_order_service
from app.services.admin_soldOrders_service import add_sales_order, get_all_sold_orders
from app.services.admin_user_service import create_department_user, delete_user_by_id, reset_password
from app.models.admin_model import EditOrderModel

# Importing the notification model and service
from app.models.notification_model import NotificationUpdate, NotificationBase
from app.services.notification_service import (
    create_notification,   
    get_all_notifications,
    update_notification_by_id,
    delete_notification_by_id
)

# Importing the admin setup model and service
from app.models.admin_setting_model import AdminSetupSettingRequest
from app.services.admin_setting_service import update_admin_setting, get_admin_setting

# Importing the category model and service
from app.models.category_model import CategoryCreate, CategoryUpdate
from app.services.category_service import (
    create_category,
    get_all_categories,
    get_category_by_id,
    update_category_by_id,
    delete_category_by_id
)
# Importing the help request model and service
from app.models.help_model import HelpRequest
from app.services.help_service import create_help_request, get_all_help_requests
# Importing store-related models and services
from app.services.store_service import get_store_detail_by_token
from app.models.store_model import StoreUpdate, StaffInput
from app.services.store_service import update_store_by_token, add_staff_to_department, update_staff_in_department, delete_staff_from_department
from app.services.dashboard_service import get_dashboard_data
from app.models.dashboard_model import DashboardResponse
router = APIRouter()

# ================== ROOT ==================
@router.get("/")
def root():
    return {"message": "Welcome to Optiven Admin APIs"}

# ================== Dashboard ==================
@router.get("/dashboard")
async def fetch_dashboard_data(request: Request):
    # You can now access role like this:
    user = request.state.user
    role = user.get("role")

    # Optional role check (if needed)
    if role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")

    data = await get_dashboard_data()
    return data


# ================== NOTIFICATIONS ==================
#create the notification by the sales , procurement department to sent the notification to the admin
# @router.post("/send/notification")
# async def send_notification(
#     model: NotificationBase,
#     admin: Optional[bool] = Query(False),
#     sales: Optional[bool] = Query(False),
#     procurement: Optional[bool] = Query(False)
# ):
#     return await notification_service.create_notification(
#         model,
#         admin=admin,
#         sales=sales,
#         procurement=procurement
#     )
@router.post("/notification")
async def send_notification(
    request: Request,  # ✅ Move request to the top
    model: NotificationBase,
    admin: Optional[bool] = Query(False),
    sales: Optional[bool] = Query(False),
    procurement: Optional[bool] = Query(False)
):
    user = request.state.user
    sender = {
        "id": user.get("id"),
        "role": user.get("role"),
        "store_id": user.get("store_id"),
        "email": user.get("email")
    }

    return await notification_service.create_notification(
        model,
        admin=admin,
        sales=sales,
        procurement=procurement
       
    )



@router.get("/notifications")
async def get_notifications(request: Request, status: Optional[int] = None):
    user = request.state.user  # Token-decoded user info: id, role, etc.
    try:
        return await get_all_notifications(user, status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# update the notifaction like read or delete
@router.patch("/notifications/{notification_id}")
async def update_notification(request: Request, notification_id: str, update_data: NotificationUpdate):
    user = request.state.user
    try:
        return await update_notification_by_id(notification_id, update_data)
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
 #delete the if there is no need of that notification 
@router.delete("/notifications/{notification_id}")
async def delete_notification(request: Request, notification_id: str):
    user = request.state.user
    try:
        return await delete_notification_by_id(notification_id)
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
# ================== ADMIN SETUP_SETTING ================

# NEW: Get admin setup_setting details for the current admin
@router.get("/setting")
async def get_admin_setup_setting_details(request: Request):
    admin_id = request.state.user.get("id")
    if not admin_id:
        raise HTTPException(status_code=401, detail="Admin ID not found in token")
    details = await get_admin_setting(admin_id)
    if not details:
        raise HTTPException(status_code=404, detail="Admin not found")
    return details  # details is already {"admin": ...}


# Update 
@router.patch("/setting")
async def admin_first_time_setup_setting(request: Request, setup_data: AdminSetupSettingRequest):
    try:
        admin_id = request.state.user.get("id")
        if not admin_id:
            raise HTTPException(status_code=401, detail="Admin ID not found in token")

    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # Step 2: Filter fields to update
    update_fields = {k: v for k, v in setup_data.dict().items() if v is not None}
    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Step 3: Update admin by _id (MongoDB _id)
    updated_admin = await update_admin_setting(admin_id, update_fields)

    if not updated_admin:
        raise HTTPException(status_code=404, detail="Admin not found or update failed")

    return updated_admin


# ================== CATEGORY ==================

# Create a new category
@router.post("/categories")
async def create_new_category(request: Request, data: CategoryCreate):
    return create_category(data)

# Get all categories
@router.get("/categories")
async def get_categories(request: Request):
    return await get_all_categories()

# Get a single category by ID
@router.get("/categories/{category_id}")
async def get_category(category_id: str, request: Request):
    return await get_category_by_id(category_id)

# Update a category
@router.patch("/categories/{category_id}")
async def update_category(category_id: str, data: CategoryUpdate, request: Request):
    return await update_category_by_id(category_id, data)

# Delete a category
@router.delete("/categories/{category_id}")
async def delete_category(category_id: str, request: Request):
    return await delete_category_by_id(category_id)

# ================== HELP REQUESTS ==================

@router.post("/help")
async def submit_help_request(request: Request, data: HelpRequest):
    return await create_help_request(data)

@router.get("/help")
async def fetch_all_help_requests(request: Request):
    return await get_all_help_requests()

# ================== STORE SETUP ==================

@router.get("/store/details")
async def get_store_details(request: Request):
    return await get_store_detail_by_token(request)

@router.patch("/store/update")
async def update_store(
    request: Request,
    updates: StoreUpdate = Body(...)
):
    return await update_store_by_token(updates.model_dump(exclude_none=True), request)

@router.post("/add/product")
async def add_product(request: Request, product: Product):
    user = request.state.user  # Decoded JWT stored by middleware
    if user.get("role") not in ["admin","procurement"]:
        raise HTTPException(status_code=403, detail="Forbidden: Admin access required.")

    store_id = user.get("store_id")
    org_id = user.get("org_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID missing in token.")

    # Call service with product data and store ID
    return await add_product_service(product, store_id, org_id)

   
@router.get("/all/product")
async def fetch_all_products_route(request: Request):
    # Role check
    user = request.state.user
    if not user or user.get("role") not in ["admin","procurement"]:
        raise HTTPException(status_code=403, detail="Forbidden: Admin access required.")
    
    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID missing in token.")
    response = await get_all_products(store_id)
    print("Fetched products:", response)
    return response


@router.get("/one/product/{product_id}")
async def fetch_product_by_id(request: Request, product_id: str):
    # Admin role check
    user = request.state.user

    if user.get("role") not in ["admin","procurement"]:
        raise HTTPException(status_code=403, detail="Forbidden: Admin access required.")

    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID missing in token.")
    return await get_product_by_id(product_id, store_id)  

@router.patch("/edit/product/{product_id}")
async def edit_product_patch(request: Request, product_id: str, data: ProductUpdate):
    # Admin role check
    user = request.state.user
    if user.get("role") not in ["admin","procurement"]:
        raise HTTPException(status_code=403, detail="Forbidden: Admin access required.")

    # ✅ These lines must be indented inside the function
    update_data = data.dict(exclude_unset=True)

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided for update.")

    response = await update_product_by_id(product_id, update_data)
    print("Update response:", response)
    return response

@router.put("/edit/product/{product_id}")
async def edit_product_put(request: Request, product_id: str, data: Product):
    # Admin role check
    user = request.state.user
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden: Admin access required.")

    update_data = data.model_dump(exclude_unset=True)
    response = await update_product_by_id(product_id, update_data)
    print("Update response:", response)
    return response


@router.delete("/delete/product/{product_id}")
async def delete_product(request: Request, product_id: str):
    user = request.state.user
    if user.get("role") not in ["admin","procurement"]:
        raise HTTPException(status_code=403, detail="Forbidden: Admin access required.")
    
    await delete_product_service(product_id)
    return {"message": f"Product with ID '{product_id}' deleted successfully"}


#export My Inventory sheet csv file
@router.get("/export_inventory", summary="Export My Inventory as CSV")
async def export_inventory(request: Request):
    try:
        user = request.state.user
        store_id = user.get("store_id")
        org_id = user.get("org_id")

        if not store_id or not org_id:
            raise HTTPException(status_code=400, detail="Missing store_id or org_id in token")

        return await export_inventory_csv(store_id, org_id)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

#export loss sheet csv file
@router.get("/export_lossSheet", summary="Export Loss Orders as CSV")
async def export_loss_orders(request: Request):
    try:
        user = request.state.user
        store_id = user.get("store_id")
        org_id = user.get("org_id")

        if not store_id or not org_id:
            raise HTTPException(status_code=400, detail="Missing store_id or org_id in token")

        return await export_loss_orders_csv(store_id, org_id)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))    


@router.get("/lossorders/report")
async def fetch_loss_orders_and_metrics(
    request: Request,
    total_inventory_value: Optional[float] = Query(100000.0)
):
    user = request.state.user
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden: Admin access required.")
    
    store_id = user.get("store_id")
    org_id = user.get("org_id")

    if not store_id or not org_id:
        raise HTTPException(status_code=400, detail="Missing store_id or org_id in token.")

    return await get_all_loss_orders_with_metrics(
        store_id=store_id,
        org_id=org_id,
        total_inventory_value=total_inventory_value # type: ignore
    )


@router.get("/requested-orders")
async def get_orders(request: Request): # type: ignore
    user = request.state.user

    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only admins are allowed.")
    storeId = user.get("store_id")
    return await get_all_requested_orders(storeId)


@router.get("/orders/sold")
async def get_sold_orders_admin(request: Request):
    user = request.state.user
    print("User in route:", user)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden: Admin access required.")
    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID missing in token.")
    orders = await get_all_sold_orders(store_id)

    return {"orders": orders}


@router.post("/add-employee")
async def add_employee(data: DepartmentUserCreate, request: Request):
    user = request.state.user  # This comes from JWT middleware
    return await create_department_user(data, user)


@router.delete("/delete/{employee_id}")
async def delete_user(employee_id: str, request: Request):
    return await delete_user_by_id(employee_id, request)


# this is from sales
@router.post("/orders/request/raise")
async def raise_request_order(request_model: RaiseRequestOrderModel, request: Request):
    user = request.state.user

    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden: Admin access required.")

    org_id = user.get("org_id")
    store_id = user.get("store_id")
    if not org_id or not store_id:
        raise HTTPException(status_code=400, detail="Organization or Store ID missing in token.")

    requester = {
        "role": user.get("role"),
        "id": user.get("id", "unknown")
    }

    request_id = await raise_request_order_service(
        order_id=request_model.order_id,
        estimate_date=request_model.estimate_date,
        org_id=org_id,
        store_id=store_id,
        requester=requester
    )

    return {"message": "Request raised successfully", "request_id": request_id}


# this is from admin
@router.post("/orders/raise-request")
async def raise_order_request_api(data: NewRaiseOrderRequest, request: Request):
    user = request.state.user

    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden: Only admins can raise procurement requests.")

    store_id = user.get("store_id")
    org_id = user.get("org_id")

    if not store_id or not org_id:
        raise HTTPException(status_code=400, detail="Store ID or Org ID missing in token.")

    requested_by = {
        "role": user.get("role"),
        "id": user.get("user_id", "unknown")
    }

    response = await raise_order_request_service(data.dict(), org_id, store_id, requested_by)
    return response

@router.post("/orders/received/add")
async def add_order(order: SalesOrderModel, request: Request):
    user = request.state.user

    if not user or user.get("role") not in ["admin"]:
        raise HTTPException(status_code=403, detail="Forbidden: Admin access required.")

    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID missing in token.")

    order_dict = order.model_dump()
    order_dict.pop("order_id", None)
    order_dict["store_id"] = store_id

    inserted_order_id = await add_sales_order(order_dict, store_id)
    return {"message": "Order added successfully", "order_id": inserted_order_id}




@router.get("/orders/received")
async def get_orders(request: Request):
    user = request.state.user

    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden: Admin access required.")
    
    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID missing in token.")

    orders = await get_all_sales_orders(store_id)

    return {"orders": orders}

@router.delete("/orders/received/{order_id}")
async def delete_order(order_id: str, request: Request):
    user = request.state.user

    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden: Admin access required.")

    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID missing in token.")

    deleted_count = await delete_order_by_id(order_id, store_id)

    if deleted_count == 0:
        raise HTTPException(status_code=404, detail="Order not found.")

    return {"message": "Order deleted successfully", "order_id": order_id}


from app.models.admin_model import EditOrderModel

@router.patch("/orders/received/{order_id}")
async def edit_order(order_id: str, order: EditOrderModel, request: Request):
    user = request.state.user

    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden: Admin access required.")

    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID missing in token.")

    order_dict = order.model_dump(exclude_unset=True)
    order_dict["store_id"] = store_id

    updated_count = await update_sales_order(order_id, store_id, order_dict)
    if updated_count == 0:
        raise HTTPException(status_code=404, detail="Order not found or no changes detected.")

    return {"message": "Order updated successfully", "order_id": order_id}


#forgot password

@router.post("/reset-password")
async def reset_password_route(payload: ResetPasswordRequest):
    return await reset_password(payload.email, payload.user_id, payload.new_password)

# sold orders
@router.get("/orders/sold") 
async def get_sold_orders(request: Request):
    user = request.state.user
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden: Sales access required.")
    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID missing in token.")
    orders = await get_all_sold_orders(store_id)

    return {"orders": orders}