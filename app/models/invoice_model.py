from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class ExtractionType(str, Enum):
    """Types of data to extract from invoice"""
    ALL = "all"
    VENDOR = "vendor"
    CUSTOMER = "customer"
    FINANCIAL = "financial"
    ITEMS = "items"
    PAYMENT = "payment"
    DATES = "dates"


class VendorModel(BaseModel):
    """Vendor/Seller information schema"""
    name: Optional[str] = Field(None, description="Vendor company name")
    store_name: Optional[str] = Field(None, description="Vendor store name")
    email: Optional[str] = Field(None, description="Vendor email address")
    phone: Optional[str] = Field(None, description="Vendor phone number")
    address: Optional[str] = Field(None, description="Vendor physical address")
    pincode: Optional[str] = Field(None, description="Vendor PIN/ZIP code")
    tax_id: Optional[str] = Field(None, description="Vendor tax ID (GST/VAT/EIN)")
    business_type: Optional[str] = Field(None, description="Business type (e.g., Retail, Wholesale)")
    # Product/Item fields - First product from invoice
    product_name: Optional[str] = Field(None, description="Product name from invoice")
    product_description: Optional[str] = Field(None, description="Product description")
    product_sku: Optional[str] = Field(None, description="Product SKU/Code")
    product_quantity: Optional[float] = Field(None, description="Product quantity")
    product_unit: Optional[str] = Field(None, description="Product unit (pcs, kg, box, etc.)")
    product_unit_price: Optional[float] = Field(None, description="Product unit price")
    product_discount: Optional[float] = Field(None, description="Product discount amount")
    product_tax: Optional[float] = Field(None, description="Product tax amount")
    product_total: Optional[float] = Field(None, description="Product total amount")
    product_category: Optional[str] = Field(None, description="Product category")


class CustomerModel(BaseModel):
    """Customer/Client information schema"""
    name: Optional[str] = Field(None, description="Customer name")
    email: Optional[str] = Field(None, description="Customer email address")
    phone: Optional[str] = Field(None, description="Customer phone number")
    address: Optional[str] = Field(None, description="Customer physical address")


class DateModel(BaseModel):
    """Date information schema"""
    invoice_date: Optional[str] = Field(None, description="Invoice issue date")
    due_date: Optional[str] = Field(None, description="Payment due date")
    issue_date: Optional[str] = Field(None, description="Issue date (alternative)")


class FinancialModel(BaseModel):
    """Financial summary schema"""
    subtotal: Optional[float] = Field(None, description="Subtotal amount")
    discount: Optional[float] = Field(None, description="Discount amount")
    shipping: Optional[float] = Field(None, description="Shipping cost")
    tax_rate: Optional[float] = Field(None, description="Tax rate percentage")
    tax_amount: Optional[float] = Field(None, description="Tax amount")
    total: Optional[float] = Field(None, description="Total amount")
    currency: Optional[str] = Field(None, description="Currency code (USD, EUR, etc.)")


class PaymentModel(BaseModel):
    """Payment information schema"""
    payment_terms: Optional[str] = Field(None, description="Payment terms")
    payment_method: Optional[str] = Field(None, description="Payment method")
    bank_name: Optional[str] = Field(None, description="Bank name")
    account_number: Optional[str] = Field(None, description="Bank account number")


class ItemModel(BaseModel):
    """Line item schema"""
    item_name: Optional[str] = Field(None, description="Item/Product name")
    quantity: Optional[float] = Field(None, description="Quantity")
    unit_price: Optional[float] = Field(None, description="Unit price")
    total: Optional[float] = Field(None, description="Line item total")


class ItemsModel(BaseModel):
    """Items collection schema"""
    items: List[ItemModel] = Field(default_factory=list, description="List of line items")
    item_count: int = Field(0, description="Total number of items")


class InvoiceDataModel(BaseModel):
    """Complete invoice data schema"""
    invoice_number: Optional[str] = Field(None, description="Invoice/Bill number")
    dates: Optional[DateModel] = None
    vendor: Optional[VendorModel] = None
    customer: Optional[CustomerModel] = None
    financial: Optional[FinancialModel] = None
    payment: Optional[PaymentModel] = None
    items_data: Optional[ItemsModel] = None
    document_type: Optional[str] = Field(None, description="Document type (invoice/quotation)")


class ExtractionResponse(BaseModel):
    """API response schema"""
    success: bool = Field(..., description="Whether extraction was successful")
    message: str = Field(..., description="Response message")
    data: Optional[InvoiceDataModel] = Field(None, description="Extracted invoice data")
    metadata: Optional[dict] = Field(None, description="Extraction metadata")
