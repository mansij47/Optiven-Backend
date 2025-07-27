from datetime import datetime
from collections import Counter
from typing import Dict, Any
from fastapi import HTTPException
from app.db import db


# async def get_total_admins() -> int:
#     return await db.Users.count_documents({"role": "admin"})

# # Function to get total number of stores
# async def get_total_stores() -> int:
#     return await db.Stores.count_documents({})

# # Function to get status counts of stores (active, disabled, and draft)
# async def get_store_status_counts(total_stores: int) -> Dict[str, int]:
#     active_stores = await db.Stores.count_documents({"status": 1})
#     disabled_stores = await db.Stores.count_documents({"status": 2})
#     draft_stores = total_stores - active_stores - disabled_stores
#     return {
#         "active": active_stores,
#         "disabled": disabled_stores,
#         "draft": draft_stores,
#     }

# # Function to get categories and subcategories data
# async def get_categories_data() -> Dict[str, int]:
#     categories = await db.Categories.find({}, {"_id": 0, "sub_categories": 1, "category_id": 1, "category_name": 1}).to_list(None)
#     total_categories = len(categories)
#     total_subcategories = sum(len(cat.get("sub_categories", [])) for cat in categories)
#     return {
#         "total_categories": total_categories,
#         "total_subcategories": total_subcategories,
#         "categories": categories,
#     }

# # Function to get top categories and subcategories by frequency
# async def get_top_categories_and_subcategories(all_stores: list) -> Dict[str, Any]:
#     category_counter = Counter()
#     subcategory_counter = Counter()

#     for store in all_stores:
#         category_counter.update(store.get("category_ids", []))
#         subcategory_counter.update(store.get("subcategory_ids", []))

#     top_categories = [{"category_id": cat_id, "count": count} for cat_id, count in category_counter.most_common(5)]
#     top_subcategories = [{"sub_category_id": sub_id, "count": count} for sub_id, count in subcategory_counter.most_common(5)]

#     return {
#         "top_categories": top_categories,
#         "top_subcategories": top_subcategories,
#     }

# # Function to resolve category names from IDs
# def resolve_category_names(top_categories: list, categories: list) -> list:
#     category_id_to_name = {cat["category_id"]: cat["category_name"] for cat in categories}
#     for cat in top_categories:
#         cat["category_name"] = category_id_to_name.get(cat["category_id"], "Unknown")
#     return top_categories

# # Function to get store creation data for growth chart
# async def get_store_creation_data(all_stores: list) -> Dict[str, int]:
#     store_creation_map = {}

#     for store in all_stores:
#         created_at = store.get("created_at")
#         if created_at:
#             try:
#                 if isinstance(created_at, datetime):
#                     date = created_at.date()
#                 elif isinstance(created_at, str):
#                     date = datetime.fromisoformat(created_at.replace('Z', '+00:00')).date()
#                 else:
#                     continue

#                 month_key = date.strftime("%Y-%m")
#                 store_creation_map[month_key] = store_creation_map.get(month_key, 0) + 1
#             except (ValueError, AttributeError):
#                 continue

#     return store_creation_map

# # Function to get recently created stores
# async def get_recent_stores(all_stores: list) -> list:
#     recent_stores = []
#     for store in all_stores:
#         created_at = store.get("created_at")
#         if created_at:
#             try:
#                 if isinstance(created_at, datetime):
#                     store["created_at"] = created_at.isoformat()
#                     store["sort_date"] = created_at
#                 elif isinstance(created_at, str):
#                     dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
#                     store["created_at"] = created_at
#                     store["sort_date"] = dt
#                 else:
#                     continue
#                 recent_stores.append(store)
#             except (ValueError, AttributeError):
#                 continue
    
#     # Sort by date and get latest 5
#     recent_stores = sorted(recent_stores, key=lambda s: s.get("sort_date", datetime.min), reverse=True)[:5]
    
#     # Remove the temporary sort_date field
#     for store in recent_stores:
#         store.pop("sort_date", None)

#     return recent_stores

# # Main function to get the dashboard overview
# async def get_dashboard_overview(_: Dict[str, Any]) -> Dict[str, Any]:
#     try:
#         total_admins = await get_total_admins()
#         total_stores = await get_total_stores()
        
#         # Store Status Counts
#         status_ratio = await get_store_status_counts(total_stores)
        
#         # Category & Subcategory Data
#         categories_data = await get_categories_data()
#         total_categories = categories_data["total_categories"]
#         total_subcategories = categories_data["total_subcategories"]
#         categories = categories_data["categories"]

#         # Top Categories/Subcategories by Frequency
#         all_stores = await db.Stores.find({}, {"_id": 0, "category_ids": 1, "subcategory_ids": 1, "created_at": 1}).to_list(None)
#         top_data = await get_top_categories_and_subcategories(all_stores)
#         top_categories = resolve_category_names(top_data["top_categories"], categories)
#         top_subcategories = top_data["top_subcategories"]

#         # Store Growth Data
#         store_growth = await get_store_creation_data(all_stores)

#         # Recently Created Stores
#         recent_stores = await get_recent_stores(all_stores)

#         # Category vs Subcategory Ratio
#         cat_sub_ratio = {
#             "categories": total_categories,
#             "subcategories": total_subcategories,
#         }

#         return {
#             "admin_count": total_admins,
#             "store_count": total_stores,
#             "category_count": total_categories,
#             "subcategory_count": total_subcategories,
#             "status_ratio": status_ratio,
#             "cat_sub_ratio": cat_sub_ratio,
#             "store_growth": store_growth,
#             "top_categories": top_categories,
#             "top_subcategories": top_subcategories,
#             "recent_stores": recent_stores
#         }

#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Failed to generate dashboard data: {str(e)}")

async def get_total_admins() -> int:
    return await db.Users.count_documents({"role": "admin"})

# Function to get total number of stores
async def get_total_stores() -> int:
    return await db.Stores.count_documents({})

# Function to get status counts of stores (active, disabled, and draft)
async def get_store_status_counts(total_stores: int) -> Dict[str, int]:
    # Handle both numeric and string status values
    active_stores = await db.Stores.count_documents({"status": {"$in": [1, "active"]}})
    disabled_stores = await db.Stores.count_documents({"status": {"$in": [2, "disabled"]}})
    draft_stores = await db.Stores.count_documents({"status": {"$in": [0, "draft"]}})
    
    return {
        "active": active_stores,
        "disabled": disabled_stores,
        "draft": draft_stores,
    }

# Function to get categories and subcategories data
async def get_categories_data() -> Dict[str, int]:
    categories = await db.Categories.find({}, {
        "_id": 0, 
        "sub_categories": 1, 
        "category_id": 1, 
        "category_name": 1
    }).to_list(None)
    
    total_categories = len(categories)
    total_subcategories = sum(len(cat.get("sub_categories", [])) for cat in categories)
    
    return {
        "total_categories": total_categories,
        "total_subcategories": total_subcategories,
        "categories": categories,
    }

# Function to get top categories and subcategories by frequency
async def get_top_categories_and_subcategories(all_stores: list) -> Dict[str, Any]:
    category_counter = Counter()
    subcategory_counter = Counter()

    for store in all_stores:
        # Extract category IDs from CategoryModel objects in category_ids
        category_ids_list = store.get("category_ids", [])
        for category_obj in category_ids_list:
            if isinstance(category_obj, dict) and "id" in category_obj:
                category_counter[category_obj["id"]] += 1
        
        # subcategory_ids is a list of strings
        subcategory_ids = store.get("subcategory_ids", [])
        for sub_id in subcategory_ids:
            subcategory_counter[sub_id] += 1

    top_categories = [{"category_id": cat_id, "count": count} for cat_id, count in category_counter.most_common(5)]
    top_subcategories = [{"sub_category_id": sub_id, "count": count} for sub_id, count in subcategory_counter.most_common(5)]

    return {
        "top_categories": top_categories,
        "top_subcategories": top_subcategories,
    }

# Function to resolve category names from IDs
def resolve_category_names(top_categories: list, categories: list) -> list:
    category_id_to_name = {cat["category_id"]: cat["category_name"] for cat in categories}
    for cat in top_categories:
        cat["category_name"] = category_id_to_name.get(cat["category_id"], "Unknown")
    return top_categories

# Function to resolve subcategory names from IDs
def resolve_subcategory_names(top_subcategories: list, categories: list) -> list:
    # Create a mapping of subcategory_id to subcategory name
    subcategory_id_to_name = {}
    for category in categories:
        sub_categories = category.get("sub_categories", [])
        for sub_cat in sub_categories:
            if isinstance(sub_cat, dict):
                # Assuming subcategory has an id field and name field
                sub_id = sub_cat.get("id") or sub_cat.get("sub_category_id") or sub_cat.get("subcategory_id")
                sub_name = sub_cat.get("name") or sub_cat.get("sub_category_name") or sub_cat.get("subcategory_name")
                if sub_id and sub_name:
                    subcategory_id_to_name[sub_id] = sub_name
    
    # Add names to top subcategories
    for sub_cat in top_subcategories:
        sub_cat["sub_category_name"] = subcategory_id_to_name.get(sub_cat["sub_category_id"], "Unknown")
    
    return top_subcategories

# Function to get store creation data for growth chart
async def get_store_creation_data(all_stores: list) -> Dict[str, int]:
    from datetime import timezone
    
    store_creation_map = {}

    for store in all_stores:
        created_at = store.get("created_at")
        if created_at:
            try:
                if isinstance(created_at, datetime):
                    # Make timezone-naive datetime timezone-aware if needed
                    if created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=timezone.utc)
                    date = created_at.date()
                elif isinstance(created_at, str):
                    # Handle ISO format strings with proper timezone handling
                    if created_at.endswith('Z'):
                        dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    elif '+' in created_at or created_at.endswith('00:00'):
                        dt = datetime.fromisoformat(created_at)
                    else:
                        # Assume UTC if no timezone info
                        dt = datetime.fromisoformat(created_at).replace(tzinfo=timezone.utc)
                    date = dt.date()
                else:
                    continue

                month_key = date.strftime("%Y-%m")
                store_creation_map[month_key] = store_creation_map.get(month_key, 0) + 1
            except (ValueError, AttributeError) as e:
                print(f"Error parsing datetime for store growth: {e}")
                continue

    return store_creation_map

# Function to get recently created stores
async def get_recent_stores(all_stores: list) -> list:
    from datetime import timezone
    
    recent_stores = []
    for store in all_stores:
        created_at = store.get("created_at")
        if created_at:
            try:
                if isinstance(created_at, datetime):
                    # Make timezone-naive datetime timezone-aware (UTC)
                    if created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=timezone.utc)
                    store["created_at"] = created_at.isoformat()
                    store["sort_date"] = created_at
                elif isinstance(created_at, str):
                    # Parse string datetime and ensure it's timezone-aware
                    if created_at.endswith('Z'):
                        dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    elif '+' in created_at or created_at.endswith('00:00'):
                        dt = datetime.fromisoformat(created_at)
                    else:
                        # Assume UTC if no timezone info
                        dt = datetime.fromisoformat(created_at).replace(tzinfo=timezone.utc)
                    
                    store["created_at"] = created_at
                    store["sort_date"] = dt
                else:
                    continue
                recent_stores.append(store)
            except (ValueError, AttributeError) as e:
                print(f"Error parsing datetime for store {store.get('store_id', 'unknown')}: {e}")
                continue
    
    # Sort by date and get latest 5 - now all datetimes are timezone-aware
    recent_stores = sorted(recent_stores, key=lambda s: s.get("sort_date", datetime.min.replace(tzinfo=timezone.utc)), reverse=True)[:5]
    
    # Remove the temporary sort_date field and clean up the data
    for store in recent_stores:
        store.pop("sort_date", None)
        # Keep only essential fields for recent stores display
        store_data = {
            "store_id": store.get("store_id"),
            "store_name": store.get("store_name"),
            "admin_name": store.get("admin_name"),
            "status": store.get("status"),
            "created_at": store.get("created_at"),
            "category_ids": store.get("category_ids", []),
            "gst_number": store.get("gst_number")
        }
        store.clear()
        store.update(store_data)

    return recent_stores

# Main function to get the dashboard overview
async def get_dashboard_overview(_: Dict[str, Any]) -> Dict[str, Any]:
    try:
        total_admins = await get_total_admins()
        total_stores = await get_total_stores()
        
        # Store Status Counts
        status_ratio = await get_store_status_counts(total_stores)
        
        # Category & Subcategory Data
        categories_data = await get_categories_data()
        total_categories = categories_data["total_categories"]
        total_subcategories = categories_data["total_subcategories"]
        categories = categories_data["categories"]

        # Get all stores with necessary fields for analysis
        all_stores = await db.Stores.find({}, {
            "_id": 0, 
            "category_ids": 1, 
            "subcategory_ids": 1, 
            "created_at": 1,
            "store_id": 1,
            "store_name": 1,
            "admin_name": 1,
            "status": 1,
            "gst_number": 1
        }).to_list(None)
        
        # Top Categories/Subcategories by Frequency
        top_data = await get_top_categories_and_subcategories(all_stores)
        top_categories = resolve_category_names(top_data["top_categories"], categories)
        top_subcategories = resolve_subcategory_names(top_data["top_subcategories"], categories)

        # Store Growth Data
        store_growth = await get_store_creation_data(all_stores)

        # Recently Created Stores
        recent_stores = await get_recent_stores(all_stores)

        # Category vs Subcategory Ratio
        cat_sub_ratio = {
            "categories": total_categories,
            "subcategories": total_subcategories,
        }

        return {
            "admin_count": total_admins,
            "store_count": total_stores,
            "category_count": total_categories,
            "subcategory_count": total_subcategories,
            "status_ratio": status_ratio,
            "cat_sub_ratio": cat_sub_ratio,
            "store_growth": store_growth,
            "top_categories": top_categories,
            "top_subcategories": top_subcategories,
            "recent_stores": recent_stores
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate dashboard data: {str(e)}")