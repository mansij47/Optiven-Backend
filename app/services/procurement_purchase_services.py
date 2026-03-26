import asyncio
import logging

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

logger = logging.getLogger(__name__)


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
            logger.info("Using cached Cloudinary PDF order_id=%s", order_id)
            return await stream_pdf_from_url(
                cloudinary_url=existing_pdf_url,
                filename=f"PurchaseOrder_{order_id}.pdf",
                inline=False
            )
        except HTTPException as e:
            # Cached URL is invalid (404 or other error) - clear it and regenerate
            logger.warning("Cached Cloudinary PDF invalid order_id=%s error=%s; regenerating", order_id, e.detail)
            await purchase_orders_collection.update_one(
                {"order_id": order_id, "store_id": store_id},
                {"$unset": {"pdf_url": ""}}
            )
    
    # Fetch store name from Stores collection
    logger.debug("Fetching store name store_id=%s", store_id)
    store = await stores_collection.find_one({"store_id": store_id}, {"_id": 0, "store_name": 1})
    logger.debug("Store lookup result store_id=%s found=%s", store_id, bool(store))
    if store and "store_name" in store:
        order["store_name"] = store["store_name"]
        logger.info("Added store_name to order order_id=%s store_name=%s", order_id, store["store_name"])
    else:
        logger.warning("Store name not found store_id=%s", store_id)
        order["store_name"] = "-"
    
    logger.debug("Order data before model order_id=%s store_name=%s", order_id, order.get("store_name", "NOT SET"))
    
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
            logger.info("Uploading purchase order PDF to Cloudinary order_id=%s", order_id)
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
                logger.info("Saved Cloudinary PDF URL to DB order_id=%s", order_id)
                
                # Return the local file directly (Cloudinary URL will be used on next request)
                # This avoids CDN propagation delay issues
                logger.info("Returning freshly generated PDF file order_id=%s", order_id)
                return FileResponse(
                    path=pdf_path,
                    media_type='application/pdf',
                    filename=f"PurchaseOrder_{order_id}.pdf",
                    headers={
                        "Content-Disposition": f"attachment; filename=PurchaseOrder_{order_id}.pdf"
                    }
                )
        
        # Fallback: Return local file if Cloudinary upload failed or not configured
        logger.warning("Using local PDF fallback order_id=%s", order_id)
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

    normalized_recipients = []
    seen_recipients = set()
    for raw_email in recipient_emails or []:
        email = str(raw_email).strip().lower()
        if not email or email in seen_recipients:
            continue
        normalized_recipients.append(email)
        seen_recipients.add(email)

    allowed_recipients = set()
    primary_email = str(order.get("vendor_email") or "").strip().lower()
    secondary_email = str(order.get("secondary_email") or "").strip().lower()
    if primary_email:
        allowed_recipients.add(primary_email)
    if secondary_email:
        allowed_recipients.add(secondary_email)

    if not allowed_recipients:
        raise HTTPException(
            status_code=400,
            detail="No valid vendor recipient email is configured on this purchase order",
        )

    invalid_recipients = [email for email in normalized_recipients if email not in allowed_recipients]
    if invalid_recipients:
        raise HTTPException(
            status_code=400,
            detail=(
                "Only purchase-order vendor emails are allowed. "
                f"Invalid recipients: {', '.join(invalid_recipients)}"
            ),
        )

    # Validate that at least one email is provided
    if not normalized_recipients:
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
        pdf_path = await asyncio.to_thread(
            generate_purchase_order_pdf_from_schema,
            order_response,
            None,
        )
        
        if not os.path.exists(pdf_path):
            logger.warning("Failed to generate PDF for PO email attachment order_id=%s", order_id)
            pdf_path = None
            
    except Exception as pdf_error:
        logger.warning("Error generating PDF for PO email attachment order_id=%s error=%s", order_id, pdf_error)
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
        email_result = await asyncio.to_thread(
            send_purchase_order_email,
            order,
            normalized_recipients,
            subject,
            custom_message,
            pdf_path,
        )

        # Clean up temporary PDF file
        if pdf_path and os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
                logger.debug("Cleaned temporary PO PDF file path=%s", pdf_path)
            except Exception as cleanup_error:
                logger.warning("Failed to clean temporary PO PDF file path=%s error=%s", pdf_path, cleanup_error)
        
        if email_result["success"]:
            success_recipients = email_result.get("successful_email_list", [])
            failed_recipients = email_result.get("failed_email_list", [])
            total_recipients = email_result.get("total_emails", len(normalized_recipients))
            successful_count = email_result.get("successful_emails", 0)
            failed_count = email_result.get("failed_emails", 0)
            delivery_status = "all_success" if failed_count == 0 else "partial_success"

            message = (
                f"Purchase order email delivered to {successful_count} out of {total_recipients} recipient(s)."
            )
            if failed_count:
                failed_addresses = ", ".join(item.get("email", "") for item in failed_recipients if item.get("email"))
                if failed_addresses:
                    message += f" Failed recipient(s): {failed_addresses}."

            warnings = []
            if not email_result.get("attachment_included"):
                if email_result.get("attachment_error"):
                    warnings.append(f"PDF attachment could not be added: {email_result.get('attachment_error')}")
                elif not pdf_path:
                    warnings.append("PDF attachment was not included because PDF generation failed.")

            return {
                "status": delivery_status,
                "message": message,
                "order_id": order_id,
                "requested_emails": normalized_recipients,
                "successful_emails": success_recipients,
                "failed_emails": failed_recipients,
                "email_results": email_result,
                "pdf_attached": bool(email_result.get("attachment_included")),
                "warnings": warnings,
                "email_sent": True,
            }
        else:
            first_error = next(
                (
                    item.get("error")
                    for item in email_result.get("details", [])
                    if item.get("status") == "failed" and item.get("error")
                ),
                "Unknown email provider error"
            )
            logger.warning(
                "PO email failed order_id=%s store_id=%s reason=%s",
                order_id,
                store_id,
                first_error,
            )
            raise HTTPException(
                status_code=502,
                detail={
                    "status": "all_failed",
                    "message": "Purchase order email delivery failed for all recipients.",
                    "reason": first_error,
                    "order_id": order_id,
                    "requested_emails": normalized_recipients,
                    "successful_emails": [],
                    "failed_emails": email_result.get("failed_email_list", []),
                    "pdf_attached": bool(email_result.get("attachment_included")),
                    "pdf_error": email_result.get("attachment_error") or (None if pdf_path else "PDF generation failed"),
                },
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
