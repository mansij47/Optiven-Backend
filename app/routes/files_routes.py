"""
File Routes
Handles document download endpoints.
Returns Cloudinary URLs for direct client-side downloads.
"""

from fastapi import APIRouter, HTTPException, Request
from app.db import db

router = APIRouter()

# Collection for contracts
contracts_collection = db["Contracts"]


@router.get("/files/contract-document/{contract_id}")
async def get_contract_uploaded_document(
    contract_id: str,
    request: Request
):
    """
    Get contract document URL - Returns URL for frontend to download directly.
    PDF delivery is enabled in Cloudinary, so just return the stored URL.
    """
    # Get user from request state
    user = request.state.user
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=403, detail="Store ID required")
    
    # Fetch contract document URL from database
    contract = await contracts_collection.find_one(
        {"contract_id": contract_id, "store_id": store_id},
        {"_id": 0, "uploaded_document_url": 1, "vendor_name": 1, "product_name": 1}
    )
    
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    document_url = contract.get("uploaded_document_url")
    
    if not document_url:
        raise HTTPException(status_code=404, detail="No document uploaded for this contract")
    
    print(f"📄 Contract {contract_id} document URL: {document_url}")
    
    # Return URL for frontend to open directly
    return {
        "url": document_url,
        "filename": f"{contract.get('vendor_name', 'contract')}_{contract.get('product_name', 'document')}.pdf"
    }


# LEGACY ENDPOINTS - Commented out, no longer in use
# These were used for PDF streaming but now we return URLs directly for client-side downloads

# @router.get("/files/{file_type}/{identifier}")
# async def get_file(file_type: str, identifier: str, request: Request, inline: bool = False):
#     """Legacy streaming endpoint - replaced by direct URL downloads"""
#     pass
