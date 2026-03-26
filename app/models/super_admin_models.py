from datetime import datetime
import re
from pydantic import BaseModel, EmailStr, validator
from typing import List, Optional, Literal, Union

# ──────────────────────────────────────────
#  A.  COMMON / REUSABLE NESTED MODELS
# ──────────────────────────────────────────
class AddressModel(BaseModel):
    location: str
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    pincode: Optional[str] = None
    phone: Optional[str] = None

class DeptStaffModel(BaseModel):
    joining_date: Optional[str] = None
    termination_date: Optional[str] = None
    staff_id: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    status: Optional[str] = None

class SubCategoryEmbedded(BaseModel):
    sub_category_id: str
    sub_category_name: str
    tags: List[str]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class NameModel(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None

# ──────────────────────────────────────────
#  B.  AUTH / PROFILE  (SuperAdmins)
# ──────────────────────────────────────────
class SuperAdminSignupModel(BaseModel):
    id: Optional[str] = None
    email: EmailStr                       
    password: str                                                    
    org_id: Optional[str] = "SUPER_ADMIN"  # default org_id for super admin
    store_id: Optional[str] = "SUPER_ADMIN"  # default store_id for super admin
    role: Optional[str] = None
    name: Optional[NameModel] = None
    joining_date: Optional[str] = None
    termination_date: Optional[str] = None
    status: Optional[int] = None

class SignupModel(BaseModel):
    id: Optional[str] = None
    email: EmailStr                       
    password: str         
    #to be removed optional from store and org id                                           
    org_id: Optional[str] = None  # default org_id for super admin
    store_id: Optional[str] = None  # default store_id for super admin
    role: Optional[str] = None
    name: Optional[NameModel] = None
    joining_date: Optional[str] = None
    termination_date: Optional[str] = None
    status: Optional[int] = None
    id: Optional[str] = None
    email: EmailStr                       
    password: str         
    #to be removed optional from store and org id                                           
    org_id: Optional[str] = None  # default org_id for super admin
    store_id: Optional[str] = None  # default store_id for super admin
    role: Optional[str] = None
    name: Optional[NameModel] = None
    joining_date: Optional[str] = None
    termination_date: Optional[str] = None
    status: Optional[int] = None


class LoginModel(BaseModel):
    email: EmailStr
    password: str

class UpdateProfileModel(BaseModel):
    # id: Optional[str] = None
    name: Optional[NameModel] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    bio: Optional[str] = None
    profile_image: Optional[str] = None
    store_id: Optional[str] = None

class ChangePasswordModel(BaseModel):
    old_password: str
    new_password: str


class SetPasswordRequest(BaseModel):
    token: str
    new_password: str
    confirm_password: str

    @validator("new_password")
    def validate_new_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Z]", value):
            raise ValueError("Password must include at least one uppercase letter")
        if not re.search(r"[a-z]", value):
            raise ValueError("Password must include at least one lowercase letter")
        if not re.search(r"\d", value):
            raise ValueError("Password must include at least one number")
        if not re.search(r"[^A-Za-z0-9]", value):
            raise ValueError("Password must include at least one special character")
        return value

    @validator("confirm_password")
    def validate_confirm_password(cls, value: str, values: dict) -> str:
        new_password = values.get("new_password")
        if new_password is not None and value != new_password:
            raise ValueError("confirm_password must match new_password")
        return value





# ──────────────────────────────────────────
#  C.  STORE  (Stores collection)
# ──────────────────────────────────────────

class CategoryModel(BaseModel):
    id: str
    name: str



class CategoryModel(BaseModel):
    id: str
    name: str


class CreateStoreModel(BaseModel):
    # full Stores schema; * required by UI
    org_id: Optional[str]= None            # filled by service
    store_id: Optional[str] = None                         # *
    org_id: Optional[str]= None            # filled by service
    store_id: Optional[str] = None                         # *
    store_name: str                       # *new
    gst_number: str                       # *
    buisness_type: Optional[str] = None
    social_media: Optional[str] = None
    website: Optional[str] = None
    address: AddressModel                 # *
    admin_id: Optional[str] = None        # backend-generated (ADM001 format)
    store_email: str                      # *
    password: Optional[str] = None        # optional for set-password-link onboarding
    status: Optional[int] = 0             # 0=draft
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    admin_name: NameModel
    departments: Optional[List[DeptStaffModel]] = []   # optional per collection# subcategory IDs for scalability
    category_ids: Optional[List[CategoryModel]] = []
    category_ids: Optional[List[CategoryModel]] = []
    subcategory_ids: Optional[List[str]] = []
 
# class Department(BaseModel):
#     department: str
#     employee_id: str
# class Department(BaseModel):
#     department: str
#     employee_id: str

class StoreUpdate(BaseModel):
    org_id: Optional[str] = None
    store_id: Optional[str] = None
    store_name: Optional[str] = None
    gst_number: Optional[str] = None
    buisness_type: Optional[str] = None
    social_media: Optional[str] = None
    website: Optional[str] = None
    address: Optional[AddressModel] = None
    admin_id: Optional[str] = None
    store_email: Optional[str] = None
    password: Optional[str] = None
    status: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    admin_name: Optional[NameModel] = None
    departments: Optional[List[DeptStaffModel]] = None
    category_ids: Optional[List[CategoryModel]]= None
    subcategory_ids: Optional[List] = None
    org_id: Optional[str] = None
    store_id: Optional[str] = None
    store_name: Optional[str] = None
    gst_number: Optional[str] = None
    buisness_type: Optional[str] = None
    social_media: Optional[str] = None
    website: Optional[str] = None
    address: Optional[AddressModel] = None
    admin_id: Optional[str] = None
    store_email: Optional[str] = None
    password: Optional[str] = None
    status: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    admin_name: Optional[NameModel] = None
    departments: Optional[List[DeptStaffModel]] = None
    category_ids: Optional[List[CategoryModel]]= None
    subcategory_ids: Optional[List] = None

class EditStoreModel(CreateStoreModel):
    """All fields optional for PUT /store/{id}.
    everything working fine also id if not included in json while put patch noissue and mandory fileds are must"""
    org_id: Optional[str] = None
    store_id: Optional[str] = None
    name: Optional[str] = None
    gst_number: Optional[str] = None
    admin_id: Optional[str] = None
    address: Optional[AddressModel] = None
    

class StoreIdsModel(BaseModel):
    store_ids: List[str]

class StoreIdsModel(BaseModel):
    store_ids: List[str]


class UpdateStoreStatusModel(BaseModel):
    status: Literal[0, 1, 2]  # 0=draft 1=active 2=disabled

class UserModel(BaseModel):
    id: str
    org_id: str
    store_id: str
    password: str
    email: EmailStr
    phone: str
    bio : Optional[str] = None
    profile_image: Optional[str] = None
    role: str = "admin"
    role: str = "admin"
    name: NameModel
    joining_date: datetime  
    termination_date: Optional[Union[str, None]] = None
    status: int = 0
    first_login: bool = True
    extra: str = ""

class UpdateUserModel(BaseModel):
    id: Optional[str] = None
    org_id: Optional[str] = None
    store_id: Optional[str] = None
    # password: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    bio: Optional[str] = None
    profile_image: Optional[str] = None
    role: Optional[str] = None
    name: Optional[NameModel] = None
    joining_date: Optional[str] = None
    termination_date: Optional[Union[str, None]] = None


class SetPasswordStatusRequest(BaseModel):
    token: str
    status: Optional[int] = None
    first_login: Optional[bool] = None
    extra: Optional[str] = None


class SetPasswordResendRequest(BaseModel):
    token: str

# ──────────────────────────────────────────
#  D.  CATEGORY  (Categories collection)
# ──────────────────────────────────────────
class AddSubcategoryModel(BaseModel):
    # full embedded object
    sub_category_id: str
    sub_category_name: str
    tags: List[str]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

# class AddCategoryModel(BaseModel):
#     # every Categories field
#     store_id: Optional[str] = None            # filled by service
#     category_id: str
#     category_name: str
#     description: Optional[str] = None
#     icon: Optional[str] = None
#     tags: Optional[List[str]] = []
#     sub_categories: Optional[List[SubCategoryEmbedded]] = []
#     created_at: Optional[str] = None
#     updated_at: Optional[str] = None


class SubCategoryEmbedded(BaseModel):
    sub_category_id: Optional[str] = None
    sub_category_name: str
    tags: Optional[List[str]] = []
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class AddCategoryModel(BaseModel):
    category_id: Optional[str] = None
    category_name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    tags: Optional[List[str]] = []
    sub_categories: Optional[List[SubCategoryEmbedded]] = []
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    sub_category_count: Optional[int] = 0  # count of subcategories, optional for UI

class EditCategoryModel(AddCategoryModel):
    category_id: Optional[str] = None
    category_name: Optional[str] = None
    tags: Optional[List[str]] = None
    sub_categories: Optional[List[SubCategoryEmbedded]] = None

class EditSubcategoryModel(AddSubcategoryModel):
    sub_category_name: Optional[str] = None
    tags: Optional[List[str]] = None

# ──────────────────────────────────────────
#  E.  STORE INVITATION  (StoreInvitations)
# ──────────────────────────────────────────
class StoreInvitationModel(BaseModel):
    store_id: Optional[str] = None            # set in service
    email: EmailStr
    temp_password: str
    sent_at: Optional[str] = None

# ──────────────────────────────────────────
#  F. HELP  (Help collection)
# ──────────────────────────────────────────
class HelpModel(BaseModel):
    requested_by: Optional[dict] = None                        # {"role": str, "id": str}
    title: str
    message: str
    submitted_at: Optional[str] = None