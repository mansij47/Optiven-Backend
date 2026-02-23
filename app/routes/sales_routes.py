from fastapi import APIRouter, HTTPException, Request, Query, BackgroundTasks
from app.models.sales_model import EditOrderModel, ProductDetails, ReturnOrderRequest, ReturnedOrderModel, SalesOrderDetails, SalesOrderModel, LoginModel, RequestOrderModel, SendToProcurement, SellOrderPayload
from app.services import sales_get_update_services
from typing import Any, Optional
from app.services import sales_add_raise_services
from app.services.sales_add_raise_services import raise_request_order_service
from app.services.sales_get_update_services import get_all_procurement_returns,get_procurement_return_by_id, get_product_details_service, get_sales_order_by_id
from app.services import sales_login_services as svc
from app.services import customer_services

router = APIRouter()

@router.get("/orders/received") 
async def get_orders(request: Request):
    user = request.state.user

    if not user or user.get("role") not in ["sales", "admin"]:
        raise HTTPException(status_code=403, detail="Forbidden: Sales or Admin access required.")
    
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

    if not user or user.get("role") not in ["sales", "admin"]:
        raise HTTPException(status_code=403, detail="Forbidden: Sales or Admin access required.")

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

    if not user or user.get("role") not in ["sales", "admin"]:
        raise HTTPException(status_code=403, detail="Forbidden: Sales or Admin access required.")

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
async def mark_order_as_sold(order_id: str, payload: SellOrderPayload, request: Request, background_tasks: BackgroundTasks):
    user = request.state.user

    if not user or user.get("role") != "sales":
        raise HTTPException(status_code=403, detail="Forbidden: Sales access required.")

    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID missing in token.")

    # Update order with all products data before marking as sold
    if payload.products:
        # Build the update payload with all products
        update_payload = {
            "products": [
                {
                    "product_id": prod.product_id,
                    "product_name": prod.product_name,
                    "order_quantity": prod.quantity,
                    "unit_price": prod.unit_price,
                    "tax": prod.tax,
                }
                for prod in payload.products
            ],
            "shipping_charges": payload.shipping_charges,
        }
        # Update the order with new product quantities/prices before marking as sold
        await sales_get_update_services.update_sales_order(order_id, store_id, update_payload)
    
    updated_count = await sales_get_update_services.mark_order_as_sold(
        order_id, 
        store_id,
        quantity=None,  # Not used anymore, we updated the order above
        price=None,
        tax=None,
        payment_status=payload.payment_status,
        background_tasks=background_tasks,
        created_by=payload.created_by
    )

    if updated_count == 0:
        raise HTTPException(status_code=404, detail="Order not found or already sold.")

    # Prepare notification sender info
    from app.models.notification_model import UserInfo, NotificationBase
    sender_info = {
        "id": user.get("id", "unknown"),
        "role": user.get("role"),
        "store_id": store_id
    }

    # Use the dynamic message for notification
    notification_message = "Order marked as sold successfully"
    notification = NotificationBase(
        sender=UserInfo(**sender_info),
        type_of_notification="Order Sold",
        title="Order Sold",
        message=notification_message,
    )

    # Send notification to both sales and admin
    from app.services.notification_service import create_notification
    notification_response = await create_notification(
        notification=notification,
        admin=True,
        sales=True
    )

    return {
        "message": notification_message,
        "order_id": order_id,
        "notification": notification_response
    }


# ✅ Mark pending (Pay Later) order as paid
@router.put("/orders/sold/{order_id}/mark-paid")
async def mark_pending_as_paid(order_id: str, request: Request):
    user = request.state.user

    if not user or user.get("role") not in ["sales", "admin"]:
        raise HTTPException(status_code=403, detail="Forbidden: Sales or Admin access required.")

    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID missing in token.")

    result = await sales_get_update_services.mark_pending_order_as_paid(order_id, store_id)
    return result


#order deleted successfully notification
@router.delete("/orders/received/{order_id}") 
async def delete_order(order_id: str, request: Request):
    user = request.state.user

    if not user or user.get("role") != "sales" and user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden: Sales or Admin access required.")

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


@router.get("/orders/sold/{order_id}/download-pdf")
async def download_sold_order_pdf(order_id: str, request: Request):
    """
    Download sold order as PDF
    """
    user = request.state.user

    if not user or user.get("role") not in ["admin", "sales"]:
        raise HTTPException(status_code=403, detail="Forbidden: Sales access required.")

    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID missing in token.")

    return await sales_get_update_services.generate_sold_order_pdf_service(order_id, store_id)


@router.get("/orders/received/{order_id}/download-pdf")
async def download_received_order_pdf(order_id: str, request: Request):
    """
    Download received order (quotation) as PDF
    """
    user = request.state.user

    if not user or user.get("role") not in ["admin", "sales"]:
        raise HTTPException(status_code=403, detail="Forbidden: Sales access required.")

    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID missing in token.")

    return await sales_get_update_services.generate_received_order_pdf_service(order_id, store_id)


@router.get("/all") 
async def fetch_all_products_route(request: Request):
    user = request.state.user

    if not user or user.get("role") != "sales":
        raise HTTPException(status_code=403, detail="Forbidden: Sales access required.")

    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID missing in token.")

    response = await sales_get_update_services.get_all_products(store_id)
   
    return {"products": response}

#order requested successfully notification 
@router.post("/orders/request/raise") 
async def raise_request_order(request_model: RequestOrderModel, request: Request):
    user = request.state.user

    if not user or user.get("role") not in ["sales", "admin"]:
        raise HTTPException(status_code=403, detail="Forbidden: Sales or Admin access required.")

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
        requester=requester,
        quantity_override=request_model.quantity  # ✅ Pass the user-provided quantity
    )

    # ✅ Check if the order is a preorder to send priority notification
    try:
        from app.db import db
        order = await db.SalesOrders.find_one({"order_id": request_model.order_id, "store_id": store_id})
        is_preorder = order and order.get("type") == "preorder"
        
        
        
        # ✅ Send notification to procurement
        from app.models.notification_model import UserInfo, NotificationBase
        from app.services.notification_service import create_notification
        
        if is_preorder:
            notification_title = " Priority: Preorder Request Raised"
            notification_message = f"Preorder request created by Sales ( {request_id})."
            notification_type = "Preorder Request"
        else:
            notification_title = "New Request from Sales"
            notification_message = f"Sales has raised a new request ( {request_id})."
            notification_type = "Order Request"
        
       
        
        notification = NotificationBase(
            sender=UserInfo(
                role=requester["role"],
                id=requester["id"],
                store_id=store_id  # Include store_id in sender info
            ),
            type_of_notification=notification_type,
            title=notification_title,
            message=notification_message,
        )

        notification_response = await create_notification(
            notification=notification,
            procurement=True  # Send only to procurement
        )
        
       

        return {
            "message": "Request raised successfully",
            "request_id": request_id,
            "notification": notification_response
        }
    except Exception as e:
        print(f"[ERROR] Failed to send notification: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Still return success for the request, even if notification fails
        return {
            "message": "Request raised successfully",
            "request_id": request_id,
            "notification": {"error": str(e)}
        }

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
    if not user or user.get("role") not in ["sales", "admin"]:
        raise HTTPException(status_code=403, detail="Forbidden: Sales or Admin access required.")
    
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
async def get_procurement_returns(request: Request, status: str = "all"):
    user = request.state.user
    if user.get("role") not in ["sales","procurement"]:
        raise HTTPException(status_code=403, detail="Only sales users are allowed.")
    if user.get("role") in ["sales","procurement"]:
        store_id = user.get("store_id")
    return await get_all_procurement_returns(store_id, status)


@router.get("/procurement/returns/{return_id}", response_model=ReturnedOrderModel)
async def get_procurement_return_detail(return_id: str, request: Request):
    user = request.state.user
    if user.get("role") not in ["sales","procurement"]:
        raise HTTPException(status_code=403, detail="Only sales users are allowed.")
    if user.get("role") in ["sales","procurement"]:
        storeId = user.get("store_id")
    result = await get_procurement_return_by_id(return_id , storeId )
    if not result:
        raise HTTPException(status_code=404, detail="Return order not found")

    return result

@router.get("/products/details", response_model=ProductDetails)
async def get_product_details(request: Request, product_id: Optional[str] = None, product_name: Optional[str] = None):
    user = request.state.user

    if not user or user.get("role") not in ["sales", "admin"]:
        raise HTTPException(status_code=403, detail="Forbidden: Sales or Admin access required.")

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
    if not user or user.get("role") not in ["sales", "admin"]:
        raise HTTPException(status_code=403, detail="Forbidden: Sales or Admin access required.")

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
    
@router.get("/dashboard/sold-orders-by-month")
async def sold_orders_by_month(request: Request):
    user = request.state.user

    if not user or user.get("role") != "sales":
        raise HTTPException(status_code=403, detail="Forbidden: Sales access required.")

    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID missing in token.")

    data = await sales_get_update_services.get_sold_orders_by_month(store_id)
    return data


@router.get("/dashboard/return-orders-by-month")
async def return_orders_by_month(request: Request):
    user = request.state.user

    if not user or user.get("role") != "sales":
        raise HTTPException(status_code=403, detail="Forbidden: Sales access required.")

    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID missing in token.")

    data = await sales_get_update_services.get_return_orders_by_month(store_id)
    return data


# Customer routes
@router.get("/customers")
async def get_all_customers(request: Request):
    """Get all customers with aggregated purchase data"""
    user = request.state.user

    if not user or user.get("role") not in ["sales", "admin"]:
        raise HTTPException(status_code=403, detail="Forbidden: Sales or Admin access required.")

    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID missing in token.")

    customers = await customer_services.get_all_customers(store_id=store_id)
    return {"customers": customers}


@router.get("/customers/{customer_id}")
async def get_customer_details(customer_id: str, request: Request):
    """Get detailed customer information including order history"""
    user = request.state.user

    if not user or user.get("role") not in ["sales", "admin"]:
        raise HTTPException(status_code=403, detail="Forbidden: Sales or Admin access required.")

    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID missing in token.")

    customer = await customer_services.get_customer_by_id(customer_id, store_id=store_id)
    return customer


@router.get("/validate-phone/{phone_number}")
async def validate_customer_phone(phone_number: str, request: Request):
    """Validate phone number and return existing customer details if found"""
    user = request.state.user

    if not user or user.get("role") not in ["sales", "admin"]:
        raise HTTPException(status_code=403, detail="Forbidden: Sales or Admin access required.")

    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID missing in token.")

    from app.services.sales_add_raise_services import find_customer_by_phone
    existing_customer = await find_customer_by_phone(phone_number, store_id=store_id)
    
    if existing_customer:
        return {
            "exists": True,
            "customer": existing_customer
        }
    
    return {"exists": False}


@router.get("/customers/search")
async def search_customers(query: str = Query(..., min_length=1), request: Request = None):
    """Search customers by name, email, or phone"""
    user = request.state.user

    if not user or user.get("role") not in ["sales", "admin"]:
        raise HTTPException(status_code=403, detail="Forbidden: Sales or Admin access required.")

    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID missing in token.")

    customers = await customer_services.search_customers(query, store_id=store_id)
    return {"customers": customers}


@router.post("/customers")
async def create_customer(customer: dict, request: Request):
    """Create a new customer"""
    user = request.state.user

    if not user or user.get("role") not in ["sales", "admin"]:
        raise HTTPException(status_code=403, detail="Forbidden: Sales or Admin access required.")

    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID missing in token.")

    result = await customer_services.create_customer(customer, store_id=store_id)
    return result


@router.patch("/customers/{customer_phone}")
async def update_customer(customer_phone: str, customer_data: dict, request: Request):
    """Update customer information by phone number"""
    user = request.state.user

    if not user or user.get("role") not in ["sales", "admin"]:
        raise HTTPException(status_code=403, detail="Forbidden: Sales or Admin access required.")

    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID missing in token.")

    result = await customer_services.update_customer(customer_phone, customer_data, store_id=store_id)
    return result


@router.delete("/customers/{customer_phone}")
async def delete_customer(customer_phone: str, request: Request):
    """Delete customer and all associated orders"""
    user = request.state.user

    if not user or user.get("role") not in ["sales", "admin"]:
        raise HTTPException(status_code=403, detail="Forbidden: Sales or Admin access required.")

    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID missing in token.")

    result = await customer_services.delete_customer(customer_phone, store_id=store_id)
    return result
