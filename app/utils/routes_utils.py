from fastapi import APIRouter, HTTPException, Request
from app.services import vendor_service as svc
from app.utils.service_utils import return_to_vendor_services, sales_order_services

router = APIRouter()

# delete by objectID  for vendor (optional)
@router.delete("/{vendor_id}")
async def delete_vendor(vendor_id: str, request: Request):
    user = request.state.user
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Unauthorized")

    deleted_count = await svc.delete_vendor(vendor_id)
    if deleted_count == 0:
        raise HTTPException(status_code=404, detail="Vendor not found")
    return {"message": "Vendor deleted successfully"}

# delete api (common)
@router.delete("/return-to-vendor/{id}")
async def delete_return_to_vendor(id: str, request: Request):
    user = request.state.user

    # Role check
    if not user or user.get("role") not in ["procurement", "admin"]:
        raise HTTPException(status_code=403, detail="Forbidden: Procurement or Admin access required.")

    deleted_count = await return_to_vendor_services.delete_return_to_vendor(id)

    if deleted_count == 0:
        raise HTTPException(status_code=404, detail="ReturnToVendor record not found or invalid ID.")

    return {"message": "ReturnToVendor deleted successfully", "id": id}
 @router.delete("/sales-orders/{id}")
async def delete_sales_order(id: str, request: Request):
    user = request.state.user

    # Role check
    if not user or user.get("role") not in ["sales", "admin"]:
        raise HTTPException(status_code=403, detail="Forbidden: Sales or Admin access required.")

    deleted_count = await sales_order_services.delete_sales_order(id)

    if deleted_count == 0:
        raise HTTPException(status_code=404, detail="SalesOrder record not found or invalid ID.")

    return {"message": "SalesOrder deleted successfully", "id": id}