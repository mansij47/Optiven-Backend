"""
Contract PDF Generation Utilities
Contains helper functions for generating contract PDFs with comprehensive vendor and product information
"""

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from datetime import datetime
import os
import tempfile
from typing import Dict, Any
import textwrap
from pathlib import Path


def generate_contract_pdf(contract_data: Dict[str, Any], output_dir: str = None) -> str:
    """
    Generate a contract PDF from contract data with comprehensive vendor and product details
    
    Args:
        contract_data: Dictionary containing contract details
        output_dir: Directory to save the PDF (if None, uses temp directory)
        
    Returns:
        str: Path to the generated PDF file
    """
    # Generate filename with contract_id
    contract_id = contract_data.get('contract_id', 'UNKNOWN')
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"Contract_{contract_id}_{timestamp}.pdf"
    
    # Use temporary directory if output_dir not specified
    if output_dir is None:
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf', prefix=f'Contract_{contract_id}_')
        output_path = temp_file.name
        temp_file.close()
    else:
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, filename)
    
    # Create PDF
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4
    
    # Page Margins
    left = 25 * mm
    right = width - 25 * mm
    top = height - 20 * mm
    
    # Title
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width / 2, top - 5, "CONTRACT AGREEMENT")
    
    # Header Info (Top Right Corner)
    y = top - 60
    c.setFont("Helvetica", 9)
    generation_date = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    c.drawRightString(right, y, f"Generated: {generation_date}")
    
    # Contract Number (Top Left)
    c.setFont("Helvetica", 9)
    c.drawString(left, y, f"Contract No: {contract_id}")
    
    # Store Name below Contract Number
    y_store = y - 12
    store_name = contract_data.get('store_name', '-')
    c.drawString(left, y_store, f"Store: {store_name}")
    
    # Vendor Information Section (Left Column)
    y_left = top - 130
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left, y_left, "Vendor Information:")
    
    y_left -= 18
    c.setFont("Helvetica", 10)
    c.drawString(left, y_left, f"Vendor Name: {contract_data.get('vendor_name', '-')}")
    

    
    y_left -= 15
    c.drawString(left, y_left, f"Email: {contract_data.get('vendor_email', '-')}")
    
    y_left -= 15
    c.drawString(left, y_left, f"Phone: {contract_data.get('phone', '-')}")
    
    y_left -= 15
    c.drawString(left, y_left, f"GST Number: {contract_data.get('gst_number', '-')}")
    
    y_left -= 15
    c.drawString(left, y_left, f"Business Type: {contract_data.get('business_type', '-')}")
    
    y_left -= 15
    address = contract_data.get('address', '-')
    if address and address != '-':
        address = ' '.join(address.split())
        wrapped_address = textwrap.wrap(address, width=40)
        c.drawString(left, y_left, f"Address: {wrapped_address[0] if wrapped_address else '-'}")
        y_left -= 12
        for line in wrapped_address[1:]:
            c.drawString(left + 45, y_left, line)  # Indent to align with address text, not label
            y_left -= 12
    else:
        c.drawString(left, y_left, f"Address: -")
        y_left -= 12
    
    c.drawString(left, y_left, f"Pincode: {contract_data.get('pincode', '-')}")
    
    # Contract Status (Right Column)
    right_col = right - 140  # Position closer to right margin
    y_right = top - 130 
    c.setFont("Helvetica-Bold", 11)
    c.drawString(right_col, y_right, "Contract Details:")
    
    y_right -= 18
    c.setFont("Helvetica", 10)
    status = contract_data.get('status', 'pending')
    c.drawString(right_col, y_right, f"Status: {status.upper()}")
    
    y_right -= 15
    request_id = contract_data.get('request_id', '-')
    c.drawString(right_col, y_right, f"Request ID: {request_id}")
    
    y_right -= 15
    created_at = contract_data.get('created_at', '-')
    if isinstance(created_at, datetime):
        created_at = created_at.strftime("%Y-%m-%d")
    elif isinstance(created_at, str) and 'T' in created_at:
        created_at = created_at.split('T')[0]
    c.drawString(right_col, y_right, f"Created: {created_at}")
    
    # Calculate the lowest Y position from both columns
    y = min(y_left, y_right)
    
    # Product Details Section
    y -= 30
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left, y, "Product Details:")
    
    table_y = y - 20
    c.setFont("Helvetica-Bold", 9)
    
    # Define column positions
    col_product = left
    col_qty = left + 100
    col_unit = left + 180
    col_base = left + 250
    col_unitprice = left + 330
    col_total = right - 40
    
    # Draw headers
    c.drawString(col_product, table_y, "Product Name")
    c.drawString(col_qty, table_y, "Quantity")
    c.drawString(col_unit, table_y, "Unit")
    c.drawString(col_base, table_y, "Base Price")
    c.drawString(col_unitprice, table_y, "Unit Price")
    c.drawRightString(col_total + 40, table_y, "Total (Rs.)")
    
    c.setLineWidth(1)
    c.line(left, table_y - 5, right, table_y - 5)
    
    # Product Row
    row_y = table_y - 20
    c.setFont("Helvetica", 9)
    
    product_name = contract_data.get("product_name", "-")
    # Wrap long product names instead of truncating (max 20 chars per line)
    wrapped_product_name = textwrap.wrap(product_name, width=20)
    
    quantity = float(contract_data.get("quantity", 0))
    unit = contract_data.get("unit", "pcs")
    unit_price = float(contract_data.get("unit_price", 0))
    vendor_tax = float(contract_data.get("vendor_tax", 0))
    
    # Calculate prices
    base_price = unit_price
    tax_per_unit = (base_price * vendor_tax) / 100
    unit_price_with_tax = base_price + tax_per_unit
    
    subtotal = quantity * base_price
    tax_amount = (subtotal * vendor_tax) / 100
    total = subtotal + tax_amount
    
    # Draw product row - first line with all columns
    c.drawString(col_product, row_y, wrapped_product_name[0] if wrapped_product_name else "-")
    c.drawString(col_qty, row_y, f"{quantity:.0f}")
    c.drawString(col_unit, row_y, unit)
    c.drawString(col_base, row_y, f"Rs. {base_price:.2f}")
    c.drawString(col_unitprice, row_y, f"Rs. {unit_price_with_tax:.2f}")
    c.drawRightString(col_total + 40, row_y, f"Rs. {total:.2f}")
    
    # Draw additional lines for wrapped product name (if any)
    if len(wrapped_product_name) > 1:
        for line in wrapped_product_name[1:]:
            row_y -= 12
            c.drawString(col_product, row_y, line)
    
    row_y -= 5
    
    # Draw line after products
    c.setLineWidth(0.5)
    c.line(left, row_y - 5, right, row_y - 5)
    
    # Pricing Summary
    pricing_y = row_y - 25
    c.setFont("Helvetica", 10)
    
    # Align pricing on the right side
    label_x = right - 150
    value_x = right
    
    c.drawString(label_x, pricing_y, "Subtotal (Base):")
    c.drawRightString(value_x, pricing_y, f"Rs. {subtotal:.2f}")
    
    pricing_y -= 15
    c.drawString(label_x, pricing_y, f"Vendor Tax ({vendor_tax}%):")
    c.drawRightString(value_x, pricing_y, f"Rs. {tax_amount:.2f}")
    
    # Grand Total
    pricing_y -= 5
    c.setLineWidth(0.5)
    c.line(label_x - 10, pricing_y, value_x, pricing_y)
    pricing_y -= 15
    
    c.setFont("Helvetica-Bold", 12)
    c.drawString(label_x, pricing_y, "Grand Total:")
    c.drawRightString(value_x, pricing_y, f"Rs. {total:.2f}")
    
    # Additional Contract Terms
    terms_y = pricing_y - 35
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left, terms_y, "Contract Terms:")
    
    terms_y -= 18
    c.setFont("Helvetica", 10)
    
    # Delivery Date
    delivery_date = contract_data.get("date_of_delivery", "-")
    if isinstance(delivery_date, datetime):
        delivery_date = delivery_date.strftime("%Y-%m-%d")
    elif isinstance(delivery_date, str) and 'T' in delivery_date:
        delivery_date = delivery_date.split('T')[0]
    c.drawString(left, terms_y, f"Delivery Date: {delivery_date}")
    
    terms_y -= 15
    warranty_tenure = contract_data.get("warranty_tenure", 0)
    warranty_unit = contract_data.get("warranty_unit", "months")
    c.drawString(left, terms_y, f"Warranty: {warranty_tenure} {warranty_unit}")
    
    terms_y -= 15
    is_returnable = contract_data.get("is_returnable", False)
    c.drawString(left, terms_y, f"Returnable: {'Yes' if is_returnable else 'No'}")
    
    terms_y -= 15
    is_damage_returnable = contract_data.get("is_damage_returnable", False)
    c.drawString(left, terms_y, f"Damage Returnable: {'Yes' if is_damage_returnable else 'No'}")
    
    # Return Conditions
    if is_returnable:
        terms_y -= 20
        c.setFont("Helvetica-Bold", 10)
        c.drawString(left, terms_y, "Return Conditions:")
        
        terms_y -= 15
        c.setFont("Helvetica", 9)
        
        return_conditions = contract_data.get("returnable_conditions", [])
        if return_conditions:
            for idx, condition in enumerate(return_conditions, 1):
                c.drawString(left + 10, terms_y, f"{idx}. {condition}")
                terms_y -= 12
        else:
            c.drawString(left + 10, terms_y, "No specific conditions specified")
            terms_y -= 12
    
    # Logo (Center Above Footer)
    try:
        logo_path = Path(__file__).parent.parent.parent.parent.parent / "Optiven-Frontend" / "public" / "optiven-blue.png"
        
        if logo_path.exists():
            img = ImageReader(str(logo_path))
            
            logo_width = 50 * mm
            logo_height = 18 * mm
            
            logo_x = (width - logo_width) / 2
            logo_y = 80 * mm
            
            c.drawImage(
                img,
                logo_x,
                logo_y,
                width=logo_width,
                height=logo_height,
                preserveAspectRatio=True,
                mask="auto"
            )
            
            # Tagline below logo
            c.setFont("Helvetica", 9)
            c.setFillColorRGB(0.4, 0.4, 0.4)
            c.drawCentredString(width / 2, logo_y - 10, "Inventory Management System")
            c.setFillColorRGB(0, 0, 0)
    
    except Exception as e:
        print(f"Logo error: {e}")
    
    # Footer
    c.setFont("Helvetica-Oblique", 10)
    footer_text = "This is a system-generated contract agreement. Please review all terms carefully."
    c.drawCentredString(width / 2, 60 * mm, footer_text)
    
    # Save PDF
    c.showPage()
    c.save()
    
    return output_path


def generate_contract_pdf_from_schema(contract_data: Any, output_dir: str = None) -> str:
    """
    Wrapper function to handle Pydantic model or dict input
    
    Args:
        contract_data: Contract model instance or dictionary
        output_dir: Directory to save the PDF (if None, uses temp directory)
        
    Returns:
        str: Path to the generated PDF file
    """
    # Convert Pydantic model to dict if needed
    if hasattr(contract_data, 'dict'):
        contract_dict = contract_data.dict()
    elif hasattr(contract_data, 'model_dump'):
        contract_dict = contract_data.model_dump()
    else:
        contract_dict = contract_data
    
    return generate_contract_pdf(contract_dict, output_dir)
