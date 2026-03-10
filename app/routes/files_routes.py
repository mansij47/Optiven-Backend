"""
File Routes
Handles document download and deletion endpoints.
Returns Cloudinary URLs for direct client-side downloads.
"""

from fastapi import APIRouter, HTTPException, Request
from app.db import db
from app.services.cloudinary_service import (
    extract_public_id_from_url,
    delete_pdf_from_cloudinary
)

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


@router.delete("/files/contract-document/{contract_id}")
async def delete_contract_uploaded_document(
    contract_id: str,
    request: Request
):
    """
    Delete uploaded contract document from Cloudinary and database.
    Handles both old contracts (without documents) and new contracts (with documents).
    """
    # Get user from request state
    user = request.state.user
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    store_id = user.get("store_id")
    if not store_id:
        raise HTTPException(status_code=403, detail="Store ID required")
    
    # Check user role - only admin and procurement can delete documents
    if user.get("role") not in ["admin", "procurement"]:
        raise HTTPException(
            status_code=403, 
            detail="Only admin or procurement users can delete documents"
        )
    
    # Fetch contract document URL from database
    contract = await contracts_collection.find_one(
        {"contract_id": contract_id, "store_id": store_id},
        {"_id": 0, "uploaded_document_url": 1}
    )
    
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    document_url = contract.get("uploaded_document_url")
    
    # Handle old contracts without uploaded documents
    if not document_url:
        return {
            "success": True,
            "message": "No document to delete (old contract without uploaded document)"
        }
    
    print(f" Deleting document for contract {contract_id}: {document_url}")
    
    # Extract public_id from Cloudinary URL
    public_id = extract_public_id_from_url(document_url)
    
    if public_id:
        # Delete from Cloudinary
        delete_success = delete_pdf_from_cloudinary(public_id)
        if delete_success:
            print(f" Document deleted from Cloudinary: {public_id}")
        else:
            print(f" Failed to delete from Cloudinary (may not exist): {public_id}")
    
    # Remove URL from database regardless of Cloudinary deletion result
    update_result = await contracts_collection.update_one(
        {"contract_id": contract_id, "store_id": store_id},
        {"$unset": {"uploaded_document_url": ""}}
    )
    
    if update_result.modified_count > 0:
        print(f" Document URL removed from database for contract {contract_id}")
        return {
            "success": True,
            "message": "Document deleted successfully"
        }
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to remove document URL from database"
        )


# LEGACY ENDPOINTS - Commented out, no longer in use
# These were used for PDF streaming but now we return URLs directly for client-side downloads

# @router.get("/files/{file_type}/{identifier}")
# async def get_file(file_type: str, identifier: str, request: Request, inline: bool = False):
#     """Legacy streaming endpoint - replaced by direct URL downloads"""
#     pass
