from pydantic import BaseModel, EmailStr, Field, validator
from typing import List, Optional
from datetime import datetime

class CustomerModel(BaseModel):
    customer_id: str
    customer_name: str
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    total_orders: int = 0
    total_purchase_amount: float = 0.0
    total_purchase_quantity: int = 0
    payment_status: Optional[str] = None  # 'Paid' or 'Unpaid' based on latest order
    payment_date: Optional[datetime] = None  # ✅ Date when order was paid (sold)
    latest_order_id: Optional[str] = None  # ✅ Latest order ID for Mark as Paid functionality
    first_order_date: Optional[datetime] = None
    last_order_date: Optional[datetime] = None
    delivery_address: Optional[str] = None
    gst_number: Optional[str] = None
    store_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class CreateCustomerModel(BaseModel):
    customer_name: str
    customer_email: Optional[str] = None
    customer_phone: str  # Required for customer identity
    delivery_address: Optional[str] = None
    gst_number: Optional[str] = None

class UpdateCustomerModel(BaseModel):
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    delivery_address: Optional[str] = None
    gst_number: Optional[str] = None

class SellOrderProductItem(BaseModel):
    product_id: str
    product_name: str
    quantity: int
    unit_price: float
    tax: float

class SellOrderPayload(BaseModel):
    products: List[SellOrderProductItem]
    payment_status: str = "Paid"  # ✅ Default to 'Paid', can be 'Pay Later'
    shipping_charges: float = 0.0
    order_status: Optional[str] = "completed"
    created_by: Optional[dict] = None

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
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
class OrderProductInput(BaseModel):
    product_id: str
    product_name: Optional[str] = None  # For preorders when product_id is empty
    quantity: int
    category: Optional[str] = None  # Optional category
    unit: Optional[str] = "pcs"  # Optional unit, defaults to pcs
    selling_price: Optional[str] = None  # Selling price per unit
    consumer_return_conditions: Optional[List[str]] = [] 
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)   

class EditOrderProductInput(BaseModel):
    product_id: str
    quantity: int
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class EditOrderModel(BaseModel):
    customer_name: Optional[str]
    customer_phone: Optional[str]
    customer_email: Optional[str]
    order_date: Optional[datetime]
    delivery_address: Optional[str]
    delivery_date: Optional[datetime]
    gst_number: Optional[str]
    currency: Optional[str] = None  # ✅ Add currency field for updates
    products: Optional[List[EditOrderProductInput]]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class SalesOrderModel(BaseModel):
    store_id: Optional[str] = None
    order_id: Optional[str] = None
    customer_id: Optional[str] = None
    type: Optional[str] = "order"  # order | preorder
    customer_name: str
    customer_phone: str           # ✅ New field
    customer_email: EmailStr      # ✅ New field (validates email)
    order_date: datetime
    quotation_status: Optional[str] = "pending"  
    delivery_address: str
    delivery_date: datetime
    gst_number: str
    currency: Optional[str] = "INR"  # ✅ Currency field with default value
    products: List[OrderProductInput]
    total_order_price: Optional[float] = None
    order_status: Optional[str] = "0"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class LoginModel(BaseModel):
    email: EmailStr
    password: str

class RequestOrderModel(BaseModel):
    order_id: str             # To fetch product info
    estimate_date: str
    quantity: Optional[int] = None  # ✅ Optional: Override the requested quantity
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class ReturnOrder(BaseModel):
    return_id: str
    order_id: str
    customer_id: str
    customer_name: str
    phone_no: int
    email: str
    product: List[Product]
    return_date: str
    is_customer_returnable: bool
    remarks: str
    reason: str
    sent_to_procurement: Optional[int] = Field(default=0, ge=0, le=1)
    store_id: Optional[str] = None  # Include this for injection
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @validator('return_date', pre=True)
    def format_return_date(cls, v):
        """Ensure return_date is always in YYYY-MM-DD format"""
        if not v:
            return v
        if isinstance(v, datetime):
            return v.strftime('%Y-%m-%d')
        if isinstance(v, str):
            return v.split('T')[0]
        return v

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
    return_date: str
    return_reason: str
    quantity:str
    unit_price:int
    tax: float
    return_amount:str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @validator('return_date', pre=True)
    def format_return_date(cls, v):
        """Ensure return_date is always in YYYY-MM-DD format"""
        if not v:
            return v
        if isinstance(v, datetime):
            return v.strftime('%Y-%m-%d')
        if isinstance(v, str):
            return v.split('T')[0]
        return v

class ReturnOrderRequest(BaseModel):
    order_id: str
    reason: str
    remarks: Optional[str] = None
    return_quantity: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ReturnedProductModel(BaseModel):
    product_id: str
    product_name: str
    return_quantity: int
    unit_price: Optional[float] = None
    tax: Optional[float] = None
    is_customer_returnable: Optional[bool] = None
    consumer_return_conditions: Optional[List[str]] = []
    is_seller_returnable: Optional[bool] = None
    seller_return_conditions: Optional[List[str]] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
class ReturnedOrderModel(BaseModel):
    return_id: str
    order_id: str
    customer_id: str
    customer_name: str
    phone_no: str
    email: str
    product: List[ReturnedProductModel]
    return_date: str
    reason: str
    is_customer_returnable: Optional[bool] = None
    remarks: Optional[str] = None
    returned_amount: Optional[float] = None
    sent_to_procurement: Optional[int] = None
    store_id: str
    destination: Optional[str] = None  # ✅ Track where the return went (Inventory, LossOrders, ReturnToVendor)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @validator('return_date', pre=True)
    def format_return_date(cls, v):
        """Ensure return_date is always in YYYY-MM-DD format"""
        if not v:
            return v
        if isinstance(v, datetime):
            return v.strftime('%Y-%m-%d')
        if isinstance(v, str):
            return v.split('T')[0]
        return v
class ProductDetails(BaseModel):
    product_id: str
    product_name: Optional[str]
    category: Optional[str]
    price: Optional[float]
    quantity_available: Optional[float]
    unit: Optional[str]
    store_id: Optional[str]  
    tax: Optional[float]  
    consumer_return_conditions: Optional[List[str]]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
class SalesProductItem(BaseModel):
    product_id: str
    product_name: Optional[str] = None
    quantity: str
    price: float
    selling_price: Optional[float] = None  # Selling price used for profit calculation
    item_ids: Optional[List[str]] = None  # Array of item IDs (handles single or multiple)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
class SalesOrderDetails(BaseModel):
    order_id: str
    customer_name: str
    customer_id: str
    store_id: str
    order_status: str
    # created_at: Optional[str] = None
    products: List[SalesProductItem]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
