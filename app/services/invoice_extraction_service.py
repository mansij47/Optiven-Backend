"""
Invoice Extraction Service
Extracts text from PDF, then validates with LLM
"""

from pathlib import Path
from typing import Dict, Any
import re

from app.utils.pdf_invoice_utils import (
    extract_pdf_text,
    clean_text,
    normalize_number,
    PATTERN_EMAIL,
    PATTERN_PHONE,
    PATTERN_GST_IN,
    PATTERN_CURRENCY,
    PATTERN_AMOUNT,
    PATTERN_DATE
)
from app.utils.llm_helper import validate_and_enhance
from app.models.invoice_model import (
    VendorModel,
    CustomerModel,
    DateModel,
    FinancialModel,
    PaymentModel,
    ItemModel,
    ItemsModel,
    InvoiceDataModel,
    ExtractionType
)


# ===================== UTILITY FUNCTIONS =====================
def clean_extracted_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Clean extracted data to ensure proper types
    Converts string 'null' to None, validates numeric fields
    """
    cleaned = {}
    
    # Define numeric fields that should be float or None
    numeric_fields = [
        'product_quantity', 'product_unit_price', 'product_discount',
        'product_tax', 'product_total', 'subtotal', 'discount',
        'shipping', 'tax_rate', 'tax_amount', 'total', 'quantity',
        'unit_price'
    ]
    
    for key, value in data.items():
        # Handle string 'null' or empty strings
        if value in ['null', 'None', '', 'undefined']:
            cleaned[key] = None
            continue
        
        # Handle numeric fields
        if key in numeric_fields:
            if value is None:
                cleaned[key] = None
            elif isinstance(value, (int, float)):
                cleaned[key] = float(value)
            elif isinstance(value, str):
                # Try to parse string to number
                try:
                    cleaned[key] = float(value.replace(',', '').strip())
                except (ValueError, AttributeError):
                    cleaned[key] = None
            else:
                cleaned[key] = None
        else:
            # For non-numeric fields, just pass through
            cleaned[key] = value
    
    return cleaned


# Extract vendor data - basic patterns
def extract_vendor_fields(text: str, tables: list = None) -> Dict[str, Any]:
    data = {
        'name': None,
        'store_name': None,
        'email': None,
        'phone': None,
        'address': None,
        'pincode': None,
        'tax_id': None,
        'business_type': None,
        'product_name': None,
        'product_description': None,
        'product_sku': None,
        'product_quantity': None,
        'product_unit': None,
        'product_unit_price': None,
        'product_discount': None,
        'product_tax': None,
        'product_total': None,
        'product_category': None
    }
    
    lines = text.split('\n')
    
    # Name - first valid line that looks like a company name
    for line in lines[:20]:
        clean_line = clean_text(line)
        if len(clean_line) > 3 and not re.search(r'invoice|date|number|total', clean_line, re.I):
            data['name'] = clean_line
            break
    
    # Email
    email_match = PATTERN_EMAIL.search(text)
    if email_match:
        data['email'] = email_match.group(0)
    
    # Phone
    phone_match = PATTERN_PHONE.search(text)
    if phone_match:
        data['phone'] = clean_text(phone_match.group(0))
    
    # Address - look for street patterns
    addr_match = re.search(r'\d+[^,\n]+(?:Street|St|Road|Rd|Avenue|Ave|City)[^,\n]*', text, re.I)
    if addr_match:
        data['address'] = clean_text(addr_match.group(0))
    
    # PIN code
    pin_match = re.search(r'\b(\d{5,6})\b', text)
    if pin_match:
        data['pincode'] = pin_match.group(1)
    
    # GST/Tax ID
    gst_match = PATTERN_GST_IN.search(text)
    if gst_match:
        data['tax_id'] = gst_match.group(0)
    
    # Extract product fields from tables if available
    if tables:
        print(f"📦 Found {len(tables)} tables in PDF, extracting product information...")
        
        for idx, table_info in enumerate(tables):
            table = table_info['data']
            if table and len(table) > 1:
                print(f"   Table {idx + 1}: {len(table)} rows, {len(table[0]) if table[0] else 0} columns")
                
                # Detect header row (optional)
                header = [clean_text(str(cell)).lower() if cell else '' for cell in table[0]]
                print(f"   Header: {header}")
                
                # Get first product row (skip header)
                for row_idx, row in enumerate(table[1:], start=2):
                    if row and len(row) >= 2:
                        # Extract product name (usually first column)
                        if row[0] and str(row[0]).strip():
                            data['product_name'] = clean_text(row[0])
                        
                        # Try to detect SKU/Code (look for alphanumeric codes)
                        for cell in row[:3]:  # Check first 3 columns
                            if cell and re.match(r'^[A-Z0-9-]{3,20}$', str(cell).strip()):
                                data['product_sku'] = clean_text(cell)
                                break
                        
                        # Extract quantity (look for numeric values)
                        for i, cell in enumerate(row[1:], start=1):
                            if cell and 'qty' in header[i] or 'quantity' in header[i]:
                                qty_value = normalize_number(cell)
                                if qty_value:
                                    data['product_quantity'] = qty_value
                                    # Try to extract unit from the same or adjacent cell
                                    unit_match = re.search(r'(pcs|kg|box|unit|ltr|mtr|set|dozen|pack)', str(cell), re.I)
                                    if unit_match:
                                        data['product_unit'] = unit_match.group(1).lower()
                                break
                        
                        # If quantity not found by header, try by position
                        if not data['product_quantity'] and len(row) > 1 and row[1]:
                            data['product_quantity'] = normalize_number(row[1])
                        
                        # Extract unit price
                        for i, cell in enumerate(row):
                            if cell and ('price' in header[i] or 'rate' in header[i]) and 'total' not in header[i]:
                                data['product_unit_price'] = normalize_number(cell)
                                break
                        
                        # If unit price not found by header, try by position
                        if not data['product_unit_price'] and len(row) > 2 and row[2]:
                            data['product_unit_price'] = normalize_number(row[2])
                        
                        # Extract discount if available
                        for i, cell in enumerate(row):
                            if cell and ('discount' in header[i] or 'disc' in header[i]):
                                data['product_discount'] = normalize_number(cell)
                                break
                        
                        # Extract tax if available
                        for i, cell in enumerate(row):
                            if cell and ('tax' in header[i] or 'gst' in header[i] or 'vat' in header[i]):
                                data['product_tax'] = normalize_number(cell)
                                break
                        
                        # Extract total (usually last column)
                        for i, cell in enumerate(row):
                            if cell and ('total' in header[i] or 'amount' in header[i]):
                                data['product_total'] = normalize_number(cell)
                                break
                        
                        # If total not found by header, try last column
                        if not data['product_total'] and len(row) > 3 and row[-1]:
                            data['product_total'] = normalize_number(row[-1])
                        
                        # Log extracted product info
                        if data['product_name']:
                            print(f"   ✅ Extracted Product (Row {row_idx}):")
                            print(f"      Name: {data['product_name']}")
                            if data['product_sku']:
                                print(f"      SKU: {data['product_sku']}")
                            if data['product_quantity']:
                                unit_str = f" {data['product_unit']}" if data['product_unit'] else ""
                                print(f"      Quantity: {data['product_quantity']}{unit_str}")
                            if data['product_unit_price']:
                                print(f"      Unit Price: {data['product_unit_price']}")
                            if data['product_discount']:
                                print(f"      Discount: {data['product_discount']}")
                            if data['product_tax']:
                                print(f"      Tax: {data['product_tax']}")
                            if data['product_total']:
                                print(f"      Total: {data['product_total']}")
                            break
                
                # If we found a product, stop looking at other tables
                if data['product_name']:
                    break
        
        # Final summary
        if data['product_name']:
            print(f"\n✅ Product extraction successful from tables!")
        else:
            print(f"\n⚠️ No product information found in tables")
    
    # Extract product info from text if not found in tables
    if not data['product_name']:
        print(f"\n📝 Attempting to extract product info from text...")
        
        # Product name - look for common patterns
        product_patterns = [
            r'(?:Product|Item|Description)[:\s]+([A-Za-z0-9][A-Za-z0-9\s\-,\.]{5,80})',
            r'(?:Particulars|Details)[:\s]+([A-Za-z0-9][A-Za-z0-9\s\-,\.]{5,80})',
        ]
        
        for pattern in product_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                data['product_name'] = clean_text(match.group(1))
                print(f"   Product Name: {data['product_name']}")
                break
        
        # SKU/Product Code
        sku_patterns = [
            r'(?:SKU|Product\s*Code|Item\s*Code|Code)[:\s]+([A-Z0-9\-]{3,20})',
            r'\b([A-Z]{2,4}\d{3,8})\b',  # Common SKU format
        ]
        
        for pattern in sku_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                data['product_sku'] = match.group(1).strip()
                print(f"   SKU: {data['product_sku']}")
                break
        
        # Quantity and Unit
        qty_patterns = [
            r'(?:Qty|Quantity)[:\s]+(\d+(?:\.\d+)?)\s*(pcs|kg|box|unit|ltr|mtr|set|dozen|pack|nos)?',
            r'(\d+(?:\.\d+)?)\s+(pcs|kg|box|unit|ltr|mtr|set|dozen|pack|nos)',
        ]
        
        for pattern in qty_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                data['product_quantity'] = normalize_number(match.group(1))
                if len(match.groups()) > 1 and match.group(2):
                    data['product_unit'] = match.group(2).lower()
                print(f"   Quantity: {data['product_quantity']} {data['product_unit'] or ''}")
                break
        
        # Unit Price/Rate
        price_patterns = [
            r'(?:Unit\s*Price|Rate|Price\s*per\s*unit)[:\s]*' + PATTERN_AMOUNT.pattern,
            r'(?:@|Rate)[:\s]*' + PATTERN_AMOUNT.pattern,
        ]
        
        for pattern in price_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                data['product_unit_price'] = normalize_number(match.group(0))
                print(f"   Unit Price: {data['product_unit_price']}")
                break
        
        # Discount
        discount_patterns = [
            r'(?:Discount|Disc)[:\s]*' + PATTERN_AMOUNT.pattern,
            r'Discount[:\s]+(\d+(?:\.\d+)?)\s*%',
        ]
        
        for pattern in discount_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                data['product_discount'] = normalize_number(match.group(0))
                print(f"   Discount: {data['product_discount']}")
                break
        
        # Tax (GST/VAT)
        tax_patterns = [
            r'(?:Tax|GST|VAT)[:\s]*' + PATTERN_AMOUNT.pattern,
            r'(?:Tax|GST|VAT)[:\s]+(\d+(?:\.\d+)?)\s*%',
        ]
        
        for pattern in tax_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                data['product_tax'] = normalize_number(match.group(0))
                print(f"   Tax: {data['product_tax']}")
                break
        
        # Product Total/Amount
        total_patterns = [
            r'(?:Item\s*Total|Line\s*Total|Amount)[:\s]*' + PATTERN_AMOUNT.pattern,
        ]
        
        for pattern in total_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                data['product_total'] = normalize_number(match.group(0))
                print(f"   Total: {data['product_total']}")
                break
        
        # Product Category/Type
        category_patterns = [
            r'(?:Category|Type)[:\s]+([A-Za-z][A-Za-z\s]{2,30})',
        ]
        
        for pattern in category_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                data['product_category'] = clean_text(match.group(1))
                print(f"   Category: {data['product_category']}")
                break
        
        # Product Description
        desc_patterns = [
            r'(?:Description|Details)[:\s]+([A-Za-z0-9][^:\n]{10,150})',
        ]
        
        for pattern in desc_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                desc_text = clean_text(match.group(1))
                # Don't use if it's too similar to product name
                if data['product_name'] and desc_text != data['product_name']:
                    data['product_description'] = desc_text
                    print(f"   Description: {data['product_description'][:50]}...")
                elif not data['product_name']:
                    data['product_description'] = desc_text
                    print(f"   Description: {data['product_description'][:50]}...")
                break
        
        if data['product_name']:
            print(f"\n✅ Product extraction successful from text!")
        else:
            print(f"\n⚠️ No product information found in text either")
    
    return data


# Extract customer data - basic patterns
def extract_customer_fields(text: str) -> Dict[str, Any]:
    data = {
        'name': None,
        'email': None,
        'phone': None,
        'address': None
    }
    
    # Look for "Bill To" or "Invoice To" sections
    patterns = [
        r'(?:Bill\s*To|Invoice\s*To)[:\s]+([A-Za-z][A-Za-z\s]{3,50})',
        r'Issued\s*to[:\s]+([A-Za-z][A-Za-z\s]{3,50})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            data['name'] = clean_text(match.group(1))
            break
    
    return data


# Extract financial data - basic patterns
def extract_financial_fields(text: str) -> Dict[str, Any]:
    data = {
        'subtotal': None,
        'discount': None,
        'shipping': None,
        'tax_rate': None,
        'tax_amount': None,
        'total': None,
        'currency': None
    }
    
    # Currency
    curr_match = PATTERN_CURRENCY.search(text)
    if curr_match:
        curr = curr_match.group(0).upper()
        curr_map = {'$': 'USD', '₹': 'INR', '€': 'EUR', '£': 'GBP'}
        data['currency'] = curr_map.get(curr, curr)
    
    # Subtotal
    subtotal_match = re.search(r'Subtotal[:\s]*' + PATTERN_AMOUNT.pattern, text, re.I)
    if subtotal_match:
        data['subtotal'] = normalize_number(subtotal_match.group(0))
    
    # Tax
    tax_match = re.search(r'(?:Tax|GST|VAT)[:\s]*' + PATTERN_AMOUNT.pattern, text, re.I)
    if tax_match:
        data['tax_amount'] = normalize_number(tax_match.group(0))
    
    # Total
    total_match = re.search(r'Total[:\s]*Amount[:\s]*' + PATTERN_AMOUNT.pattern, text, re.I)
    if not total_match:
        total_match = re.search(r'Total[:\s]*' + PATTERN_AMOUNT.pattern, text, re.I)
    if total_match:
        data['total'] = normalize_number(total_match.group(0))
    
    return data


# Extract payment info - basic patterns
def extract_payment_fields(text: str) -> Dict[str, Any]:
    data = {
        'payment_terms': None,
        'payment_method': None,
        'bank_name': None,
        'account_number': None
    }
    
    # Bank name
    bank_match = re.search(r'Bank\s*Name[:\s]*([^\n]{3,80})', text, re.I)
    if bank_match:
        data['bank_name'] = clean_text(bank_match.group(1))
    
    # Account number
    acc_match = re.search(r'Account\s*(?:No|Number)[:\s]*([^\n]{3,50})', text, re.I)
    if acc_match:
        data['account_number'] = clean_text(acc_match.group(1))
    
    return data


# Extract dates - basic patterns
def extract_dates(text: str) -> Dict[str, Any]:
    data = {
        'invoice_date': None,
        'due_date': None,
        'issue_date': None
    }
    
    # Invoice date
    date_match = re.search(r'(?:Invoice\s*)?Date[:\s]*' + PATTERN_DATE.pattern, text, re.I)
    if date_match:
        for group in date_match.groups():
            if group:
                data['invoice_date'] = clean_text(group)
                break
    
    # Due date
    due_match = re.search(r'Due\s*Date[:\s]*' + PATTERN_DATE.pattern, text, re.I)
    if due_match:
        for group in due_match.groups():
            if group:
                data['due_date'] = clean_text(group)
                break
    
    return data


async def extract_invoice_data(
    pdf_path: Path,
    extraction_type: ExtractionType,
    use_llm: bool = True
) -> InvoiceDataModel:
    """
    Extract invoice data: Basic extraction → LLM validation
    
    Args:
        pdf_path: Path to PDF file
        extraction_type: Type of data to extract
        use_llm: Whether to use LLM for validation (default: True)
    
    Returns:
        InvoiceDataModel with validated data
    """
    # Step 1: Extract text from PDF
    full_text, tables = extract_pdf_text(pdf_path)
    
    if not full_text or len(full_text) < 50:
        raise ValueError("No text content found in PDF")
    
    print(f"📄 Extracted {len(full_text)} characters from PDF")
    
    # Initialize response
    response_data = InvoiceDataModel(document_type='invoice')
    
    # Step 2: Extract and validate based on type
    if extraction_type in [ExtractionType.ALL, ExtractionType.VENDOR]:
        print("\n📋 Extracting vendor data...")
        vendor_data = extract_vendor_fields(full_text, tables)
        
        print("\n📊 Raw Vendor Extraction Results:")
        print(f"   Vendor Name: {vendor_data.get('name')}")
        print(f"   Email: {vendor_data.get('email')}")
        print(f"   Phone: {vendor_data.get('phone')}")
        print(f"   Address: {vendor_data.get('address')}")
        print(f"   Tax ID: {vendor_data.get('tax_id')}")
        
        # Validate with LLM
        if use_llm:
            print("\n Validating with LLM...")
            vendor_data = validate_and_enhance(vendor_data, full_text, "vendor")
            print(" LLM validation complete")
        
        # Clean data before creating model (handle 'null' strings, validate types)
        vendor_data = clean_extracted_data(vendor_data)
        
        response_data.vendor = VendorModel(**vendor_data)
        print("\n Vendor data extraction complete!")
    
    if extraction_type in [ExtractionType.ALL, ExtractionType.CUSTOMER]:
        print(" Extracting customer data...")
        customer_data = extract_customer_fields(full_text)
        
        # Validate with LLM
        if use_llm:
            customer_data = validate_and_enhance(customer_data, full_text, "customer")
        
        # Clean data
        customer_data = clean_extracted_data(customer_data)
        
        response_data.customer = CustomerModel(**customer_data)
    
    if extraction_type in [ExtractionType.ALL, ExtractionType.DATES]:
        print(" Extracting dates...")
        dates_data = extract_dates(full_text)
        
        # Validate with LLM
        if use_llm:
            dates_data = validate_and_enhance(dates_data, full_text, "dates")
        
        # Clean data
        dates_data = clean_extracted_data(dates_data)
        
        response_data.dates = DateModel(**dates_data)
    
    if extraction_type in [ExtractionType.ALL, ExtractionType.FINANCIAL]:
        print(" Extracting financial data...")
        financial_data = extract_financial_fields(full_text)
        
        # Validate with LLM
        if use_llm:
            financial_data = validate_and_enhance(financial_data, full_text, "financial")
        
        # Clean data (convert string 'null' to None, validate numbers)
        financial_data = clean_extracted_data(financial_data)
        
        response_data.financial = FinancialModel(**financial_data)
    
    if extraction_type in [ExtractionType.ALL, ExtractionType.PAYMENT]:
        print(" Extracting payment info...")
        payment_data = extract_payment_fields(full_text)
        
        # Validate with LLM
        if use_llm:
            payment_data = validate_and_enhance(payment_data, full_text, "payment")
        
        # Clean data
        payment_data = clean_extracted_data(payment_data)
        
        response_data.payment = PaymentModel(**payment_data)
    
    if extraction_type in [ExtractionType.ALL, ExtractionType.ITEMS]:
        print(" Extracting line items...")
        # Items extraction from tables (basic)
        items_list = []
        for table_info in tables:
            table = table_info['data']
            if table and len(table) > 1:
                # Simple table parsing
                for row in table[1:]:
                    if row and len(row) >= 2:
                        item = {
                            'item_name': clean_text(row[0]) if row[0] else None,
                            'quantity': normalize_number(row[1]) if len(row) > 1 else None,
                            'unit_price': normalize_number(row[2]) if len(row) > 2 else None,
                            'total': normalize_number(row[3]) if len(row) > 3 else None
                        }
                        if item['item_name']:
                            items_list.append(item)
        
        items_models = [ItemModel(**item) for item in items_list]
        response_data.items_data = ItemsModel(
            items=items_models,
            item_count=len(items_models)
        )
    
    return response_data
