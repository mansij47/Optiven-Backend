from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from datetime import datetime
from bson import ObjectId


class Address(BaseModel):
    location: str
    city: str
    state: str
    country: str
    pincode: str
    phone: str

class AdminName(BaseModel):
    first_name: str
    Last_name: str

class DepartmentEntry(BaseModel):
    department: str
    employee_id: str

class StoreDetails(BaseModel):
    org_id: str
    store_id: str
    store_name: str
    gst_number: str
    buisness_type: str
    social_media: str
    website: str
    address: Address
    admin_id: str
    store_email: str
    password: str
    status: int
    created_at: str
    updated_at: str
    admin_name: AdminName
    departments: List[DepartmentEntry]

class StoreSetupUpdate(BaseModel):
    org_id: Optional[str] = None
    store_name: Optional[str] = None
    gst_number: Optional[str] = None
    buisness_type: Optional[str] = None
    social_media: Optional[str] = None
    website: Optional[str] = None
    address: Optional[Address] = None
    admin_id: Optional[str] = None
    store_email: Optional[str] = None
    status: Optional[int] = None
    department: Optional[Dict[str, list]] = None

class StoreUpdate(BaseModel):
    org_id: Optional[str] = None
    store_name: Optional[str] = None
    gst_number: Optional[str] = None
    buisness_type: Optional[str] = None
    social_media: Optional[str] = None
    website: Optional[str] = None
    address: Optional[Address] = None
    admin_id: Optional[str] = None
    store_email: Optional[str] = None
    status: Optional[int] = None

class StaffInput(BaseModel):
    staff_id: str
    joining_date: str
    termination_date: Optional[str] = ""
    status: int