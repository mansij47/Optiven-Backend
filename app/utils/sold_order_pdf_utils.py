"""
Sold Order PDF Generation Utilities
Contains helper functions for generating sold order PDFs with comprehensive customer-facing information
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


def generate_sold_order_pdf(order_data: Dict[str, Any], output_dir: str = None) -> str:
    """
    Generate a sold order PDF from order data with comprehensive customer-facing details
    
    Args:
        order_data: Dictionary containing sold order details
        output_dir: Directory to save the PDF (if None, uses temp directory)
        
    Returns:
        str: Path to the generated PDF file
    """
    # Generate filename with order_id
    order_id = order_data.get('order_id', 'UNKNOWN')
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"SoldOrder_{order_id}_{timestamp}.pdf"
    
    # Use temporary directory if output_dir not specified
    if output_dir is None:
        # Create temporary file that will be automatically cleaned up
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf', prefix=f'SoldOrder_{order_id}_')
        output_path = temp_file.name
        temp_file.close()
    else:
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, filename)
    
    # Create PDF
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4
    
    # -------- Page Margins --------
    left = 25 * mm
    right = width - 25 * mm
    top = height - 20 * mm
    
    
    # -------- Title --------
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width / 2, top - 5, "CUSTOMER INVOICE")
    
    # -------- Header Info (Top Right Corner) --------
    y = top - 60
    c.setFont("Helvetica", 9)
    generation_date = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    c.drawRightString(right, y, f"Generated: {generation_date}")

    
    # -------- INVOICE (Top Left) --------
    y_left = top - 60
    c.setFont("Helvetica", 9)
    c.drawString(left, y, f"Invoice No: SO-{order_id}")
    
    # Store Name below Invoice Number
    y_store = y - 12
    store_name = order_data.get('store_name', '-')
    c.drawString(left, y_store, f"Store Name: {store_name}")
    
    # -------- Order Details Section (Left Column) --------
    y_left = top - 130
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left, y_left, "Order Details:")
    
    y_left -= 18
    c.setFont("Helvetica", 10)
    c.drawString(left, y_left, f"Order ID: {order_data.get('order_id', '-')}")
    
    y_left -= 15
    order_date = order_data.get('order_date', '-')
    if isinstance(order_date, datetime):
        order_date = order_date.strftime("%Y-%m-%d")
    elif isinstance(order_date, str) and 'T' in order_date:
        order_date = order_date.split('T')[0]
    c.drawString(left, y_left, f"Order Date: {order_date}")
    
    y_left -= 15
    sold_at = order_data.get('sold_at', '-')
    if isinstance(sold_at, datetime):
        sold_at = sold_at.strftime("%Y-%m-%d ")
    elif isinstance(sold_at, str) and 'T' in sold_at:
        try:
            sold_at_dt = datetime.fromisoformat(sold_at.replace('Z', '+00:00'))
            sold_at = sold_at_dt.strftime("%Y-%m-%d ")
        except:
            pass
    c.drawString(left, y_left, f"Sold At: {sold_at}")
    
    y_left -= 15
    status = order_data.get('status', '-')
    c.drawString(left, y_left, f"Status: {status}")
    
    # -------- Customer Information Section (Right Column, aligned with Order Details) --------
    mid_page = width / 2
    y_right = top - 130
    c.setFont("Helvetica-Bold", 11)
    c.drawString(mid_page, y_right, "Customer Information:")
    
    y_right -= 18
    c.setFont("Helvetica", 10)
    c.drawString(mid_page, y_right, f"Name: {order_data.get('customer_name', '-')}")
    
    y_right -= 15
    c.drawString(mid_page, y_right, f"Phone: {order_data.get('customer_phone', '-')}")
    
    y_right -= 15
    customer_email = order_data.get('customer_email', '-')
    c.drawString(mid_page, y_right, f"Email: {customer_email}")
    
    # -------- Delivery Information (part of Customer Info) --------
    y_right -= 15
    delivery_address = order_data.get('delivery_address', '-')
    if delivery_address and delivery_address != '-':
        # Clean up address (remove extra newlines/spaces)
        delivery_address = ' '.join(delivery_address.split())
        # Wrap text if too long (shorter width for right column)
        wrapped_address = textwrap.wrap(delivery_address, width=40)
        c.drawString(mid_page, y_right, f"Delivery Address: {wrapped_address[0] if wrapped_address else '-'}")
        y_right -= 12
        for line in wrapped_address[1:]:
            c.setFont("Helvetica", 9)
            c.drawString(mid_page + 20, y_right, line)
            y_right -= 12
        c.setFont("Helvetica", 10)
    else:
        c.drawString(mid_page, y_right, f"Delivery Address: -")
    
    # -------- Delivery Date --------
    y_right -= 3
    delivery_date = order_data.get('delivery_date', '-')
    if isinstance(delivery_date, datetime):
        delivery_date = delivery_date.strftime("%Y-%m-%d")
    elif isinstance(delivery_date, str) and 'T' in delivery_date:
        delivery_date = delivery_date.split('T')[0]
    c.drawString(mid_page, y_right, f"Delivery Date: {delivery_date}")
    
    # -------- GST Number --------
    y_right -= 15
    gst_number = order_data.get('gst_number', '-')
    if not gst_number or gst_number.strip() == '':
        gst_number = '-'
    c.drawString(mid_page, y_right, f"GST Number: {gst_number}")
    
    # Calculate the lowest Y position from both columns
    y = min(y_left, y_right)
    
    # -------- Products Table --------
    y -= 30
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left, y, "Products:")
    
    table_y = y - 20
    c.setFont("Helvetica-Bold", 9)
    
    # Define column positions for better alignment
    col_product = left
    col_qty = left + 120
    col_unit = left + 200
    col_price = left + 290
    col_tax = left + 370
    col_total = right - 40
    
    # Draw headers
    c.drawString(col_product, table_y, "Product Name")
    c.drawString(col_qty, table_y, "Quantity")
    c.drawString(col_unit, table_y, "Unit")
    c.drawString(col_price, table_y, "Unit Price")
    c.drawString(col_tax, table_y, "Tax %")
    c.drawRightString(col_total + 40, table_y, "Total (Rs.)")
    
    c.setLineWidth(1)
    c.line(left, table_y - 5, right, table_y - 5)
    
    # -------- Product Rows --------
    row_y = table_y - 20
    c.setFont("Helvetica", 9)
    
    products = order_data.get("products", [])
    subtotal = 0.0
    total_tax_amount = 0.0
    
    for product in products:
        # Handle product name wrapping if too long
        product_name = product.get("product_name", "-")
        if len(product_name) > 23:
            product_name = product_name[:20] + "..."
        
        order_quantity = int(product.get("order_quantity", 0))
        unit = product.get("unit", "pcs")
        unit_price = float(product.get("unit_price", 0) or product.get("selling_price", 0))
        tax = float(product.get("tax", 0))
        
        # Calculate product total with tax
        product_subtotal = order_quantity * unit_price
        tax_amount = product_subtotal * (tax / 100)
        product_total = product_subtotal + tax_amount
        
        subtotal += product_subtotal
        total_tax_amount += tax_amount
        
        # Draw product row
        c.drawString(col_product, row_y, product_name)
        c.drawString(col_qty, row_y, str(order_quantity))
        c.drawString(col_unit, row_y, unit)
        c.drawString(col_price, row_y, f"Rs. {unit_price:.2f}")
        c.drawString(col_tax, row_y, f"{tax:.1f}%")
        c.drawRightString(col_total + 40, row_y, f"Rs. {product_total:.2f}")
        
        row_y -= 5
    
    # Draw line after products
    c.setLineWidth(0.5)
    c.line(left, row_y - 5, right, row_y - 5)
    
    # -------- Pricing Summary --------
    pricing_y = row_y - 25
    c.setFont("Helvetica", 10)
    
    # Align pricing on the right side
    label_x = right - 150
    value_x = right
    
    c.drawString(label_x, pricing_y, "Subtotal:")
    c.drawRightString(value_x, pricing_y, f"Rs. {subtotal:.2f}")
    
    pricing_y -= 15
    c.drawString(label_x, pricing_y, "Total Tax:")
    c.drawRightString(value_x, pricing_y, f"Rs. {total_tax_amount:.2f}")
    
    # -------- Grand Total --------
    pricing_y -= 5
    c.setLineWidth(0.5)
    c.line(label_x - 10, pricing_y, value_x, pricing_y)
    pricing_y -= 15
    
    c.setFont("Helvetica-Bold", 12)
    grand_total = subtotal + total_tax_amount
    c.drawString(label_x, pricing_y, "Grand Total:")
    c.drawRightString(value_x, pricing_y, f"Rs. {grand_total:.2f}")
    
    # -------- Warranty & Return Information Section --------
    warranty_y = pricing_y - 35
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left, warranty_y, "Warranty & Return Information:")
    
    warranty_y -= 18
    c.setFont("Helvetica", 10)
    
    # Display warranty information for each product
    for product in products:
        product_name = product.get("product_name", "-")
        items = product.get("items", [])
        
        if items:
            for item in items:
                # Product name with warranty details
                if item.get("has_warranty"):
                    warranty_tenure = item.get("warranty_tenure", 0)
                    warranty_unit = item.get("warranty_unit", "months")
                    c.drawString(left, warranty_y, f"{product_name}: {warranty_tenure} {warranty_unit} warranty")
                else:
                    c.drawString(left, warranty_y, f"{product_name}: No warranty")
                
                warranty_y -= 15
    
    # Consumer Return Conditions
    warranty_y -= 5
    c.setFont("Helvetica-Bold", 10)
    c.drawString(left, warranty_y, "Consumer Return Conditions:")
    
    warranty_y -= 15
    c.setFont("Helvetica", 9)
    
    # Get return conditions from products (they should all have the same conditions)
    return_conditions = []
    for product in products:
        product_conditions = product.get("consumer_return_conditions", [])
        if product_conditions:
            return_conditions = product_conditions
            break
    
    if return_conditions:
        for idx, condition in enumerate(return_conditions, 1):
            c.drawString(left + 10, warranty_y, f"{idx}. {condition}")
            warranty_y -= 12
    else:
        c.drawString(left + 10, warranty_y, "No return conditions specified")
        warranty_y -= 12

    # ================= LOGO (CENTER ABOVE FOOTER) =================
    try:
        logo_path = Path(__file__).parent.parent.parent.parent.parent / "Optiven-Frontend" / "public" / "optiven-blue.png"

        if logo_path.exists():
            img = ImageReader(str(logo_path))

            logo_width = 50 * mm
            logo_height = 18 * mm

            logo_x = (width - logo_width) / 2
            logo_y = 80 * mm   # ABOVE footer

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
    
    # -------- Footer --------
    c.setFont("Helvetica-Oblique", 10)
    footer_text = "This is a system-generated sold order invoice. Thank you for your business!"
    c.drawCentredString(width / 2, 60 * mm, footer_text)
    
    # Save PDF
    c.showPage()
    c.save()
    
    return output_path


def generate_sold_order_pdf_from_schema(order_data: Any, output_dir: str = None) -> str:
    """
    Wrapper function to handle Pydantic model or dict input
    
    Args:
        order_data: SalesOrderDetails model instance or dictionary
        output_dir: Directory to save the PDF (if None, uses temp directory)
        
    Returns:
        str: Path to the generated PDF file
    """
    # Convert Pydantic model to dict if needed
    if hasattr(order_data, 'dict'):
        order_dict = order_data.dict()
    elif hasattr(order_data, 'model_dump'):
        order_dict = order_data.model_dump()
    else:
        order_dict = order_data
    
    return generate_sold_order_pdf(order_dict, output_dir)
