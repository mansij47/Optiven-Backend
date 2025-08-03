import logging
import uuid
from fastapi import HTTPException
from app.models.procurement_models import Contract
from app.utils.auth import verify_password, create_access_token
from app.db import db
from fastapi import HTTPException
from app.db import db
from fastapi import HTTPException
from typing import Dict
from app.db import db  # Make sure this is your MongoDB client instance
from app.models.procurement_models import ContractUpdate  # Your Pydantic model
from bson import ObjectId

from datetime import datetime

contracts_collection = db["Contracts"]
purchase_orders_collection = db["PurchaseOrders"]


# Add contract 
async def add_contract(contract_data: Contract, store_id: str):

    if not contract_data.contract_id:
        contract_data.contract_id = str(uuid.uuid4())
    existing = await contracts_collection.find_one({
        "contract_id": contract_data.contract_id,
        "store_id": store_id
    }, {"_id": 0})

    if existing:
        raise HTTPException(status_code=400, detail="Contract with this ID already exists.")

    try:
        contract_dict = contract_data.model_dump()
        contract_dict["store_id"] = store_id
        await contracts_collection.insert_one(contract_dict)

        return {
            "message": "Contract successfully created"
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
                "is_product_damaged": False,
                "returnable": contract.get("is_seller_returnable", True),
                "return_conditions": contract.get("seller_return_conditions", []),
                "is_consumer_returnable": contract.get("is_consumer_returnable", True),
                "consumer_return_conditions": contract.get("consumer_return_conditions", []),
                "unit": contract.get("unit", "pcs"),
                "category": contract.get("category", "misc"),
                "sub_category": contract.get("sub_category", "misc"),

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
        raise HTTPException(status_code=404, detail="No contracts found for this request.")

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
