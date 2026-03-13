import logging
import uuid
import os
from fastapi import HTTPException,Request
from fastapi.responses import FileResponse, StreamingResponse
from bson import ObjectId
from datetime import datetime
from datetime import timedelta
from app.db import db
from typing import Dict, List, Optional
from app.models.procurement_models import Contract
from app.utils.auth import verify_password, create_access_token
from app.utils.contract_pdf_utils import generate_contract_pdf_from_schema
from app.services.cloudinary_service import (
    upload_pdf_from_path,
    stream_pdf_from_url,
    is_cloudinary_configured
)
 
from app.services.vendor_service import create_vendor
from app.models.procurement_models import VendorModel
from app.utils.vendor_utils import get_or_create_vendor_id

from app.models.procurement_models import ContractUpdate  # Your Pydantic model


contracts_collection = db["Contracts"]
purchase_orders_collection = db["PurchaseOrders"]
VENDOR_COLLECTION = db["Vendors"]
stores_collection = db["Stores"]


def round_contract_prices(contract: dict) -> dict:
    """
    Round all price-related fields in a contract to 2 decimal places
    """
    price_fields = ['base_price', 'unit_price', 'vendor_tax']
    for field in price_fields:
        if field in contract and contract[field] is not None:
            try:
                contract[field] = round(float(contract[field]), 2)
            except (ValueError, TypeError):
                pass
    return contract


async def generate_contract_id(store_id: str) -> str:
    """
    Generate contract ID in format: CONT-{YEAR}-{6-digit-sequence}
    Example: CONT-2026-000001
    """
    current_year = datetime.now().year
    prefix = f"CONT-{current_year}-"
    
    # Find the last contract ID for this year and store
    last_contract = await contracts_collection.find_one(
        {
            "contract_id": {"$regex": f"^{prefix}"},
            "store_id": store_id
        },
        sort=[("contract_id", -1)]
    )
    
    if last_contract and last_contract.get("contract_id"):
        # Extract sequence number from last contract ID
        last_id = last_contract["contract_id"]
        try:
            last_sequence = int(last_id.split("-")[-1])
            next_sequence = last_sequence + 1
        except (ValueError, IndexError):
            next_sequence = 1
    else:
        next_sequence = 1
    
    contract_id = f"{prefix}{next_sequence:06d}"
    return contract_id


#Add Contract
async def add_contract(contract_data: Contract, store_id: str, request: Request):
    if not contract_data.contract_id:
        contract_data.contract_id = await generate_contract_id(store_id)
    
    # ✅ Auto-generate request_id if not provided (direct contract creation without requested order)
    auto_generated_request = False
    if not contract_data.request_id or contract_data.request_id.strip() == "" or contract_data.request_id.lower() in ["all", "undefined", "null"]:
        from app.utils.sales_utils import generate_request_id
        contract_data.request_id = await generate_request_id()
        auto_generated_request = True
        print(f" Auto-generated request_id: {contract_data.request_id} for direct contract creation")

    existing = await contracts_collection.find_one(
        {"contract_id": contract_data.contract_id, "store_id": store_id},
        {"_id": 0}
    )
    if existing:
        raise HTTPException(status_code=400, detail="Contract with this ID already exists.")

    try:
        vendor_id = None

        # ✅ Check vendor existence by vendor_name AND store_id
        if contract_data.vendor_name:
            # Get or create vendor_id based on vendor_name and store_id
            vendor_id = await get_or_create_vendor_id(contract_data.vendor_name, store_id)
            
            # Check if vendor with this name already exists in Vendors collection for this store
            existing_vendor = await VENDOR_COLLECTION.find_one(
                {"vendor_name": contract_data.vendor_name, "store_id": store_id},
                {"vendor_id": 1, "_id": 0}
            )
            
            if not existing_vendor:
                # Vendor doesn't exist, create new vendor with this vendor_id
                vendor_payload = VendorModel(
                    vendor_name=contract_data.vendor_name,
                    email=contract_data.vendor_email,
                    secondary_email=contract_data.secondary_email,
                    phone_number=contract_data.phone,
                    vendor_store_name=contract_data.vendor_store_name,
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
        
        # ✅ Add valid_upto date (15 days from created_at) in Indian format
        if "created_at" in contract_dict:
            created_date = contract_dict["created_at"]
            if isinstance(created_date, str):
                created_date = datetime.fromisoformat(created_date.replace("Z", "+00:00"))
            
            valid_date = created_date + timedelta(days=15)
            # Format as DD-MM-YYYY (Indian format)
            contract_dict["valid_upto"] = valid_date.strftime("%d-%m-%Y")

        # Debug: Log if document URL is present
        if contract_dict.get("uploaded_document_url"):
            print(f" Contract has document URL: {contract_dict['uploaded_document_url'][:50]}...")
        else:
            print(f" No document URL in contract {contract_dict.get('contract_id')}")

        await contracts_collection.insert_one(contract_dict)

        # ✅ If request_id was auto-generated, create a RequestedOrders entry
        if auto_generated_request:
            user = request.state.user
            requested_orders_collection = db["RequestedOrders"]
            
            # Format estimate_date to YYYY-MM-DD (remove time component)
            estimate_date_str = contract_dict.get("date_of_delivery", "")
            if estimate_date_str:
                try:
                    # Parse ISO string and format as YYYY-MM-DD
                    if isinstance(estimate_date_str, str):
                        date_obj = datetime.fromisoformat(estimate_date_str.replace("Z", "+00:00"))
                        estimate_date_str = date_obj.strftime("%Y-%m-%d")
                    elif isinstance(estimate_date_str, datetime):
                        estimate_date_str = estimate_date_str.strftime("%Y-%m-%d")
                except (ValueError, AttributeError):
                    # If parsing fails, keep original or use empty string
                    pass
            
            # Create a RequestedOrders entry so the contract appears in the requested orders list
            requested_order_data = {
                "request_id": contract_dict["request_id"],
                "product_name": contract_dict.get("product_name", ""),
                "quantity": contract_dict.get("quantity", 0),
                "unit": contract_dict.get("unit", "pcs"),
                "category": contract_dict.get("category", ""),
                "store_id": store_id,
                "org_id": contract_dict.get("org_id", "ORG001"),
                "estimate_date": estimate_date_str,
                "status": "pending",
                "type": "order",
                "requested_by": {
                    "user_id": user.get("user_id", ""),
                    "name": user.get("name", ""),
                    "role": user.get("role", "procurement")
                },
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            await requested_orders_collection.insert_one(requested_order_data)
            print(f"✅ Created RequestedOrders entry for request_id: {contract_dict['request_id']}")

        return {
            "message": "Contract successfully created",
            "vendor_id": vendor_id,
            "contract_id": contract_dict["contract_id"],
            "request_id": contract_dict["request_id"],
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
async def update_contract_status(contract_id: str, store_id: str, action: str, vendor_email: str = None, secondary_email: str = None):
    contract = await contracts_collection.find_one({
        "contract_id": contract_id,
        "store_id": store_id
    }, {"_id": 0})

    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found.")

    if action == "accept":
        new_status = "accepted"

        existing_po = await purchase_orders_collection.find_one({
            "contract_id": contract_id,
            "store_id": store_id
        })
        if not existing_po:
            purchase_order = {
                "order_id": f"PO{contract_id[-4:]}",
                "contract_id": contract_id,
                "vendor_id": contract.get("vendor_id"),
                "vendor_name": contract["vendor_name"],
                "vendor_email": vendor_email or contract.get("vendor_email"),
                "secondary_email": secondary_email or contract.get("secondary_email"),
                "delivery_date": contract["date_of_delivery"],
                "received_status": 0,  # 0 = Waiting, 1 = Received
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
                "valid_upto": contract.get("valid_upto"),
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
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
    # ✅ If request_id is "all" or "undefined", return all contracts for the store
    if request_id in ["all", "undefined", "null", None]:
        contracts = await contracts_collection.find(
            {"store_id": store_id},
            {"_id": 0}
        ).to_list(length=None)
    else:
        # Return contracts for specific request_id
        contracts = await contracts_collection.find(
            {"request_id": request_id, "store_id": store_id},
            {"_id": 0}
        ).to_list(length=None)

    if not contracts:
        return {
            "contracts": [],
            "message": "No contracts found for this request."
        }

    # Round price fields to 2 decimal places
    contracts = [round_contract_prices(contract) for contract in contracts]

    return {"contracts": contracts}


#Veiw Contract details
async def get_contract_by_id(contract_id: str, store_id: str):
    contract = await contracts_collection.find_one(
        {"contract_id": contract_id, "store_id": store_id},
        {"_id": 0}  # Exclude MongoDB internal _id field
    )

    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found.")

    # Round price fields to 2 decimal places
    contract = round_contract_prices(contract)

    return {"contract": contract}


async def generate_contract_pdf_service(contract_id: str, store_id: str):
    """
    Generate and return contract PDF.
    
    Flow:
    1. Check if PDF URL exists in database (cached in Cloudinary)
    2. If exists and valid, stream from Cloudinary
    3. If not or invalid, generate PDF, upload to Cloudinary, save URL in DB, then stream
    
    Args:
        contract_id: ID of the contract
        store_id: Store ID for authorization
        
    Returns:
        StreamingResponse or FileResponse: PDF file for download
    """
    # Fetch contract details from database
    contract = await contracts_collection.find_one(
        {"contract_id": contract_id, "store_id": store_id},
        {"_id": 0}
    )
    
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found.")
    
    # Check if PDF is already cached in Cloudinary
    existing_pdf_url = contract.get("pdf_url")
    if existing_pdf_url and is_cloudinary_configured():
        try:
            print(f"✅ Using cached PDF from Cloudinary for contract {contract_id}")
            return await stream_pdf_from_url(
                cloudinary_url=existing_pdf_url,
                filename=f"Contract_{contract_id}.pdf",
                inline=False
            )
        except HTTPException as e:
            # Cached URL is invalid - clear it and regenerate
            print(f"⚠️ Cached PDF URL invalid for contract {contract_id}: {e.detail}. Regenerating...")
            await contracts_collection.update_one(
                {"contract_id": contract_id, "store_id": store_id},
                {"$unset": {"pdf_url": ""}}
            )
    
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
        
        # Upload to Cloudinary if configured
        if is_cloudinary_configured():
            print(f"📤 Uploading PDF to Cloudinary for contract {contract_id}")
            upload_result = upload_pdf_from_path(
                file_path=pdf_path,
                folder="optiven_pdfs/contracts",
                public_id=f"Contract_{contract_id}"
            )
            
            if upload_result and upload_result.get("secure_url"):
                cloudinary_url = upload_result["secure_url"]
                
                # Save URL to database for future requests
                await contracts_collection.update_one(
                    {"contract_id": contract_id, "store_id": store_id},
                    {"$set": {"pdf_url": cloudinary_url}}
                )
                print(f"✅ PDF URL saved to database: {cloudinary_url}")
                
                # Return the local file directly (Cloudinary URL will be used on next request)
                # This avoids CDN propagation delay issues
                print(f"✅ Returning freshly generated PDF for contract {contract_id}")
                return FileResponse(
                    path=pdf_path,
                    media_type="application/pdf",
                    filename=f"Contract_{contract_id}.pdf",
                    headers={
                        "Content-Disposition": f"attachment; filename=Contract_{contract_id}.pdf"
                    }
                )
        
        # Fallback: Return local file if Cloudinary upload failed or not configured
        print(f"⚠️ Using local file fallback for contract {contract_id}")
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

