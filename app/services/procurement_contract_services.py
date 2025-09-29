import logging
import uuid
from fastapi import HTTPException,Request
from bson import ObjectId
from datetime import datetime
from app.db import db
from typing import Dict

from app.models.procurement_models import Contract
from app.utils.auth import verify_password, create_access_token
 
from app.services.vendor_service import create_vendor
from app.models.procurement_models import VendorModel

from app.models.procurement_models import ContractUpdate  # Your Pydantic model


contracts_collection = db["Contracts"]
purchase_orders_collection = db["PurchaseOrders"]
VENDOR_COLLECTION = db["Vendors"]

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

    try:
        vendor_id = None

        # ✅ Check vendor existence before creating
        if contract_data.vendor_name and contract_data.gst_number:
            existing_vendor = await VENDOR_COLLECTION.find_one(
                {"vendor_name": contract_data.vendor_name, "gst_number": contract_data.gst_number},
                {"vendor_id": 1, "_id": 0}
            )
            if existing_vendor:
                vendor_id = existing_vendor["vendor_id"]
            else:
                # Call create_vendor to insert vendor
                vendor_payload = VendorModel(
                    vendor_name=contract_data.vendor_name,
                    email=contract_data.vendor_email,   # fixed
                    phone_number=contract_data.phone,
                    vendor_store_name=None,  # or fallback
                    vendor_store_address=contract_data.address,
                    pincode=contract_data.pincode,
                    gst_number=contract_data.gst_number,
                    business_type=contract_data.business_type,
)

                vendor_id = await create_vendor(vendor_payload, request)

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

    except Exception as e:
        logging.error("Error inserting contract: %s", str(e))
        raise HTTPException(status_code=500, detail="Could not insert contract.")

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
                "unit_price": contract.get("unit_price"),
                "is_damage_returnable": contract.get("is_damage_returnable"),
                "warranty_tenure": contract.get("warranty_tenure"),
                "warranty_unit": contract.get("warranty_unit"),

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
