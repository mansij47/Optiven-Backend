from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from datetime import datetime
import os
import tempfile
from typing import Dict, Any
from textwrap import wrap
from pathlib import Path


def generate_purchase_order_pdf(order_data: Dict[str, Any], output_dir: str = None) -> str:
    # Generate filename
    order_id = order_data.get("order_id", "UNKNOWN")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Use temporary directory if output_dir not specified
    if output_dir is None:
        # Create temporary file that will be automatically cleaned up
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf', prefix=f'PurchaseOrder_{order_id}_')
        output_path = temp_file.name
        temp_file.close()
    else:
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"PurchaseOrder_{order_id}_{timestamp}.pdf")

    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4

    left = 25 * mm
    right = width - 25 * mm
    top = height - 20 * mm



    # ================= TITLE =================
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width / 2, top - 5, "PURCHASE ORDER")

    # ================= HEADER =================
    y = top - 55
    c.setFont("Helvetica", 9)
    c.drawRightString(right, y, f"Generated: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    c.drawString(left, y, f"Invoice No: PO-{order_id}")
    
    # Store Name below Invoice Number
    y -= 12
    store_name = order_data.get('store_name', '-')
    c.drawString(left, y, f"Store Name: {store_name}")

    # ================= ORDER DETAILS =================
    y = top - 115
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left, y, "Order Details")

    y -= 18
    c.setFont("Helvetica", 10)

    # Left column
    c.drawString(left, y, f"Order ID: {order_id}")
    c.drawString(left, y - 15, f"Vendor: {order_data.get('vendor_name', '-')}")
    c.drawString(left, y - 30, f"Validation Status: {order_data.get('validation_status', '-')}")
    c.drawString(left, y - 45, f"Delivery Date: {order_data.get('delivery_date', '-')}")
    c.drawString(left, y - 60, f"Received Status: {order_data.get('received_status', '-')}")



    # ================= TABLE =================
    y -= 90
    c.setFont("Helvetica-Bold", 10)

    # Column positions with proper spacing to avoid overlap
    col_desc = left
    col_exp = left + 120
    col_rec = left + 200
    col_unit = left + 275
    col_price = left + 320
    col_total = right - 5

    # Table header
    c.drawString(col_desc, y, "Description")
    c.drawString(col_exp, y, "Expected")
    c.drawString(col_rec, y, "Received")
    c.drawString(col_unit, y, "Unit")
    c.drawString(col_price, y, "Unit Price")
    c.drawRightString(col_total, y, "Total (Rs.)")

    c.setLineWidth(1)
    c.line(left, y - 6, right, y - 6)

    # ================= TABLE ROW =================
    y -= 24
    c.setFont("Helvetica", 10)

    expected = order_data.get("expected_quantity") or 0
    received = order_data.get("received_quantity") or 0
    unit_price = order_data.get("unit_price") or 0
    base_price = order_data.get("base_price") or unit_price

    qty = received if received > 0 else expected
    subtotal = qty * unit_price

    desc = order_data.get("product_name", "-")
    if len(desc) > 32:
        desc = desc[:29] + "..."

    c.drawString(col_desc, y, desc)
    c.drawString(col_exp, y, str(expected))
    c.drawString(col_rec, y, str(received))
    c.drawString(col_unit, y, order_data.get("unit", "-"))
    c.drawString(col_price, y, f"Rs. {unit_price:.2f}")
    c.drawRightString(col_total, y, f"Rs. {subtotal:.2f}")

    c.setLineWidth(0.5)
    c.line(left, y - 10, right, y - 10)


    # ================= PRICING =================
    y -= 30
    label_x = right - 150
    value_x = right

    c.setFont("Helvetica", 10)
    c.drawString(label_x, y, "Base Price:")
    c.drawRightString(value_x, y, f"Rs. {base_price:.2f}")

    y -= 15
    tax = order_data.get("vendor_tax", 0) or 0
    tax_amt = subtotal * tax / 100
    c.drawString(label_x, y, f"Tax ({tax}%):")
    c.drawRightString(value_x, y, f"Rs. {tax_amt:.2f}")

    y -= 15
    total = subtotal + tax_amt
    c.setLineWidth(0.5)
    c.line(label_x - 10, y, value_x, y)

    y -= 15
    c.setFont("Helvetica-Bold", 12)
    c.drawString(label_x, y, "Grand Total:")
    c.drawRightString(value_x, y, f"Rs. {total:.2f}")

    # ================= WARRANTY =================
    y -= 40
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left, y, "Warranty & Return Information")

    y -= 18
    c.setFont("Helvetica", 10)
    tenure = order_data.get("warranty_tenure", 0)
    unit = order_data.get("warranty_unit", "months")
    c.drawString(left, y, f"Warranty: {tenure} {unit}" if tenure else "Warranty: No warranty")

    y -= 15
    c.drawString(left, y, f"Vendor Returnable: {'Yes' if order_data.get('returnable') else 'No'}")

    conditions = order_data.get("return_conditions", [])
    for cond in conditions:
        y -= 12
        for line in wrap(cond, 80):
            c.drawString(left + 15, y, f"- {line}")

    y -= 15
    c.drawString(left, y, f"Consumer Returnable: {'Yes' if order_data.get('is_consumer_returnable') else 'No'}")

    consumer_conditions = order_data.get("consumer_return_conditions", [])
    for cond in consumer_conditions:
        y -= 12
        for line in wrap(cond, 80):
            c.drawString(left + 15, y, f"- {line}")
    
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

    # ================= FOOTER =================
    c.setFont("Helvetica-Oblique", 10)
    c.drawCentredString(width / 2, 60 * mm, "This is a system-generated purchase order. No signature required.")

    c.showPage()
    c.save()
    return output_path


def generate_purchase_order_pdf_from_schema(order_response, output_dir: str = None) -> str:
    """
    Generate PDF from PurchaseOrderDetailResponse Pydantic model
    
    Args:
        order_response: PurchaseOrderDetailResponse model instance
        output_dir: Directory to save the PDF (if None, uses temp directory)
        
    Returns:
        str: Path to the generated PDF file
    """
    if hasattr(order_response, 'dict'):
        order_dict = order_response.dict()
    elif hasattr(order_response, 'model_dump'):
        order_dict = order_response.model_dump()
    else:
        order_dict = dict(order_response)
    
    return generate_purchase_order_pdf(order_dict, output_dir)