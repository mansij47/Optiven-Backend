from datetime import datetime
from typing import List, Union,Dict, Any
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class Product(BaseModel):
    org_id: Optional[str] = None
    store_id: Optional[str] = None
    product_name: Optional[str] = None
    product_id: Optional[str] = None #Auto generated unique ID (PROD001, PROD002 etc)
    unit: Optional[str] = None
    quantity: Optional[int] = None
    average_price: Optional[float] = 0.0  # Calculated from all items' unit_price
    average_selling_price: Optional[float] = 0.0  # Calculated from all items' selling_price
    
    min_stock: Optional[int] = 5  # Minimum stock level to trigger restock notification
    category: Optional[str] = None
    sub_category: Optional[str] = None
    tags: Optional[List[str]] = Field(default_factory=list)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
    status: Optional[str] = None
    type: Optional[str] = "order"  # "order" or "preorder" - defaults to "order" for regular inventory
    tax: Optional[float] = 0.0 # tax according to country wise 
   
    class ProductUpdateModel(BaseModel):
     org_id: Optional[str] = None
     store_id: Optional[str] = None
     product_name: Optional[str] = None
     product_id: Optional[str] = None #Auto generated unique ID (PROD001, PROD002 etc)
     unit: Optional[str] = None
     quantity: Optional[int] = None
     average_price: Optional[float] = 0.0  # Calculated from all items' unit_price
     average_selling_price: Optional[float] = 0.0 
     min_stock: Optional[int] = 5  # Minimum stock level to trigger restock notification
     category: Optional[str] = None
     sub_category: Optional[str] = None
     tags: Optional[List[str]] = Field(default_factory=list)
     updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
     created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
     status: Optional[str] = None
     type: Optional[str] = None  # "order" or "preorder"
     tax: Optional[float] = 0.0

class ProductItem(BaseModel):
    org_id: Optional[str] = None
    store_id: Optional[str] = None
    item_id: Optional[str] = None  # Auto-generated unique ID (ITEM001, ITEM002, etc.)
    product_id: Optional[str] = None  # Maps to parent product (e.g., iPhone product)
    item_name: Optional[str] = None
    unit_price: Optional[str] = "0"
    selling_price: Optional[str] = None  # Default: unit_price + 50
    vendor_id: Optional[str] = None  # Link to vendor
    vendor_name: Optional[str] = None 
    serial_no: Optional[str] = None
    batch_number: Optional[str] = None
    status: Optional[str] = "available"  # available, sold, returned, damaged
    
    # Warranty information
    has_warranty: Optional[bool] = False
    warranty_tenure: Optional[int] = 0
    warranty_unit: Optional[str] = ""
    
    # Return conditions
    is_consumer_returnable: Optional[bool] = False
    consumer_return_conditions: Optional[List[str]] = Field(default_factory=list)
    is_seller_returnable: Optional[bool] = False
    seller_return_conditions: Optional[List[str]] = Field(default_factory=list)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

# Combined model for directly adding product to inventory
# Individual item data for direct product addition
class ProductItemData(BaseModel):
    serial_no: Optional[str] = None
    batch_number: Optional[str] = None
    unit_price: str = "0"
    
    # Warranty information
    has_warranty: Optional[bool] = False
    warranty_tenure: Optional[int] = 0
    warranty_unit: Optional[str] = ""
    
    # Return conditions
    is_consumer_returnable: Optional[bool] = False
    consumer_return_conditions: Optional[List[str]] = Field(default_factory=list)
    is_seller_returnable: Optional[bool] = False
    seller_return_conditions: Optional[List[str]] = Field(default_factory=list)


class AddProductDirectRequest(BaseModel):
    # Product fields
    product_name: str
    unit: str = "pcs"
    category: str
    sub_category: Optional[str] = ""
    min_stock: int = 5
    tags: Optional[List[str]] = Field(default_factory=list)
    tax: Optional[float] = 0.0
    
    # Vendor fields (shared across all items)
    vendor_id: Optional[str] = None
    vendor_name: Optional[str] = None
    
    # Selling price (can be provided or auto-calculated)
    selling_price: Optional[str] = None
    
    # Items array - each item has its own serial, batch, warranty, and return conditions
    items: List[ProductItemData] = Field(default_factory=list)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class ProductItemUpdateModel(BaseModel):
     org_id: Optional[str] = None
     store_id: Optional[str] = None
     item_id: Optional[str] = None
     product_id: Optional[str] = None
     item_name: Optional[str] = None
     unit_price: Optional[str] = None
     selling_price: Optional[str] = None  # Can be updated
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
     updated_at: datetime = Field(default_factory=datetime.utcnow)  # Format: "YYYY-MM-DD HH:MM:SS"
     
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
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

#Profit Orders
class ProfitOrder(BaseModel):
    product_name: str
    category: str
    date_recorded: str
    quantity_sold: int
    unit: str
    unit_price: float  # Cost price
    selling_price: float  # Selling price
    profit_amount: Optional[float] = None  # Auto-calculated: (selling_price - unit_price) * quantity_sold
    order_id: Optional[str] = None  # Reference to sales order
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

       

class OrderProductInput(BaseModel): # type: ignore
    product_id: str
    quantity: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ReportResponse(BaseModel):
    total_loss: float
    total_profit: float
    chart_data: List[Dict[str, Any]]
    top_loss_products: List[Dict[str, Any]]
    top_profit_products: List[Dict[str, Any]]
    loss_table_data: List[Dict[str, Any]]
    profit_table_data: List[Dict[str, Any]]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


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
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)    
 

class AddressModel(BaseModel):
    location: str
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    pincode: Optional[str] = None
    phone: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
      

class DepartmentUserCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: str  # Made required since backend service expects it
    password: str
    role: str  # 'sales' or 'procurement'
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
   

class DepartmentUserResponse(BaseModel):
    id: str
    name: str
    email: EmailStr
    department: str
    status: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class DepartmentUserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    status: Optional[int] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class RaiseRequestOrderModel(BaseModel):
    order_id: str             # To fetch product info
    estimate_date: str        # Given by user in request  
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

#inventory mai naya product lane krne ke liye
class NewRaiseOrderRequest(BaseModel):
    product_name: str
    quantity: float
    unit: Optional[str] = "pcs"  # Default unit if not specified
    category: Optional[str] = "general"
    sub_category: Optional[str] = ""
    estimate_date: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    type: Optional[str] = "order"  # "order" or "preorder

class OrderProductInput(BaseModel):
    product_id: str
    quantity: int  
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

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
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class EditOrderProductInput(BaseModel):
    product_id: str
    quantity: int
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class EditOrderModel(BaseModel):
    customer_name: Optional[str]=None
    customer_phone: Optional[str]=None
    customer_email: Optional[str]=None
    order_date: Optional[datetime]=None
    delivery_address: Optional[str]=None
    delivery_date: Optional[datetime]=None
    gst_number: Optional[str]=None
    products: Optional[List[EditOrderProductInput]]=None   
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class NameModel(BaseModel):
    first_name: str= ""
    last_name: str= ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    
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
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


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
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)