from fastapi import HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from app.db import db
from app.models.procurement_models import PurchaseOrderResponse, PurchaseOrderDetailResponse
from app.utils.purchase_order_pdf_utils import generate_purchase_order_pdf_from_schema
from app.services.cloudinary_service import (
    upload_pdf_from_path,
    stream_pdf_from_url,
    is_cloudinary_configured
)
import os

purchase_orders_collection = db["PurchaseOrders"]
stores_collection = db["Stores"]

# Maps stored integer values to readable status
RECEIVED_MAP = {0: "Waiting", 1: "Received"}
VALIDATION_MAP = {0: "Pending", 1: "Completed"}


def round_purchase_order_prices(order: dict) -> dict:
    """
    Round all price-related fields in a purchase order to 2 decimal places
    """
    price_fields = ['amount', 'base_price', 'unit_price', 'vendor_tax']
    for field in price_fields:
        if field in order and order[field] is not None:
            try:
                order[field] = round(float(order[field]), 2)
            except (ValueError, TypeError):
                pass
    return order

async def get_all_purchase_orders(store_id: str):
    # 👇 Added sort so latest entries come first
    cursor = purchase_orders_collection.find(
        {"store_id": store_id}, {"_id": 0}
    ).sort("_id", -1)

    result = []
    async for order in cursor:
        # Handle received_status (supports both int and string)
        raw_received = order.get("received_status", 0)
        if isinstance(raw_received, int):
            order["received_status"] = RECEIVED_MAP.get(raw_received, "Waiting")
        elif isinstance(raw_received, str):
            order["received_status"] = raw_received
        else:
            order["received_status"] = "Waiting"

        # Handle validation_status (supports both int and string)
        raw_validation = order.get("validation_status", 0)
        if isinstance(raw_validation, int):
            order["validation_status"] = VALIDATION_MAP.get(raw_validation, "Pending")
        elif isinstance(raw_validation, str):
            order["validation_status"] = raw_validation
        else:
            order["validation_status"] = "Pending"

        # Round price fields to 2 decimal places
        order = round_purchase_order_prices(order)

        result.append(PurchaseOrderResponse(**order))
    return result

async def get_purchase_order_by_id(order_id: str, store_id: str):
    order = await purchase_orders_collection.find_one(
        {"order_id": order_id, "store_id": store_id}, {"_id": 0}
    )
    if not order:
        raise HTTPException(status_code=404, detail="Purchase Order not found")

    # received_status normalize
    raw_received = order.get("received_status", 0)
    if isinstance(raw_received, int):
        order["received_status"] = RECEIVED_MAP.get(raw_received, "Waiting")
    elif isinstance(raw_received, str):
        order["received_status"] = raw_received
    else:
        order["received_status"] = "Waiting"

    # validation_status normalize
    raw_validation = order.get("validation_status", 0)
    if isinstance(raw_validation, int):
        order["validation_status"] = VALIDATION_MAP.get(raw_validation, "Pending")
    elif isinstance(raw_validation, str):
        order["validation_status"] = raw_validation
    else:
        order["validation_status"] = "Pending"

    # Round price fields to 2 decimal places
    order = round_purchase_order_prices(order)

    return PurchaseOrderDetailResponse(**order)



async def mark_purchase_order_as_received(order_id: str, store_id: str) -> dict:
    existing_order = await purchase_orders_collection.find_one({
        "order_id": order_id,
        "store_id": store_id
    })
    
    if not existing_order:
        raise HTTPException(status_code=404, detail="Purchase Order not found")

    # Set numeric value for consistent mapping
    await purchase_orders_collection.update_one(
        {"order_id": order_id, "store_id": store_id},
        {"$set": {"received_status": 1}}
    )
    
    return {"message": "Purchase Order marked as received successfully"}


async def generate_purchase_order_pdf_service(order_id: str, store_id: str):
    """
    Generate PDF for a purchase order.
    
    Flow:
    1. Check if PDF URL exists in database (cached in Cloudinary)
    2. If exists and valid, stream from Cloudinary
    3. If not or invalid, generate PDF, upload to Cloudinary, save URL in DB, then stream
    
    Args:
        order_id: Purchase order ID
        store_id: Store ID for validation
        
    Returns:
        StreamingResponse or FileResponse: PDF file response
    """
    # Fetch the order details
    order = await purchase_orders_collection.find_one(
        {"order_id": order_id, "store_id": store_id}, {"_id": 0}
    )
    
    if not order:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
    
    # Check if PDF is already cached in Cloudinary
    existing_pdf_url = order.get("pdf_url")
    if existing_pdf_url and is_cloudinary_configured():
        try:
            print(f"✅ Using cached PDF from Cloudinary for order {order_id}")
            return await stream_pdf_from_url(
                cloudinary_url=existing_pdf_url,
                filename=f"PurchaseOrder_{order_id}.pdf",
                inline=False
            )
        except HTTPException as e:
            # Cached URL is invalid (404 or other error) - clear it and regenerate
            print(f"⚠️ Cached PDF URL invalid for order {order_id}: {e.detail}. Regenerating...")
            await purchase_orders_collection.update_one(
                {"order_id": order_id, "store_id": store_id},
                {"$unset": {"pdf_url": ""}}
            )
    
    # Fetch store name from Stores collection
    print(f"🔍 Fetching store name for store_id: {store_id}")
    store = await stores_collection.find_one({"store_id": store_id}, {"_id": 0, "store_name": 1})
    print(f"🔍 Store found: {store}")
    if store and "store_name" in store:
        order["store_name"] = store["store_name"]
        print(f"✅ Added store_name to order: {store['store_name']}")
    else:
        print(f"❌ Store name not found for store_id: {store_id}")
        order["store_name"] = "-"
    
    print(f"🔍 Order data before Pydantic model: store_name = {order.get('store_name', 'NOT SET')}")
    
    # Normalize status fields
    raw_received = order.get("received_status", 0)
    if isinstance(raw_received, int):
        order["received_status"] = RECEIVED_MAP.get(raw_received, "Waiting")
    elif isinstance(raw_received, str):
        order["received_status"] = raw_received
    else:
        order["received_status"] = "Waiting"

    raw_validation = order.get("validation_status", 0)
    if isinstance(raw_validation, int):
        order["validation_status"] = VALIDATION_MAP.get(raw_validation, "Pending")
    elif isinstance(raw_validation, str):
        order["validation_status"] = raw_validation
    else:
        order["validation_status"] = "Pending"
    
    # Create response model
    order_response = PurchaseOrderDetailResponse(**order)
    
    # Generate PDF
    try:
        pdf_path = generate_purchase_order_pdf_from_schema(order_response, output_dir=None)
        
        if not os.path.exists(pdf_path):
            raise HTTPException(status_code=500, detail="Failed to generate PDF")
        
        # Upload to Cloudinary if configured
        if is_cloudinary_configured():
            print(f"📤 Uploading PDF to Cloudinary for order {order_id}")
            upload_result = upload_pdf_from_path(
                file_path=pdf_path,
                folder="optiven_pdfs/purchase_orders",
                public_id=f"PurchaseOrder_{order_id}"
            )
            
            if upload_result and upload_result.get("secure_url"):
                cloudinary_url = upload_result["secure_url"]
                
                # Save URL to database for future requests
                await purchase_orders_collection.update_one(
                    {"order_id": order_id, "store_id": store_id},
                    {"$set": {"pdf_url": cloudinary_url}}
                )
                print(f"✅ PDF URL saved to database: {cloudinary_url}")
                
                # Return the local file directly (Cloudinary URL will be used on next request)
                # This avoids CDN propagation delay issues
                print(f"✅ Returning freshly generated PDF for order {order_id}")
                return FileResponse(
                    path=pdf_path,
                    media_type='application/pdf',
                    filename=f"PurchaseOrder_{order_id}.pdf",
                    headers={
                        "Content-Disposition": f"attachment; filename=PurchaseOrder_{order_id}.pdf"
                    }
                )
        
        # Fallback: Return local file if Cloudinary upload failed or not configured
        print(f"⚠️ Using local file fallback for order {order_id}")
        return FileResponse(
            path=pdf_path,
            media_type='application/pdf',
            filename=f"PurchaseOrder_{order_id}.pdf",
            headers={
                "Content-Disposition": f"attachment; filename=PurchaseOrder_{order_id}.pdf"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")


async def send_purchase_order_email_service(order_id: str, store_id: str, recipient_emails: list, subject: str = None, custom_message: str = None):
    """
    Service to send purchase order via email to vendor(s) with PDF attachment
    """
    from app.utils.email_utils import send_purchase_order_email
    
    # Get purchase order data
    order = await purchase_orders_collection.find_one(
        {"order_id": order_id, "store_id": store_id}, {"_id": 0}
    )
    
    if not order:
        raise HTTPException(status_code=404, detail="Purchase Order not found")
    
    # Validate that at least one email is provided
    if not recipient_emails or len(recipient_emails) == 0:
        raise HTTPException(status_code=400, detail="At least one recipient email is required")

    # Handle received_status (supports both int and string)
    raw_received = order.get("received_status", 0)
    if isinstance(raw_received, int):
        order["received_status"] = RECEIVED_MAP.get(raw_received, "Waiting")
    elif isinstance(raw_received, str):
        order["received_status"] = raw_received
    else:
        order["received_status"] = "Waiting"

    # Handle validation_status (supports both int and string)
    raw_validation = order.get("validation_status", 0)
    if isinstance(raw_validation, int):
        order["validation_status"] = VALIDATION_MAP.get(raw_validation, "Pending")
    elif isinstance(raw_validation, str):
        order["validation_status"] = raw_validation
    else:
        order["validation_status"] = "Pending"

    # Generate PDF for email attachment
    pdf_path = None
    try:
        # Create response model for PDF generation
        order_response = PurchaseOrderDetailResponse(**order)
        pdf_path = generate_purchase_order_pdf_from_schema(order_response, output_dir=None)
        
        if not os.path.exists(pdf_path):
            print(f"⚠️ Failed to generate PDF for email attachment")
            pdf_path = None
            
    except Exception as pdf_error:
        print(f"⚠️ Error generating PDF for email attachment: {pdf_error}")
        pdf_path = None
    
    # Format delivery date if exists
    if order.get("delivery_date"):
        try:
            from datetime import datetime
            if isinstance(order["delivery_date"], str):
                # Try to parse and format the date
                dt = datetime.fromisoformat(order["delivery_date"].replace("Z", "+00:00"))
                order["delivery_date"] = dt.strftime("%d/%m/%Y")
        except:
            # Keep original format if parsing fails
            pass
    
    # Set default subject if not provided
    if not subject:
        subject = "Purchase Order"
    
    try:
        # Send emails with PDF attachment
        email_result = send_purchase_order_email(
            order_data=order,
            recipient_emails=recipient_emails,
            subject=subject,
            custom_message=custom_message,
            pdf_path=pdf_path
        )
        
        # Clean up temporary PDF file
        if pdf_path and os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
                print(f"🗑️ Cleaned up temporary PDF file: {pdf_path}")
            except Exception as cleanup_error:
                print(f"⚠️ Failed to clean up PDF file: {cleanup_error}")
        
        if email_result["success"]:
            attachment_note = " with PDF attachment" if pdf_path else " (PDF generation failed)"
            return {
                "message": f"Purchase order sent successfully to {email_result['successful_emails']} out of {email_result['total_emails']} recipients{attachment_note}",
                "order_id": order_id,
                "email_results": email_result,
                "pdf_attached": pdf_path is not None
            }
        else:
            first_error = next(
                (
                    item.get("error")
                    for item in email_result.get("details", [])
                    if item.get("status") == "failed" and item.get("error")
                ),
                "Unknown SMTP error"
            )
            raise HTTPException(
                status_code=500,
                detail=f"Failed to send emails. All {email_result['total_emails']} attempts failed. Reason: {first_error}",
            )

    except HTTPException:
        raise
    except Exception as e:
        # Clean up PDF file in case of error
        if pdf_path and os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
            except:
                pass
        raise HTTPException(status_code=500, detail=f"Error sending purchase order email: {str(e)}")
