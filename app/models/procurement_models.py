from enum import Enum
from typing import List,Optional,Literal
from pydantic import BaseModel, EmailStr,Field, validator
from datetime import datetime
# from datetime import date

#Login 
class LoginModel(BaseModel):
    email: EmailStr
    password: str  

# vendor collection
class VendorModel(BaseModel):
    vendor_name: str
    email: EmailStr
    secondary_email: Optional[EmailStr] = None
    phone_number: str
    vendor_store_name:Optional[str]= None
    vendor_store_address: str
    pincode: str
    gst_number: str
    business_type: str
    tags: Optional[List[str]] = None
    created_at: Optional[datetime] = datetime.utcnow()
    updated_at: Optional[datetime] = datetime.utcnow()

class VendorUpdate(BaseModel):
    vendor_name: Optional[str] = None
    email: Optional[EmailStr] = None
    secondary_email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    vendor_store_name: Optional[str] = None
    vendor_store_address: Optional[str] = None
    pincode: Optional[str] = None
    gst_number: Optional[str] = None
    business_type: Optional[str] = None
    tags: Optional[List[str]] = None
    updated_at: Optional[datetime] = datetime.utcnow()

#Requested Order
class RequestedOrder(BaseModel):
    product_name: str
    quantity: int
    unit: str
    store_id: str
    org_id: str
    status: Optional[str] = "pending"
    type: Optional[str] = "order"  # "order" or "preorder"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class RequestedOrderUpdate(BaseModel):
    product_name: Optional[str]
    quantity: Optional[int]
    unit: Optional[str]
    status: Optional[str]
    type: Optional[str]  # "order" or "preorder"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
#Add Contracts
class Contract(BaseModel):
    contract_id: Optional[str] = None
    request_id: Optional[str] = None  # ✅ Optional to support direct PDF uploads
    vendor_name: str
    vendor_store_name: Optional[str] = None
    vendor_email: Optional[str] = None
    secondary_email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    pincode: Optional[str] = None
    business_type: Optional[str] = None
    base_price: Optional[float] = None
    unit_price: Optional[float] = None
    gst_number: Optional[str] = None
    vendor_tax: Optional[float] = None
    product_name: Optional[str] = None
    quantity: Optional[int] = None
    unit: Optional[str] = None
    category: Optional[str] = None
    sub_category: Optional[str] = None
    tags: Optional[List[str]] = None
    warranty_tenure: Optional[int] = None
    warranty_unit: Optional[str] = None
    date_of_delivery: Optional[str] = None
    returnable: Optional[bool] = None
    return_conditions: Optional[List[str]] = None
    is_damage_returnable: Optional[bool] = None
    uploaded_document_url: Optional[str] = None  # Cloudinary URL for uploaded contract document
    type: Optional[str] = "order"  # "order" or "preorder"
    status: Optional[str] = "pending"  # ✅ Made optional with default
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    
    @validator('base_price', 'unit_price', 'vendor_tax', pre=True)
    def round_to_two_decimals(cls, v):
        if v is not None:
            return round(float(v), 2)
        return v
    
#Update Contracts
class ContractUpdate(BaseModel):
    contract_id: str= None
    vendor_name: Optional[str]= None
    vendor_store_name: Optional[str]= None
    vendor_email: Optional[EmailStr]= None
    secondary_email: Optional[EmailStr]= None
    phone: Optional[str]= None
    address: Optional[str]= None
    pincode: Optional[str]= None
    business_type: Optional[str]= None
    base_price: Optional[float]= None
    unit_price: Optional[float]= None
    gst_number: Optional[str]= None
    vendor_tax: Optional[float]= None
    type: Optional[str]= None  # "order" or "preorder"
    product_name: Optional[str]= None
    quantity: Optional[int]= None
    unit: Optional[str]= None
    category: Optional[str]= None
    sub_category: Optional[str]= None
    tags: Optional[List[str]]= None
    warranty_tenure: Optional[int]= None
    warranty_unit: Optional[str]= None
    date_of_delivery: Optional[str]= None
    returnable: Optional[bool]= None
    return_conditions: Optional[List[str]]= None
    is_damage_returnable: Optional[bool] = None
    uploaded_document_url: Optional[str] = None  # Cloudinary URL for uploaded contract document

    status: Optional[str]= None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @validator('base_price', 'unit_price', 'vendor_tax', pre=True)
    def round_to_two_decimals(cls, v):
        if v is not None:
            return round(float(v), 2)
        return v

#Contract Status 
class ContractStatusUpdate(BaseModel):
    action: Literal["accept", "decline", "revoke"]
    contract_id: str
    vendor_email: Optional[str] = None
    secondary_email: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

#ReturnToVendor
class ReturnToVendorModel(BaseModel):
    return_id: str
    order_id: str
    vendor_name: str
    product_name: str
    delivery_date: str
    status: int
    return_amount: str
    original_quantity: int
    return_quantity: int
    unit: str
    contract_id: str
    purchase_date: str
    product_condition: str
    total_price: int
    unit_price: int
    return_reason: str
    store_id: Optional[str] = None
    org_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    @validator('total_price', 'unit_price', pre=True)
    def round_to_two_decimals(cls, v):
        if v is not None:
            return round(float(v), 2)
        return v
    
class ReturnToVendorResponse(BaseModel):
    return_id: str
    order_id: str
    vendor_name: Optional[str] = ""
    product_name: str
    delivery_date: Optional[str] = ""
    status: str
    return_amount: Optional[str] = "0"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
class ReturnToVendorDetail(BaseModel):
    contract_id: str
    return_id: str
    vendor_name: str  # Company
    total_price: float  # Price
    original_quantity: int  # Quantity received
    return_quantity: int  # Quantity Returned
    product_condition: str      
    returnable_condition: Optional[str] = None  # Whether damaged is returnable
    return_reason: Optional[str] = None  # Reason    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @validator('total_price', pre=True)
    def round_to_two_decimals(cls, v):
        if v is not None:
            return round(float(v), 2)
        return v

#Purchase Orders
class PurchaseOrderResponse(BaseModel):
    order_id: str
    contract_id: str
    vendor_id: Optional[str] = None
    vendor_name:str  = None
    vendor_email: Optional[str] = None
    secondary_email: Optional[str] = None
    delivery_date: str
    received_status: str
    validation_status: str
    amount: Optional[float] = None
    product_name: Optional[str] = None
    category: Optional[str] = None
    unit: Optional[str] = None
    quantity: Optional[int] = None
    base_price: Optional[float] = None
    unit_price: Optional[float] = None
    vendor_tax: Optional[float] = 0
    return_conditions: Optional[List[str]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @validator('amount', 'base_price', 'unit_price', 'vendor_tax', pre=True)
    def round_to_two_decimals(cls, v):
        if v is not None:
            return round(float(v), 2)
        return v

#Purchase Orders (Detail Response)
class PurchaseOrderDetailResponse(BaseModel):
    order_id: str
    contract_id: str
    vendor_id: Optional[str] = None
    vendor_name: Optional[str] = None
    vendor_email: Optional[str] = None
    secondary_email: Optional[str] = None
    delivery_date: str
    validation_status: str
    received_status: str
    product_name: Optional[str] = None
    amount: Optional[float] = None
    category: Optional[str] = None
    sub_category: Optional[str] = None
    unit: Optional[str] = None
    quantity_unit: Optional[str] = None
    expected_quantity: Optional[int] = None
    received_quantity: Optional[int] = None
    base_price: Optional[float] = None
    unit_price: Optional[float] = None
    vendor_tax: Optional[float] = 0
    is_product_damaged: Optional[bool] = None
    returnable: Optional[bool] = None
    return_conditions: Optional[List[str]] = []
    is_consumer_returnable: Optional[bool] = None
    consumer_return_conditions: Optional[List[str]] = []
    store_id: Optional[str] = None
    store_name: Optional[str] = None  # Added for PDF generation
    org_id: Optional[str] = None
    warranty_tenure: Optional[int] = None
    warranty_unit: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @validator('amount', 'base_price', 'unit_price', 'vendor_tax', pre=True)
    def round_to_two_decimals(cls, v):
        if v is not None:
            return round(float(v), 2)
        return v


#Delivery Status
class PurchaseOrderUpdateStatus(BaseModel):
    received_status: str    




#Return Orders From sales
class ReturnOrderSummary(BaseModel):
    order_id: str
    return_id: str
    product_name: str
    customer_name: str
    returned_amount: float
    status: str = "pending"
    action: str = "view"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @validator('returned_amount', pre=True)
    def round_to_two_decimals(cls, v):
        if v is not None:
            return round(float(v), 2)
        return v


class ProductDetails(BaseModel):
    product_id: str
    product_name: str
    quantity: int
    unit_price: float
    tax: float
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @validator('unit_price', 'tax', pre=True)
    def round_to_two_decimals(cls, v):
        if v is not None:
            return round(float(v), 2)
        return v

class ReturnOrderDetail(BaseModel):
    return_id: str
    order_id: str
    customer_id: str
    customer_name: str
    phone_no: Optional[str] = None
    email: Optional[str] = None
    product: List[ProductDetails]
    return_date: str
    is_customer_returnable: bool
    remarks: str
    reason: str
    returned_amount: Optional[float] = None
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
            # Remove time component if present (e.g., "2026-02-13T00:00:00" -> "2026-02-13")
            return v.split('T')[0]
        return v

    @validator('returned_amount', pre=True)
    def round_to_two_decimals(cls, v):
        if v is not None:
            return round(float(v), 2)
        return v

#Return Validation
class ReturnValidationRequest(BaseModel):
    return_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

#Loss Orders
class LossOrder(BaseModel):
    product_name: str
    category: str
    date_reported: str
    quantity_lost: int
    unit: str
    unit_price: float
    reason: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @validator('unit_price', pre=True)
    def round_to_two_decimals(cls, v):
        if v is not None:
            return round(float(v), 2)
        return v

#Inventory
# class Product(BaseModel):
#     org_id: str
#     store_id: str
#     product_id: str
#     product_name: str
#     is_consumer_returnable: bool
#     consumer_return_conditions: List[str]
#     is_seller_returnable: bool
#     seller_return_conditions: List[str]
#     unit_price: str
#     unit: str
#     quantity: int
#     category: str
#     sub_category: str
#     tags: List[str]
#     tax: float
#     has_warranty: bool
#     warranty_tenure: int
#     warranty_unit: str
#     last_updated: str
#     status: Optional[str] = None    


class AdminSetupRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    profile_image: Optional[str] = None
    bio: Optional[str] = None
    password: Optional[str] = None    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

#Dashboard
class MonthlyStats(BaseModel):
    month: str
    orders: int
    returns: int

class SupplierContract(BaseModel):
    name: str
    email: str
    value: str
    status: str

class ProcurementDashboardResponse(BaseModel):
    total_purchase_orders: int
    pending_validations: int
    active_contracts: int
    returns_initiated: int
    monthly_data: List[MonthlyStats]
    supplier_contracts: List[SupplierContract]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)    
#purchase order validation and submission
class TargetCollection(str, Enum):
    inventory = "Inventory"
    return_to_vendor = "ReturnToVendor"
    loss = "LossOrders"


class PurchaseOrderValidationRequest(BaseModel):
    order_id: str
    contract_id: str
    delivery_date: str
    vendor_name: str
    expected_quantity: int
    received_quantity: int
    unit: str
    is_product_damaged: bool
    returnable: bool
    return_conditions: Optional[List[str]] = []
    is_consumer_returnable: bool
    consumer_return_conditions: Optional[List[str]] = []
    unit_price: float
    category: str
    product_name: str
    sub_category: Optional[str] = None
    has_warranty: Optional[bool] = False
    warranty_tenure: Optional[int] = 0
    warranty_unit: Optional[str] = "months"
    tax: Optional[int] = 0
    product_id: Optional[str] = None
    selected_action: Optional[TargetCollection] = None   # ✅ new field
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @validator('unit_price', pre=True)
    def round_to_two_decimals(cls, v):
        if v is not None:
            return round(float(v), 2)
        return v

class PurchaseOrderValidationInput(BaseModel):
    order_id: str
    expected_quantity: int
    received_quantity: int
    is_product_damaged: bool
    selected_action: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
class ItemDetail(BaseModel):
    item_name: str
    serial_no: Optional[str] = None
    batch_number: Optional[str] = None
    unit_price: str = "0"
    selling_price: Optional[str] = None  # Default will be unit_price + 50
    # ✅ NEW: Item-level validation fields
    is_consumer_returnable: Optional[bool] = None
    consumer_return_conditions: Optional[List[str]] = []
    is_seller_returnable: Optional[bool] = None
    seller_return_conditions: Optional[List[str]] = []
    # ✅ NEW: Item damage status (for semi-damaged)
    is_damaged: Optional[bool] = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @validator('unit_price', 'selling_price', pre=True)
    def round_price_strings(cls, v):
        if v is not None and v != "0":
            try:
                return str(round(float(v), 2))
            except (ValueError, TypeError):
                return v
        return v

class PurchaseOrderSubmitRequest(BaseModel):
    order_id: str
    expected_quantity: int
    received_quantity: int
    min_quantity: Optional[int] = 4
    is_product_damaged: bool
    is_semi_damaged: Optional[bool] = False  # ✅ NEW: Semi-damaged flag
    selected_action: TargetCollection
    is_consumer_returnable: bool
    consumer_return_conditions: Optional[List[str]] = []
    items: Optional[List[ItemDetail]] = []  # ✅ Items edited by user
    type: Optional[str] = "order"  # "order" or "preorder" - defaults to "order" when validated    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# Purchase Order Email
class SendPurchaseOrderEmail(BaseModel):
    order_id: str
    recipient_emails: List[EmailStr]  # Can send to vendor_email and/or secondary_email
    subject: Optional[str] = "Purchase Order"
    message: Optional[str] = None  # Optional custom message
    created_at: datetime = Field(default_factory=datetime.utcnow)