from datetime import datetime
from typing import List, Union,Dict, Any
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


# class Product(BaseModel):
#     org_id: Optional[str] = None
#     store_id: Optional[str] = None
#     product_name: Optional[str] = None
#     is_consumer_returnable: Optional[bool] = False
#     consumer_return_conditions: Optional[List[str]] = Field(default_factory=list)
#     is_seller_returnable: Optional[bool] = False
#     seller_return_conditions: Optional[List[str]] = Field(default_factory=list)
#     unit_price: Optional[str] = "0"
#     unit: Optional[str] = None
#     quantity: Optional[int] = 0
#     category: Optional[str] = None
#     sub_category: Optional[str] = None
#     tags: Optional[List[str]] = Field(default_factory=list)
#     tax: Optional[float] = 0.0
#     has_warranty: Optional[bool] = False
#     warranty_tenure: Optional[int] = 0
#     warranty_unit: Optional[str] = ""
#     last_updated: Optional[datetime] = Field(default_factory=datetime.utcnow)
#     status: Optional[str] = None 

class Product(BaseModel):
    org_id: Optional[str] = None
    store_id: Optional[str] = None
    product_name: Optional[str] = None
    product_id: Optional[str] = None #Auto generated unique ID (PROD001, PROD002 etc)
    unit: Optional[str] = None
    quantity: Optional[int] = None
    average_price: Optional[float] = 0.0  # Calculated from all items' unit_price
    
    min_stock: Optional[int] = 5  # Minimum stock level to trigger restock notification
    category: Optional[str] = None
    sub_category: Optional[str] = None
    tags: Optional[List[str]] = Field(default_factory=list)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    status: Optional[str] = None
    tax: Optional[float] = 0.0 # tax according to country wise 
   
    class ProductUpdateModel(BaseModel):
     org_id: Optional[str] = None
     store_id: Optional[str] = None
     product_name: Optional[str] = None
     product_id: Optional[str] = None #Auto generated unique ID (PROD001, PROD002 etc)
     unit: Optional[str] = None
     quantity: Optional[int] = None
     average_price: Optional[float] = 0.0  # Calculated from all items' unit_price
     min_stock: Optional[int] = 5  # Minimum stock level to trigger restock notification
     category: Optional[str] = None
     sub_category: Optional[str] = None
     tags: Optional[List[str]] = Field(default_factory=list)
     updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
     created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
     status: Optional[str] = None
     tax: Optional[float] = 0.0

class ProductItem(BaseModel):
    org_id: Optional[str] = None
    store_id: Optional[str] = None
    item_id: Optional[str] = None  # Auto-generated unique ID (ITEM001, ITEM002, etc.)
    product_id: Optional[str] = None  # Maps to parent product (e.g., iPhone product)
    item_name: Optional[str] = None
    unit_price: Optional[str] = "0"
    vendor_id: Optional[str] = None  # Link to vendor
    vendor_name: Optional[str] = None 
    serial_no: Optional[str] = None
    batch_number: Optional[str] = None

class ProductItemUpdateModel(BaseModel):
     org_id: Optional[str] = None
     store_id: Optional[str] = None
     item_id: Optional[str] = None
     product_id: Optional[str] = None
     item_name: Optional[str] = None
     unit_price: Optional[str] = None
     vendor_id: Optional[str] = None
     vendor_name: Optional[str] = None
     serial_no: Optional[str] = None
     batch_number: Optional[str] = None

    # Return conditions
     is_consumer_returnable: Optional[bool] = False
     consumer_return_conditions: Optional[List[str]] = Field(default_factory=list)
     is_seller_returnable: Optional[bool] = False
     seller_return_conditions: Optional[List[str]] = Field(default_factory=list)
    
    # Warranty information
     has_warranty: Optional[bool] = False
     warranty_tenure: Optional[int] = 0
     warranty_unit: Optional[str] = ""
     updated_at: Optional[str] = Field(default_factory=datetime.utcnow)  # Format: "YYYY-MM-DD HH:MM:SS"
     


# class ProductUpdate(BaseModel):  # <- now this is importable
#     org_id: Optional[str] = None
#     store_id: Optional[str] = None
#     product_name: Optional[str] = None
#     is_consumer_returnable: Optional[bool] = None
#     consumer_return_conditions: Optional[List[str]] = None
#     is_seller_returnable: Optional[bool] = None
#     seller_return_conditions: Optional[List[str]] = None
#     unit_price: Optional[str] = None
#     unit: Optional[str] = None
#     quantity: Optional[int] = None
#     category: Optional[str] = None
#     sub_category: Optional[str] = None
#     tags: Optional[List[str]] = None
#     tax: Optional[int] = None
#     has_warranty: Optional[bool] = None
#     warranty_tenure: Optional[int] = None
#     warranty_unit: Optional[str] = None
#     last_updated: Optional[str] = None
#     status: Optional[str] = None
    
    

   

class LoginModel(BaseModel):
    email: EmailStr
    password: str  


#Loss Orders
class LossOrder(BaseModel):
    product_name: str
    category: str
    date_reported: str
    quantity_lost: int
    unit: str
    unit_price: float
    reason: str

       

class OrderProductInput(BaseModel): # type: ignore
    product_id: str
    quantity: int


class ReportResponse(BaseModel):
    total_loss: float
    total_profit: float
    chart_data: List[Dict[str, Any]]
    top_loss_products: List[Dict[str, Any]]
    top_profit_products: List[Dict[str, Any]]
    loss_table_data: List[Dict[str, Any]]
    profit_table_data: List[Dict[str, Any]]


class SalesOrderModel(BaseModel): # type: ignore
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
 

class AddressModel(BaseModel):
    location: str
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    pincode: Optional[str] = None
    phone: Optional[str] = None
      

class DepartmentUserCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: str  # Made required since backend service expects it
    password: str
    role: str  # 'sales' or 'procurement'
   

class DepartmentUserResponse(BaseModel):
    id: str
    name: str
    email: EmailStr
    department: str
    status: int
    created_at: datetime

class DepartmentUserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    status: Optional[int] = None

class RaiseRequestOrderModel(BaseModel):
    order_id: str             # To fetch product info
    estimate_date: str        # Given by user in request  

#inventory mai naya product lane krne ke liye
class NewRaiseOrderRequest(BaseModel):
    product_name: str
    quantity: float
    unit: Optional[str] = "pcs"  # Default unit if not specified
    category: Optional[str] = "general"
    sub_category: Optional[str] = ""
    estimate_date: Optional[str] = None

class OrderProductInput(BaseModel):
    product_id: str
    quantity: int  

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


class EditOrderProductInput(BaseModel):
    product_id: str
    quantity: int

class EditOrderModel(BaseModel):
    customer_name: Optional[str]=None
    customer_phone: Optional[str]=None
    customer_email: Optional[str]=None
    order_date: Optional[datetime]=None
    delivery_address: Optional[str]=None
    delivery_date: Optional[datetime]=None
    gst_number: Optional[str]=None
    products: Optional[List[EditOrderProductInput]]=None   

class NameModel(BaseModel):
    first_name: str= ""
    last_name: str= ""
    
    
class UserModel(BaseModel):
    id: str
    org_id: str
    store_id: str
    password: str
    email: EmailStr
    role: str = "admin"
    name: NameModel
    joining_date: str
    termination_date: Optional[Union[str, None]] = None
    status: int = 0
    first_login: bool = True
    extra: str= ""


class UserInfo(BaseModel):
    id: str
    store_id: str
    role: str
    email: EmailStr

#forgot password

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    user_id: str  # string version of ObjectId
    new_password: str = Field(..., min_length=6)