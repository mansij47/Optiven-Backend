"""
File Proxy Routes
Handles streaming of files from Cloudinary to users.
Users access files through these endpoints - they never see Cloudinary URLs.
"""

from fastapi import APIRouter, HTTPException, Request, Query
from typing import Optional
from app.db import db
from app.services.cloudinary_service import (
    stream_pdf_from_url,
    is_cloudinary_configured
)

router = APIRouter()

# Collections that may have PDF URLs
purchase_orders_collection = db["PurchaseOrders"]
contracts_collection = db["Contracts"]
sales_orders_collection = db["SalesOrders"]
sold_orders_collection = db["SoldOrders"]


@router.get("/files/{file_type}/{identifier}")
async def get_file(
    file_type: str,
    identifier: str,
    request: Request,
    inline: bool = Query(False, description="If true, display in browser; if false, download")
):
    """
    Proxy endpoint for serving files stored in Cloudinary.
    
    Users access PDFs through this endpoint, hiding the Cloudinary URL.
    
    Args:
        file_type: Type of document (purchase_order, contract, sold_order, quotation)
        identifier: Unique identifier (order_id, contract_id, etc.)
        inline: If true, display in browser; if false, force download
        
    Returns:
        StreamingResponse with the PDF content
    """
    # Get user from request state
    user = request.state.user
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=400, detail="Store ID missing in token")
    
    # Route to appropriate handler based on file type
    handlers = {
        "purchase_order": _get_purchase_order_pdf,
        "contract": _get_contract_pdf,
        "sold_order": _get_sold_order_pdf,
        "quotation": _get_quotation_pdf,
        "received_order": _get_quotation_pdf  # Alias for quotation
    }
    
    handler = handlers.get(file_type.lower())
    if not handler:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown file type: {file_type}. Valid types: {list(handlers.keys())}"
        )
    
    return await handler(identifier, store_id, inline)


async def _get_purchase_order_pdf(order_id: str, store_id: str, inline: bool):
    """Fetch and stream purchase order PDF"""
    order = await purchase_orders_collection.find_one(
        {"order_id": order_id, "store_id": store_id},
        {"_id": 0, "pdf_url": 1}
    )
    
    if not order:
        raise HTTPException(status_code=404, detail="Purchase order not found")
    
    pdf_url = order.get("pdf_url")
    if not pdf_url:
        raise HTTPException(
            status_code=404,
            detail="PDF not yet generated. Please download using the download button first."
        )
    
    return await stream_pdf_from_url(
        cloudinary_url=pdf_url,
        filename=f"PurchaseOrder_{order_id}.pdf",
        inline=inline
    )


async def _get_contract_pdf(contract_id: str, store_id: str, inline: bool):
    """Fetch and stream contract PDF"""
    contract = await contracts_collection.find_one(
        {"contract_id": contract_id, "store_id": store_id},
        {"_id": 0, "pdf_url": 1}
    )
    
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    pdf_url = contract.get("pdf_url")
    if not pdf_url:
        raise HTTPException(
            status_code=404,
            detail="PDF not yet generated. Please download using the download button first."
        )
    
    return await stream_pdf_from_url(
        cloudinary_url=pdf_url,
        filename=f"Contract_{contract_id}.pdf",
        inline=inline
    )


async def _get_sold_order_pdf(order_id: str, store_id: str, inline: bool):
    """Fetch and stream sold order PDF"""
    # Sold orders are stored in SalesOrders collection with status='sold'
    order = await sales_orders_collection.find_one(
        {"order_id": order_id, "store_id": store_id, "status": "sold"},
        {"_id": 0, "pdf_url": 1}
    )
    
    if not order:
        raise HTTPException(status_code=404, detail="Sold order not found")
    
    pdf_url = order.get("pdf_url")
    if not pdf_url:
        raise HTTPException(
            status_code=404,
            detail="PDF not yet generated. Please download using the download button first."
        )
    
    return await stream_pdf_from_url(
        cloudinary_url=pdf_url,
        filename=f"Invoice_{order_id}.pdf",
        inline=inline
    )


async def _get_quotation_pdf(order_id: str, store_id: str, inline: bool):
    """Fetch and stream quotation (received order) PDF"""
    order = await sales_orders_collection.find_one(
        {"order_id": order_id, "store_id": store_id},
        {"_id": 0, "pdf_url": 1, "status": 1}
    )
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    pdf_url = order.get("pdf_url")
    if not pdf_url:
        raise HTTPException(
            status_code=404,
            detail="PDF not yet generated. Please download using the download button first."
        )
    
    return await stream_pdf_from_url(
        cloudinary_url=pdf_url,
        filename=f"Quotation_{order_id}.pdf",
        inline=inline
    )


@router.get("/files/status")
async def check_cloudinary_status():
    """
    Check if Cloudinary storage is properly configured.
    Useful for debugging deployment issues.
    """
    return {
        "cloudinary_enabled": is_cloudinary_configured(),
        "message": "Cloudinary is " + ("enabled" if is_cloudinary_configured() else "disabled - PDFs will use local temp files")
    }
