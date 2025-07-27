from fastapi import APIRouter, HTTPException, Request, Query
from app.models.sales_model import EditOrderModel, ProductDetails, ReturnOrderRequest, ReturnedOrderModel, SalesOrderDetails, SalesOrderModel, LoginModel, RequestOrderModel, SendToProcurement
from app.services import sales_get_update_services
from typing import Any, List, Optional
from app.services import sales_add_raise_services
from app.services.sales_add_raise_services import raise_request_order_service
from app.services.sales_get_update_services import get_all_procurement_returns,get_procurement_return_by_id, get_product_details_service, get_sales_order_by_id
from app.services import sales_login_services as svc

router = APIRouter()

@router.get("/orders/received") 
async def get_orders(request: Request):
    user = request.state.user

    if not user or user.get("role") != "sales":
        raise HTTPException(status_code=403, detail="Forbidden: Sales access required.")
    
    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID missing in token.")

    orders = await sales_get_update_services.get_all_sales_orders(store_id)

    return {"orders": orders}

@router.get("/orders/sold") 
async def get_sold_orders(request: Request):
    user = request.state.user
    if not user or user.get("role") not in ["admin", "sales"]:
        raise HTTPException(status_code=403, detail="Forbidden: Sales access required.")
    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID missing in token.")
    orders = await sales_get_update_services.get_all_sold_orders(store_id)

    return {"orders": orders}

#Add order notification
@router.post("/orders/received/add") 
async def add_order(order: SalesOrderModel, request: Request):
    user = request.state.user

    if not user or user.get("role") not in ["sales"]:
        raise HTTPException(status_code=403, detail="Forbidden: Sales access required.")

    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID missing in token.")

    order_dict = order.model_dump()
    order_dict.pop("order_id", None)
    order_dict["store_id"] = store_id

    inserted_order_id = await sales_add_raise_services.add_sales_order(order_dict, store_id)
    return {"message": "Order added successfully", "order_id": inserted_order_id}

#successfully login notification
@router.post("/auth/login") 
async def login(login_data: LoginModel):
    res = await svc.login(login_data.email, login_data.password)
    if res is None:
        raise HTTPException(401, "Invalid email or password")
    return res


#order edited notification
@router.put("/orders/received/{order_id}") 
async def edit_order(order_id: str, order: EditOrderModel, request: Request):
    user = request.state.user

    if not user or user.get("role") != "sales":
        raise HTTPException(status_code=403, detail="Forbidden: Sales access required.")

    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID missing in token.")

    order_dict = order.model_dump(exclude_unset=True)
    order_dict["store_id"] = store_id

    updated_count = await sales_get_update_services.update_sales_order(order_id, store_id, order_dict)
    if updated_count == 0:
        raise HTTPException(status_code=404, detail="Order not found or no changes detected.")

    return {"message": "Order updated successfully", "order_id": order_id}


#order sold successfully notification
@router.put("/orders/received/{order_id}/sell") 
async def mark_order_as_sold(order_id: str, request: Request):
    user = request.state.user

    if not user or user.get("role") != "sales":
        raise HTTPException(status_code=403, detail="Forbidden: Sales access required.")

    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID missing in token.")

    updated_count = await sales_get_update_services.mark_order_as_sold(order_id, store_id)

    if updated_count == 0:
        raise HTTPException(status_code=404, detail="Order not found or already sold.")

    return {"message": "Order marked as sold successfully", "order_id": order_id}

#order deleted successfully notification
@router.delete("/orders/received/{order_id}") 
async def delete_order(order_id: str, request: Request):
    user = request.state.user

    if not user or user.get("role") != "sales":
        raise HTTPException(status_code=403, detail="Forbidden: Sales access required.")

    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID missing in token.")

    deleted_count = await sales_get_update_services.delete_order_by_id(order_id, store_id)

    if deleted_count == 0:
        raise HTTPException(status_code=404, detail="Order not found.")

    return {"message": "Order deleted successfully", "order_id": order_id}

@router.get("/orders/sold/{order_id}")
async def get_sold_order_by_id(order_id: str, request: Request):
    user = request.state.user

    if not user or user.get("role") not in ["admin", "sales"]:
        raise HTTPException(status_code=403, detail="Forbidden: Sales access required.")

    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID missing in token.")

    order = await sales_get_update_services.get_sold_order_by_id(order_id, store_id)

    if not order:
        raise HTTPException(status_code=404, detail="Sold order not found.")

    return {"order": order}


@router.get("/all") 
async def fetch_all_products_route(request: Request):
    user = request.state.user

    if not user or user.get("role") != "sales":
        raise HTTPException(status_code=403, detail="Forbidden: Sales access required.")

    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID missing in token.")

    response = await sales_get_update_services.get_all_products(store_id)
    print("Fetched products:", response)
    return {"products": response}

#order requested successfully notification 
@router.post("/orders/request/raise") 
async def raise_request_order(request_model: RequestOrderModel, request: Request):
    user = request.state.user

    if not user or user.get("role") != "sales":
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

#return added successfully notification
@router.post("/orders/returns/add", tags=["Sales"]) 
async def create_return_order(data: ReturnOrderRequest, request: Request):
    user = request.state.user

    if not user or user.get("role") != "sales":
        raise HTTPException(status_code=403, detail="Forbidden: Sales access required.")

    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID not found in token")

    return await sales_add_raise_services.add_return(data, store_id)

@router.get("/orders/returns", tags=["Sales"]) 
async def get_all_return_orders(request: Request):
    user = request.state.user
    if not user or user.get("role") != "sales":
        raise HTTPException(status_code=403, detail="Forbidden: Sales access required.")
    
    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID not found in token")
    returns = await sales_get_update_services.get_all_returns(store_id=store_id)
    return {"returns": returns}

# GET /orders/returns/{return_id} -> View More popup
@router.get("/orders/returns/{return_id}", tags=["Sales"]) 
async def get_return_order_details(return_id: str, request: Request):
    user = request.state.user

    # Check role
    if not user or user.get("role") != "sales":
        raise HTTPException(status_code=403, detail="Forbidden: Sales access required.")

    # Extract store_id from token
    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID not found in token")

    # Call service with store_id check
    return await sales_get_update_services.get_return_by_id(return_id, store_id)

#return deleted successfully notification
@router.delete("/orders/returns/{return_id}", tags=["Sales"])  
async def delete_return_order(return_id: str, request: Request):
    user = request.state.user

    if not user or user.get("role") != "sales":
        raise HTTPException(status_code=403, detail="Forbidden: Sales access required.")

    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID not found in token")

    return await sales_get_update_services.delete_return(return_id, store_id)

#sent to procurement successfully notification
@router.put("/orders/returns/procure/{return_id}", tags=["Sales"])
async def mark_as_sent_to_procurement(return_id: str, request: Request):
    user = request.state.user

    if not user or user.get("role") != "sales":
        raise HTTPException(status_code=403, detail="Forbidden: Sales access required.")

    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID not found in token")

    result = await sales_get_update_services.mark_return_sent_to_procurement(return_id, store_id)
    return result
 
@router.get("/procurement/returns") 
async def get_procurement_returns(request: Request):
    user = request.state.user
    if user.get("role") != "sales":
        raise HTTPException(status_code=403, detail="Only sales users are allowed.")
    storeId = user.get("store_id")
    return await get_all_procurement_returns(storeId )

@router.get("/procurement/returns/{return_id}", response_model=ReturnedOrderModel)
async def get_procurement_return_detail(return_id: str, request: Request):
    user = request.state.user
    if user.get("role") != "sales":
        raise HTTPException(status_code=403, detail="Only sales users are allowed.")
    storeId = user.get("store_id")
    result = await get_procurement_return_by_id(return_id , storeId )
    if not result:
        raise HTTPException(status_code=404, detail="Return order not found")
    return result

@router.get("/products/details", response_model=ProductDetails)
async def get_product_details(request: Request, product_id: Optional[str] = None, product_name: Optional[str] = None):
    user = request.state.user

    if not user or user.get("role") != "sales":
        raise HTTPException(status_code=403, detail="Forbidden: Sales access required.")

    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID missing in access token.")

    if not product_id and not product_name:
        raise HTTPException(status_code=400, detail="Either product_id or product_name is required")

    product = await get_product_details_service(store_id, product_id, product_name)
    return product

@router.get("/orders/{order_id}", response_model=Any)  # Using Any if response is a dict (not pydantic model)
async def get_order_by_id(order_id: str, request: Request):
    user = request.state.user

    # Role check
    if not user or user.get("role") != "sales":
        raise HTTPException(status_code=403, detail="Forbidden: Sales access required.")

    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Missing store_id in token")

    # Call updated service
    return await get_sales_order_by_id(order_id, store_id)

@router.get("/dashboard/summary")
async def get_sales_summary(request: Request):
    user = request.state.user

    if not user or user.get("role") != "sales":
        raise HTTPException(status_code=403, detail="Forbidden: Sales access required.")

    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID missing in token.")

    summary = await sales_get_update_services.get_sales_dashboard_summary(store_id)

    return summary
    