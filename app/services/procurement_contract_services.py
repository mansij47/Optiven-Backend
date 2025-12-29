import logging
import uuid
from fastapi import HTTPException,Request
from fastapi.responses import FileResponse
from bson import ObjectId
from datetime import datetime
from app.db import db
from typing import Dict

from app.models.procurement_models import Contract
from app.utils.auth import verify_password, create_access_token
from app.utils.contract_pdf_utils import generate_contract_pdf_from_schema
 
from app.services.vendor_service import create_vendor
from app.models.procurement_models import VendorModel
from app.utils.vendor_utils import get_or_create_vendor_id

from app.models.procurement_models import ContractUpdate  # Your Pydantic model


contracts_collection = db["Contracts"]
purchase_orders_collection = db["PurchaseOrders"]
VENDOR_COLLECTION = db["Vendors"]
stores_collection = db["Stores"]

#Add Contract
async def add_contract(contract_data: Contract, store_id: str, request: Request):
    if not contract_data.contract_id:
        contract_data.contract_id = str(uuid.uuid4())

    existing = await contracts_collection.find_one(
        {"contract_id": contract_data.contract_id, "store_id": store_id},
        {"_id": 0}
    )
    if existing:
        raise HTTPException(status_code=400, detail="Contract with this ID already exists.")

    # ✅ Check for existing active contract with same vendor and product for this request
    duplicate_contract = await contracts_collection.find_one({
        "request_id": contract_data.request_id,
        "vendor_name": contract_data.vendor_name,
        "product_name": contract_data.product_name,
        "store_id": store_id,
        "status": {"$in": ["pending", "accept"]}  # Check for active contracts only
    })
    
    # ✅ If contract exists, UPDATE quantity instead of creating duplicate
    if duplicate_contract:
        existing_quantity = duplicate_contract.get("quantity", 0)
        new_quantity = existing_quantity + (contract_data.quantity or 0)
        
        # Update the existing contract with new quantity and latest details
        await contracts_collection.update_one(
            {"_id": duplicate_contract["_id"]},
            {"$set": {
                "quantity": new_quantity,
                "base_price": contract_data.base_price,
                "unit_price": contract_data.unit_price,
                "vendor_tax": contract_data.vendor_tax,
                "date_of_delivery": contract_data.date_of_delivery,
                "warranty_tenure": contract_data.warranty_tenure,
                "warranty_unit": contract_data.warranty_unit,
                "returnable": contract_data.returnable,
                "return_conditions": contract_data.return_conditions,
                "is_damage_returnable": contract_data.is_damage_returnable,
            }}
        )
        
        return {
            "message": f"Contract updated successfully. Quantity increased from {existing_quantity} to {new_quantity}.",
            "contract_id": duplicate_contract.get("contract_id"),
            "previous_quantity": existing_quantity,
            "new_quantity": new_quantity,
            "was_updated": True
        }

    try:
        vendor_id = None

        # ✅ Check vendor existence by vendor_name only
        if contract_data.vendor_name:
            # Get or create vendor_id based on vendor_name
            vendor_id = await get_or_create_vendor_id(contract_data.vendor_name)
            
            # Check if vendor with this name already exists in Vendors collection
            existing_vendor = await VENDOR_COLLECTION.find_one(
                {"vendor_name": contract_data.vendor_name},
                {"vendor_id": 1, "_id": 0}
            )
            
            if not existing_vendor:
                # Vendor doesn't exist, create new vendor with this vendor_id
                vendor_payload = VendorModel(
                    vendor_name=contract_data.vendor_name,
                    email=contract_data.vendor_email,
                    phone_number=contract_data.phone,
                    vendor_store_name=None,
                    vendor_store_address=contract_data.address,
                    pincode=contract_data.pincode,
                    gst_number=contract_data.gst_number,
                    business_type=contract_data.business_type,
                )
                await create_vendor(vendor_payload, request)

        # ✅ Insert contract with vendor_id
        contract_dict = contract_data.model_dump()
        contract_dict["store_id"] = store_id
        if vendor_id:
            contract_dict["vendor_id"] = vendor_id

        await contracts_collection.insert_one(contract_dict)

        return {
            "message": "Contract successfully created",
            "vendor_id": vendor_id,
            "contract_id": contract_dict["contract_id"],
        }

    except HTTPException:
        # Re-raise HTTPException as is
        raise
    except Exception as e:
        logging.error("Error inserting contract: %s", str(e))
        logging.error("Exception type: %s", type(e).__name__)
        import traceback
        logging.error("Traceback: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Could not insert contract: {str(e)}")

#Update contract
async def update_contract(contract_id: str, store_id: str, updated_data: dict):
    # Find the contract first
    print(store_id)
    existing_contract = await contracts_collection.find_one({
        "contract_id": contract_id,
        "store_id": store_id
    })

    if not existing_contract:
        raise HTTPException(status_code=404, detail="Contract not found.")

    # Perform the update
    await contracts_collection.update_one(
        {"contract_id": contract_id, "store_id": store_id},
        {"$set": updated_data.dict(exclude_unset=True)}
    )

    return {"message": "Contract updated successfully"}


#STATUS (Accept, Decline & Revoke)
async def update_contract_status(contract_id: str, store_id: str, action: str):
    contract = await contracts_collection.find_one({
        "contract_id": contract_id,
        "store_id": store_id
    }, {"_id": 0})

    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found.")

    if action == "accept":
        new_status = "accepted"

        existing_po = await purchase_orders_collection.find_one({"contract_id": contract_id})
        if not existing_po:
            purchase_order = {
                "order_id": f"PO{contract_id[-4:]}",
                "contract_id": contract_id,
                "vendor_id": contract.get("vendor_id"),
                "vendor_name": contract["vendor_name"],
                "delivery_date": contract["date_of_delivery"],
                "validation_status": "Pending",
                "product_name": contract.get("product_name"),
                "amount": float(float(contract["quantity"]) * float(contract["unit_price"])),
                "store_id": store_id,
                "org_id": contract.get("org_id", "ORG001"),
                "received_quantity": contract.get("quantity", 0),
                "expected_quantity": contract.get("quantity", 0),
                "quantity_unit": contract.get("unit", "pcs"),
                "is_product_damaged": contract.get("is_product_damaged"),
                "returnable": contract.get("returnable"),
                "return_conditions": contract.get("return_conditions", []),
                "is_consumer_returnable": contract.get("is_consumer_returnable", True),
                "consumer_return_conditions": contract.get("consumer_return_conditions", []),
                "unit": contract.get("unit", "pcs"),
                "category": contract.get("category", "misc"),
                "sub_category": contract.get("sub_category", "misc"),
                "quantity": contract.get("quantity"),
                "base_price": contract.get("base_price", contract.get("unit_price")),
                "unit_price": contract.get("unit_price"),
                "vendor_tax": contract.get("vendor_tax", contract.get("tax", 0)),
                "is_damage_returnable": contract.get("is_damage_returnable"),
                "warranty_tenure": contract.get("warranty_tenure"),
                "warranty_unit": contract.get("warranty_unit"),
                "type": contract.get("type", "order"),

            }
            await purchase_orders_collection.insert_one(purchase_order)

    elif action == "decline":
        new_status = "declined"

    elif action == "revoke":
        new_status = "revoked"

    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    await contracts_collection.update_one(
        {"contract_id": contract_id, "store_id": store_id},
        {"$set": {"status": new_status}}
    )
    return {"message": f"Contract {action}ed successfully"}



#List of Contracts
async def get_contracts_by_request_id(request_id: str, store_id: str):
    contracts = await contracts_collection.find(
        {"request_id": request_id, "store_id": store_id},
        {"_id": 0}  # Exclude MongoDB's internal _id field
    ).to_list(length=None)

    if not contracts:
        return {
            "contracts": [],
            "message": "No contracts found for this request."
        }

    return {"contracts": contracts}


#Veiw Contract details
async def get_contract_by_id(contract_id: str, store_id: str):
    contract = await contracts_collection.find_one(
        {"contract_id": contract_id, "store_id": store_id},
        {"_id": 0}  # Exclude MongoDB internal _id field
    )

    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found.")

    return {"contract": contract}


async def generate_contract_pdf_service(contract_id: str, store_id: str):
    """
    Generate and return contract PDF
    
    Args:
        contract_id: ID of the contract
        store_id: Store ID for authorization
        
    Returns:
        FileResponse: PDF file for download
    """
    # Fetch contract details from database
    contract = await contracts_collection.find_one(
        {"contract_id": contract_id, "store_id": store_id},
        {"_id": 0}
    )
    
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found.")
    
    # Fetch store name from Stores collection
    print(f"🔍 Fetching store name for store_id: {store_id}")
    store = await stores_collection.find_one({"store_id": store_id}, {"_id": 0, "store_name": 1})
    print(f"🔍 Store found: {store}")
    if store and "store_name" in store:
        contract["store_name"] = store["store_name"]
    else:
        contract["store_name"] = "N/A"
    
    print(f"🔍 Contract data before PDF generation: store_name = {contract.get('store_name', 'NOT SET')}")
    
    # Generate PDF
    try:
        pdf_path = generate_contract_pdf_from_schema(contract)
        
        # Return PDF as file response
        return FileResponse(
            path=pdf_path,
            media_type="application/pdf",
            filename=f"Contract_{contract_id}.pdf",
            headers={
                "Content-Disposition": f"attachment; filename=Contract_{contract_id}.pdf"
            }
        )
    except Exception as e:
        logging.error(f"Error generating contract PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")

