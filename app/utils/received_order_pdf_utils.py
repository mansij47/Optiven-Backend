"""
Received Order (Quotation) PDF Generation Utilities
Contains helper functions for generating quotation PDFs for received orders
"""

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from datetime import datetime
import os
import tempfile
from typing import Dict, Any
import textwrap


def generate_received_order_pdf(order_data: Dict[str, Any], output_dir: str = None) -> str:
    """
    Generate a quotation PDF from received order data
    
    Args:
        order_data: Dictionary containing received order details
        output_dir: Directory to save the PDF (if None, uses temp directory)
        
    Returns:
        str: Path to the generated PDF file
    """
    # Generate filename with order_id
    order_id = order_data.get('order_id', 'UNKNOWN')
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"Quotation_{order_id}_{timestamp}.pdf"
    
    # Use temporary directory if output_dir not specified
    if output_dir is None:
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf', prefix=f'Quotation_{order_id}_')
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
    c.drawCentredString(width / 2, top - 5, "CUSTOMER QUOTATION")
    
    # Header Info
    y = top - 60
    c.setFont("Helvetica", 9)
    generation_date = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    c.drawRightString(right, y, f"Generated: {generation_date}")
    
    # Quotation Number
    c.setFont("Helvetica", 9)
    c.drawString(left, y, f"Quotation No: QT-{order_id}")
    
    # Store Name
    y_store = y - 12
    store_name = order_data.get('store_name', '-')
    c.drawString(left, y_store, f"Store Name: {store_name}")
    
    # Order Details Section (Left Column)
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
    delivery_date = order_data.get('delivery_date', '-')
    if isinstance(delivery_date, datetime):
        delivery_date = delivery_date.strftime("%Y-%m-%d")
    elif isinstance(delivery_date, str) and 'T' in delivery_date:
        delivery_date = delivery_date.split('T')[0]
    c.drawString(left, y_left, f"Delivery Date: {delivery_date}")
    
    y_left -= 15
    c.drawString(left, y_left, f"GST Number: {order_data.get('gst_number', '-')}")
    
    # Customer Information Section (Right Column)
    mid_page = width / 2
    y_right = top - 130
    c.setFont("Helvetica-Bold", 11)
    c.drawString(mid_page, y_right, "Customer Information:")
    
    y_right -= 18
    c.setFont("Helvetica", 10)
    c.drawString(mid_page, y_right, f"Customer ID: {order_data.get('customer_id', '-')}")
    
    y_right -= 15
    c.drawString(mid_page, y_right, f"Name: {order_data.get('customer_name', '-')}")
    
    y_right -= 15
    c.drawString(mid_page, y_right, f"Phone: {order_data.get('customer_phone', '-')}")
    
    y_right -= 15
    c.drawString(mid_page, y_right, f"Email: {order_data.get('customer_email', '-')}")
    
    # Delivery Address
    y_right -= 15
    delivery_address = order_data.get('delivery_address', '-')
    if delivery_address and delivery_address != '-':
        delivery_address = ' '.join(delivery_address.split())
        wrapped_address = textwrap.wrap(delivery_address, width=40)
        c.drawString(mid_page, y_right, f"Address: {wrapped_address[0] if wrapped_address else '-'}")
        y_right -= 12
        for line in wrapped_address[1:]:
            c.setFont("Helvetica", 9)
            c.drawString(mid_page + 15, y_right, line)
            y_right -= 12
        c.setFont("Helvetica", 10)
    else:
        c.drawString(mid_page, y_right, f"Address: -")
    
    # Product Table
    y_table = y_left - 50
    c.setFont("Helvetica-Bold", 10)
    c.drawString(left, y_table, "Product Details:")
    
    y_table -= 20
    
    # Table Headers
    col_widths = [120, 60, 80, 80]
    col_x = [left, left + col_widths[0], left + col_widths[0] + col_widths[1], 
             left + col_widths[0] + col_widths[1] + col_widths[2]]
    
    c.setFont("Helvetica-Bold", 9)
    c.drawString(col_x[0], y_table, "Product Name")
    c.drawString(col_x[1], y_table, "Quantity")
    c.drawString(col_x[2], y_table, "Unit Price (Rs.)")
    c.drawString(col_x[3], y_table, "Total (Rs.)")
    
    # Draw line under headers
    y_table -= 5
    c.line(left, y_table, right, y_table)
    y_table -= 15
    
    # Product Rows
    products = order_data.get('products', [])
    subtotal = 0
    total_tax = 0
    
    c.setFont("Helvetica", 9)
    for product in products:
        if y_table < 100:  # Page break if needed
            c.showPage()
            y_table = height - 50
            c.setFont("Helvetica", 9)
        
        product_name = product.get('product_name', '-')
        if len(product_name) > 25:
            product_name = product_name[:22] + "..."
        
        quantity = product.get('order_quantity', 0)
        unit_price = float(product.get('unit_price', 0))
        product_total = quantity * unit_price
        tax = float(product.get('tax', 0))
        tax_amount = (product_total * tax) / 100
        
        subtotal += product_total
        total_tax += tax_amount
        
        c.drawString(col_x[0], y_table, product_name)
        c.drawString(col_x[1], y_table, str(quantity))
        c.drawString(col_x[2], y_table, f"Rs.{unit_price:.2f}")
        c.drawString(col_x[3], y_table, f"Rs.{product_total:.2f}")
        
        y_table -= 15
    
    # Draw line before totals
    y_table -= 5
    c.line(left, y_table, right, y_table)
    y_table -= 20
    
    # Totals Section
    totals_x = right - 150
    c.setFont("Helvetica-Bold", 10)
    
    c.drawString(totals_x, y_table, "Subtotal:")
    c.drawRightString(right, y_table, f"Rs.{subtotal:.2f}")
    
    y_table -= 15
    c.drawString(totals_x, y_table, "Tax (Total):")
    c.drawRightString(right, y_table, f"Rs.{total_tax:.2f}")
    
    y_table -= 5
    c.line(totals_x - 10, y_table, right, y_table)
    y_table -= 15
    
    grand_total = subtotal + total_tax
    c.setFont("Helvetica-Bold", 11)
    c.drawString(totals_x, y_table, "Total Amount:")
    c.drawRightString(right, y_table, f"Rs.{grand_total:.2f}")
    
    # Footer
    y_footer = 50
    c.setFont("Helvetica-Oblique", 8)
    c.drawCentredString(width / 2, y_footer, "Thank you for your business!")
    c.drawCentredString(width / 2, y_footer - 10, "This is a computer-generated quotation.")
    
    # Save PDF
    c.save()
    
    return output_path
