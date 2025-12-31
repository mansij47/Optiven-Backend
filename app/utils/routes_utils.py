from fastapi import APIRouter, HTTPException, Request
from app.db import db
from app.utils.service_utils import delete_by_object_id

router = APIRouter()

# Common delete route for any collection
@router.delete("/delete/{collection_name}/{object_id}")
async def delete_document(collection_name: str, object_id: str, request: Request):
    """
    Common delete endpoint for any collection.
    
    Args:
        collection_name: Name of the collection (e.g., 'Vendors', 'SalesOrders', 'ReturnToVendor')
        object_id: ObjectId of the document to delete
    
    Usage:
        DELETE /delete/Vendors/{vendor_id}
        DELETE /delete/SalesOrders/{order_id}
        DELETE /delete/ReturnToVendor/{return_id}
    """
    user = request.state.user
    
    # Role-based access control
    collection_permissions = {
        "Admins": ["admin"],
        "Categories": ["admin", "procurement"],
        "Contracts": ["procurement", "admin"],
        "CustomerHistory": ["sales", "admin"],
        "Help": ["admin"],
        "Inventory": ["admin", "procurement", "sales"],
        "LossOrders": ["sales", "admin"],
        "LossProducts": ["procurement", "admin"],
        "NewInventory": ["admin", "procurement"],
        "Notifications": ["admin"],
        "PasswordResets": ["admin"],
        "ProductItems": ["procurement", "admin"],
        "ProfitOrders": ["sales", "admin"],
        "PurchaseOrders": ["procurement", "admin"],
        "RequestedOrders": ["procurement", "admin"],
        "ReturnOrders": ["sales", "admin"],
        "ReturnToVendor": ["procurement", "admin"],
        "SalesOrders": ["sales", "admin"],
        "Vendors": ["admin", "procurement"],
    }
    
    # Check if collection exists in permissions
    if collection_name not in collection_permissions:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid collection name: {collection_name}"
        )
    
    # Check user role permission
    allowed_roles = collection_permissions[collection_name]
    if not user or user.get("role") not in allowed_roles:
        raise HTTPException(
            status_code=403, 
            detail=f"Forbidden: {', '.join(allowed_roles)} access required."
        )
    
    # Get the collection from db
    collection = getattr(db, collection_name, None)
    if collection is None:
        raise HTTPException(
            status_code=400, 
            detail=f"Collection {collection_name} not found in database"
        )
    
    # Delete the document
    deleted_count = await delete_by_object_id(collection, object_id)
    
    if deleted_count == 0:
        raise HTTPException(
            status_code=404, 
            detail=f"{collection_name} record not found or invalid ID."
        )
    
    return {
        "message": f"{collection_name} deleted successfully", 
        "collection": collection_name,
        "id": object_id
    }