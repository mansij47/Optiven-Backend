from app.db import db

async def generate_vendor_id():
    """
    Generate sequential vendor ID in format VEN001, VEN002, etc.
    """
    # Find all vendors with the VEN prefix format
    all_vendors = await db.Vendors.find(
        {"vendor_id": {"$regex": "^VEN[0-9]+$"}}
    ).sort("vendor_id", -1).to_list(length=1)
    
    if all_vendors and len(all_vendors) > 0:
        latest = all_vendors[0]
        # Extract number from VEN001 format
        try:
            last_num = int(latest["vendor_id"].replace("VEN", ""))
            return f"VEN{last_num + 1:03d}"
        except ValueError:
            # If conversion fails, start from VEN001
            return "VEN001"
    else:
        return "VEN001"


async def get_or_create_vendor_id(vendor_name: str):
    """
    Check if vendor exists by vendor_name.
    If exists, return existing vendor_id.
    If not, generate and return new vendor_id.
    """
    existing_vendor = await db.Vendors.find_one(
        {"vendor_name": vendor_name},
        {"vendor_id": 1, "_id": 0}
    )
    
    if existing_vendor and "vendor_id" in existing_vendor:
        return existing_vendor["vendor_id"]
    else:
        return await generate_vendor_id()
