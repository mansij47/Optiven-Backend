import logging
from fastapi import APIRouter, HTTPException, Path, Request, Body
from typing import Dict

from jose import JWTError
from pydantic import ValidationError

from app.models.procurement_models import Contract,ContractUpdate, ContractStatusUpdate, RequestedOrder, RequestedOrderUpdate

from app.services import procurement_requestedOrder_service
from app.services import procurement_contract_services
from app.services.procurement_contract_services import add_contract, update_contract

from app.services import procurement_return_services

from app.services import procurement_purchase_services

from app.models.procurement_models import PurchaseOrderValidationRequest
from app.services import procurement_validation_services

from app.services import procurement_salesreturn_services
from app.models.procurement_models import ReturnOrderSummary
from typing import List
from app.services.procurement_salesreturn_services import get_return_order_detail
from app.models.procurement_models import ReturnOrderDetail

from app.models.procurement_models import ReturnValidationRequest
from app.services.procurement_return_validation_services import validate_return_order

from app.models.procurement_models import LossOrder
from app.services import procurement_loss_services

from app.services.procurement_inventory_services import add_product_service,get_all_products,get_product_by_id,update_product_by_id,delete_product_service
from app.models.procurement_models import Product

from app.models.procurement_models import AdminSetupRequest
from app.services import procurement_setup_services

from app.services.procurement_dashboard_service import get_procurement_dashboard_data
from app.models.procurement_models import ProcurementDashboardResponse

router = APIRouter()

@router.get("/")
def root():
    return {"message": "Welcome to Optiven Procurement APIs"}

#RequestedOrders
@router.get("/requested-orders")
async def get_orders(request: Request):
    user = request.state.user

    if user.get("role") != "procurement":
        raise HTTPException(status_code=403, detail="Only procurement users are allowed.")
    storeId = user.get("store_id")
    return await procurement_requestedOrder_service.get_all_requested_orders(storeId)


# Add contract route
@router.post("/addContracts")
async def add_contract_route(contract: Contract, request: Request):
    try:
        user = request.state.user
        if user.get("role") != "procurement":
            raise HTTPException(status_code=403, detail="Only procurement users are allowed.")

        store_id = user.get("store_id")
        return await add_contract(contract, store_id)

    except ValidationError as e:
        logging.error("Validation error in route: %s", e.json())
        raise HTTPException(status_code=422, detail="Contract validation failed.")

    except Exception as e:
        logging.error("Unexpected error: %s", str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


#Update contract
@router.put("/updateContract/{contract_id}")
async def update_contract_route(
    request: Request, 
    contract_id: str ,
    updated_data: ContractUpdate
):
    user = request.state.user

    if user.get("role") != "procurement":
        raise HTTPException(status_code=403, detail="Only procurement users are allowed.")
    
    store_id = user.get("store_id")
    
    return await procurement_contract_services.update_contract(contract_id, store_id, updated_data)


#Status (Accept, Decline & Revoke)
@router.put("/contracts/status")
async def update_contract_status_route(
    request: Request,
    status_update: ContractStatusUpdate = Body(...)
):
    user = request.state.user
    if user.get("role") != "procurement":
        raise HTTPException(status_code=403, detail="Only procurement users are allowed.")

    store_id = user.get("store_id")
    return await procurement_contract_services.update_contract_status(
        status_update.contract_id, store_id, status_update.action
    )


#List of Contracts
@router.get("/contracts/request/{request_id}")
async def get_contracts_by_request_id_route(
    request_id: str,
    request: Request
):
    user = request.state.user
    if user.get("role") != "procurement":
        raise HTTPException(status_code=403, detail="Only procurement users are allowed.")
    
    store_id = user.get("store_id")
    return await procurement_contract_services.get_contracts_by_request_id(request_id, store_id)


#Veiw Contract details
@router.get("/viewContract/{contract_id}")
async def get_contract_by_id_route(
    contract_id: str,
    request: Request
):
    user = request.state.user
    if user.get("role") != "procurement":
        raise HTTPException(status_code=403, detail="Only procurement users are allowed.")

    store_id = user.get("store_id")
    return await procurement_contract_services.get_contract_by_id(contract_id, store_id)


#ReturnToVendor List
@router.get("/returnToVendor-list")
async def get_return_list(request: Request):
    user = request.state.user
    if user.get("role") != "procurement":
        raise HTTPException(status_code=403, detail="Only procurement users are allowed.")

    store_id = user.get("store_id")
    return await procurement_return_services.get_all_returns(store_id)


#ReturnToVendor Details
@router.get("/returnToVendor-details/{return_id}")
async def get_return_detail_by_id(request: Request, return_id: str):
    user = request.state.user
    if user.get("role") != "procurement":
        raise HTTPException(status_code=403, detail="Only procurement users are allowed.")

    store_id = user.get("store_id")
    return await procurement_return_services.get_return_by_id(store_id, return_id)


#List of Purchase Orders
@router.get("/purchase-orders")
async def get_purchase_orders(request: Request):
    user = request.state.user
    if user.get("role") != "procurement":
        raise HTTPException(status_code=403, detail="Only procurement users are allowed.")

    store_id = user.get("store_id")
    return await procurement_purchase_services.get_all_purchase_orders(store_id)


#Veiw the details of purchase order
@router.put("/purchase-orders/{order_id}/mark-received")
async def mark_as_received(order_id: str):
    return await procurement_purchase_services.mark_purchase_order_as_received(order_id)


#Validate the Purchase order
@router.post("/purchase-orders/validate")
async def validate_purchase_order_route(
    request: Request, data: PurchaseOrderValidationRequest = Body(...)
):
    user = request.state.user
    if user.get("role") != "procurement":
        raise HTTPException(status_code=403, detail="Only procurement users allowed.")

    store_id = user.get("store_id")
    org_id = user.get("org_id")  # If needed

    return await procurement_validation_services.validate_purchase_order(data, store_id, org_id)


#List of  Return orders from sales
@router.get("/return-orders", response_model=List[ReturnOrderSummary], tags=["Return Orders"])
async def get_all_return_orders(request: Request):
    user = request.state.user
    if user.get("role") != "procurement":
        raise HTTPException(status_code=403, detail="Forbidden: procurement access required.")
    
    store_id = user.get("store_id")
    return await procurement_salesreturn_services.get_return_orders_for_table_view(store_id)


#Veiw the details of Return orders 
@router.get("/return-orders-from-sales/{return_id}", response_model=ReturnOrderDetail, tags=["Return Orders"])
async def get_return_order_detail_view(return_id: str, request: Request):
    user = request.state.user
    if user.get("role") != "procurement":
        raise HTTPException(status_code=403, detail="Forbidden: procurement access required.")
    
    store_id = user.get("store_id")
    return await get_return_order_detail(return_id, store_id)


#Return order validation 
@router.post("/return-orders/validate-return-orders")
async def validate_return_order_route(
    request: Request,
    data: ReturnValidationRequest = Body(...)
):
    user = request.state.user

    if user.get("role") != "procurement":
        raise HTTPException(status_code=403, detail="Only procurement users allowed.")

    store_id = user.get("store_id")
    org_id = user.get("org_id")  # optional if needed for logging or constraints

    return await validate_return_order(data, store_id, org_id)


#List of loss orders 
@router.get("/loss-orders")
async def get_loss_orders(request: Request):
    user = request.state.user

    if not user or "store_id" not in user:
        raise HTTPException(status_code=401, detail="Unauthorized: store_id missing")

    if user["role"] != "procurement":
        raise HTTPException(status_code=403, detail="Forbidden: Procurement access required")

    store_id = user["store_id"]

    return await procurement_loss_services.get_loss_orders_by_store(store_id)


#Veiw loss  orders details by product_id
@router.get("/loss-orders/product/{product_id}")
async def get_loss_orders_by_product_id(product_id: str, request: Request):
    user = request.state.user

    if not user or "store_id" not in user:
        raise HTTPException(status_code=401, detail="Unauthorized: store_id missing")

    if user["role"] != "procurement":
        raise HTTPException(status_code=403, detail="Forbidden: Procurement access required")

    store_id = user["store_id"]

    return await procurement_loss_services.get_loss_orders_by_product_id(product_id, store_id)


#Inventory
@router.post("/add")
async def add_product(request: Request, product: Product):
    user = request.state.user  # Decoded JWT stored by middleware
    if user.get("role") != "Procurement":
        raise HTTPException(status_code=403, detail="Forbidden: Admin access required.")
    # admin_id = user.get("admin_id")
    inserted_id = await add_product_service(product)
    return {"message": "Product added successfully", "id": inserted_id}

@router.get("/all")
async def fetch_all_products_route(request: Request):
    # Role check
    user = request.state.user
    if not user or user.get("role") not in ["admin", "procurement"]:
        raise HTTPException(status_code=403, detail="Forbidden: Admin access required.")
    
    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID missing in token.")
    response = await get_all_products(store_id)
    print("Fetched products:", response)
    return response

@router.get("/one/{product_id}")
async def fetch_product_by_id(request: Request, product_id: str):
    # Admin role check
    user = request.state.user
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden: Admin access required.")

    # store_id = user.get("store_id")
    # if not store_id:
    #     raise HTTPException(status_code=400, detail="Store ID missing in token.")
    return await get_product_by_id(product_id)  
    # return await get_product_by_id(store_id)

@router.put("/edit/{product_id}")
async def edit_product(request: Request, product_id: str, data: Product):
    # Admin role check
    user = request.state.user
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden: Admin access required.")

    response = await update_product_by_id(product_id, data)
    print("Update response:", response)
    return response


@router.delete("/delete/{product_id}")
async def delete_product(request: Request, product_id: str):
    user = request.state.user
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden: Admin access required.")
    
    await delete_product_service(product_id)
    return {"message": f"Product with ID '{product_id}' deleted successfully"}


@router.patch("/setup")
async def admin_first_time_setup(request: Request, setup_data: AdminSetupRequest):
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
    updated_admin = await procurement_setup_services.update_admin_setup(admin_id, update_fields)

    if not updated_admin:
        raise HTTPException(status_code=404, detail="Admin not found or update failed")

    return updated_admin


#Dashboard
@router.get("/dashboard")
async def procurement_dashboard(request: Request):
    user = request.state.user

    if user.get("role") != "procurement":
        raise HTTPException(status_code=403, detail="Only procurement users allowed.")
    
    store_id = user.get("store_id")
    return await get_procurement_dashboard_data(store_id)

