from typing import List,Optional
from pydantic import BaseModel, EmailStr
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from typing import Literal
from pydantic import BaseModel
from typing import List, Optional
# from datetime import date

#Login 
class LoginModel(BaseModel):
    email: EmailStr
    password: str  

#Requested Order
class RequestedOrder(BaseModel):
    product_name: str
    quantity: int
    unit: str
    store_id: str
    org_id: str
    status: Optional[str] = "pending"
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)


class RequestedOrderUpdate(BaseModel):
    product_name: Optional[str]
    quantity: Optional[int]
    unit: Optional[str]
    status: Optional[str]

#Add Contracts
class Contract(BaseModel):
    contract_id: Optional[str] = None
    request_id: str
    vendor_name: str
    vendor_email: EmailStr
    phone: str
    address: str
    pincode: str
    business_type: str
    unit_price: float
    gst_number: str
    tax: float
    product_name: str
    quantity: int
    unit: str
    category: str
    sub_category: str
    tags: List[str]
    warranty_tenure: int
    warranty_unit: str
    date_of_delivery: str
    returnable: bool
    return_conditions: List[str]
    status: str

#Update Contracts
class ContractUpdate(BaseModel):
    contract_id: str= None
    vendor_name: Optional[str]= None
    vendor_email: Optional[EmailStr]= None
    phone: Optional[str]= None
    address: Optional[str]= None
    pincode: Optional[str]= None
    business_type: Optional[str]= None
    unit_price: Optional[float]= None
    gst_number: Optional[str]= None
    tax: Optional[float]= None
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
    status: Optional[str]= None


#Contract Status 
class ContractStatusUpdate(BaseModel):
    action: Literal["accept", "decline", "revoke"]
    contract_id: str


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

class ReturnToVendorResponse(BaseModel):
    return_id: str
    order_id: str
    vendor_name: str
    product_name: str
    delivery_date: str
    status: str
    return_amount: str

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


#Purchase Orders
class PurchaseOrderResponse(BaseModel):
    order_id: str
    contract_id: str
    supplier:str  = None
    delivery_date: str
    received_status: str
    validation_status: str
    amount: Optional[int] = None


#Delivery Status
class PurchaseOrderUpdateStatus(BaseModel):
    received_status: str    


#PurchaseOrder Validation
class PurchaseOrderValidationRequest(BaseModel):
    order_id: str
    contract_id: str
    delivery_date: str
    supplier_name: str
    expected_quantity: int
    received_quantity: int
    quantity_unit: str
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


#Return Orders From sales
class ReturnOrderSummary(BaseModel):
    order_id: str
    return_id: str
    product_name: str
    customer_name: str
    returned_amount: float
    action: str = "view"



class ProductDetails(BaseModel):
    product_id: str
    product_name: str
    quantity: int
    unit_price: float
    tax: float


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


#Return Validation
class ReturnValidationRequest(BaseModel):
    return_id: str


#Loss Orders
class LossOrder(BaseModel):
    product_name: str
    category: str
    date_reported: str
    quantity_lost: int
    unit: str
    unit_price: float
    reason: str


#Inventory
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
    unit: str
    quantity: int
    category: str
    sub_category: str
    tags: List[str]
    tax: float
    has_warranty: bool
    warranty_tenure: int
    warranty_unit: str
    last_updated: str
    status: Optional[str] = None    


class AdminSetupRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    profile_image: Optional[str] = None
    bio: Optional[str] = None
    password: Optional[str] = None    