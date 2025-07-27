from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime

class Product(BaseModel):
    org_id: str
    store_id: str
    product_id: str
    product_name: str
    is_consumer_returnable: bool
    consumer_return_conditions: List[str]
    is_seller_returnable: bool
    seller_return_conditions: List[str]
    unit_price: str
    quantity: str
    category: str
    sub_category: str
    tags: List[str]
    tax: float
    has_warranty: bool
    warranty_tenure: int
    warranty_unit: str
    last_updated: str
    
class OrderProductInput(BaseModel):
    product_id: str
    quantity: int    

class EditOrderProductInput(BaseModel):
    product_id: str
    quantity: int

class EditOrderModel(BaseModel):
    customer_name: Optional[str]
    customer_phone: Optional[str]
    customer_email: Optional[str]
    order_date: Optional[datetime]
    delivery_address: Optional[str]
    delivery_date: Optional[datetime]
    gst_number: Optional[str]
    products: Optional[List[EditOrderProductInput]]

class SalesOrderModel(BaseModel):
    store_id: Optional[str] = None
    order_id: Optional[str] = None
    customer_id: Optional[str] = None
    customer_name: str
    customer_phone: str           # ✅ New field
    customer_email: EmailStr      # ✅ New field (validates email)
    order_date: datetime
    delivery_address: str
    delivery_date: datetime
    gst_number: str
    products: List[OrderProductInput]
    total_order_price: Optional[float] = None
    order_status: Optional[str] = "0"

class LoginModel(BaseModel):
    email: EmailStr
    password: str

class RequestOrderModel(BaseModel):
    order_id: str             # To fetch product info
    estimate_date: str        # Given by user in request 

class ReturnOrder(BaseModel):
    return_id: str
    order_id: str
    customer_id: str
    customer_name: str
    phone_no: int
    email: str
    product: List[Product]
    return_date: datetime
    is_customer_returnable: bool
    remarks: str
    reason: str
    sent_to_procurement: Optional[int] = Field(default=0, ge=0, le=1)
    store_id: Optional[str] = None  # Include this for injection

class SendToProcurement(BaseModel):
    return_id: str
    product_id: str
    product_name: str
    order_id: str
    remarks: str
    customer_id: str
    customer_name: str
    email: str
    phone_no: int
    return_date: datetime
    return_reason: str
    quantity:str
    unit_price:int
    tax: float
    return_amount:str

class ReturnOrderRequest(BaseModel):
    order_id: str
    reason: str
    remarks: Optional[str] = None
    return_quantity: int



class ReturnedProductModel(BaseModel):
    product_id: str
    product_name: str
    quantity: int
    unit_price: Optional[float] = None
    tax: Optional[float] = None  # present in DB

class ReturnedOrderModel(BaseModel):
    store_id: str
    organisation_id: Optional[str] = None
    return_id: str
    order_id: str
    customer_id: str
    customer_name: str
    phone_no: str
    email: str
    return_to: Optional[str] = None
    product: List[ReturnedProductModel]
    return_date: datetime
    reason: str
    is_customer_returnable: Optional[bool] = None
    returned_amount: Optional[float] = None
    remarks: Optional[str] = None
    sent_to_procurement: Optional[int] = None

class ProductDetails(BaseModel):
    product_id: str
    product_name: Optional[str]
    category: Optional[str]
    price: Optional[float]
    quantity_available: Optional[float]
    unit: Optional[str]
    store_id: Optional[str]  
    tax: Optional[float]  

class SalesProductItem(BaseModel):
    product_id: str
    product_name: Optional[str] = None
    quantity: str
    price: float

class SalesOrderDetails(BaseModel):
    order_id: str
    customer_name: str
    customer_id: str
    store_id: str
    order_status: str
    created_at: Optional[str] = None
    products: List[SalesProductItem]

