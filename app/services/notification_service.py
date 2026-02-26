import random
from typing import Optional
from fastapi import HTTPException
from app.models.notification_model import NotificationBase
from datetime import datetime
from app.db import db
from bson import ObjectId
from uuid import uuid4

# Accessing Notifications collection without needing db.Notifications
notifications_collection = db.Notifications


async def create_notification(
    notification: NotificationBase,
    admin: Optional[bool] = False,
    sales: Optional[bool] = False,
    procurement: Optional[bool] = False,
    super_admin: Optional[bool] = False
):
    data = notification.dict()

    now = datetime.now()
    data["date"] = now.strftime('%Y-%m-%d')
    data["time"] = now.strftime('%H:%M')
    data["status"] = 0

    selected_roles = {
        "admin": admin,
        "sales": sales,
        "procurement": procurement,
        "super_admin": super_admin
    }

    sender_store_id = notification.sender.store_id
    target_emails = notification.emails or []
    responses = []

    for role, send_flag in selected_roles.items():
        if not send_flag:
            continue

        user_query = {
            "role": role,
            "store_id": sender_store_id
        }
        if target_emails:
            user_query["email"] = {"$in": target_emails}

        users = await db.Users.find(user_query).to_list(length=None)

        for user in users:
            user_id = user.get("id")
            if not user_id:
                print(f"⚠️ User missing 'id': {user}")
                continue

            # ✅ Use UUID or timestamp ID
            notification_id = f"NOTI{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{random.randint(100, 999)}"
            # Or: notification_id = str(uuid4())

            new_data = data.copy()
            new_data["notification_id"] = notification_id
            new_data["receiver"] = {
                "role": role,
                "id": user_id,
                "store_id": user.get("store_id"),
                "email": user.get("email")
            }
            new_data["created_at"] = datetime.utcnow()

            result = await notifications_collection.insert_one(new_data)

            responses.append({
                "notification_id": notification_id,
                "receiver_id": user_id,
                "mongo_id": str(result.inserted_id)
            })

    return {
        "message": f"{len(responses)} notification(s) sent successfully",
        "notifications": responses
    }

   
# async def get_all_notifications(user: dict, status: Optional[int] = None):
#     print("User:", user)

#     query = {}

#     if status is not None:
#         query["status"] = status

#     user_id = str(user["id"])
#     email = user.get("email")
#     store_id = user.get("store_id")  # Retrieve the store_id from the user object

#     # Show notifications where receiver.id or receiver.email matches the current user
#     query["$or"] = [
#         {"receiver.id": user_id},
#         {"receiver.email": email}
#     ]
    
#     # Add store_id filtering to the query
#     if store_id:
#         query["receiver.store_id"] = store_id

#     notifications = await notifications_collection.find(query).sort([
#         ("date", -1),
#         ("time", -1)
#     ]).to_list(length=None)

#     for notif in notifications:
#         notif["_id"] = str(notif["_id"])  # Convert ObjectId to string

#     return notifications

async def get_all_notifications(user: dict, status: Optional[int] = None, show_deleted: bool = False):
    """
    Get all notifications for a user with optional filters.
    
    Args:
        user: User dict with id, email, store_id
        status: Optional status filter (0=unread, 1=read)
        show_deleted: If True, only show deleted notifications (Bin). If False, only show active.
    """
    print(f"\n========== GET NOTIFICATIONS DEBUG ==========")
    print(f" User ID: {user.get('id')}")
    print(f" User Email: {user.get('email')}")
    print(f" Store ID: {user.get('store_id')}")
    print(f"Status filter: {status}")
    print(f" Show deleted: {show_deleted}")
    
    query = {}

    if status is not None:
        query["status"] = status

    user_id = str(user["id"])
    email = user.get("email")
    store_id = user.get("store_id")

    # OR conditions for receiver
    or_conditions = [
        {"receiver.id": user_id},
        {"receiver.email": email}
    ]

    # Add store_id filtering to the query
    if store_id:
        or_conditions = [
            {"receiver.id": user_id, "receiver.store_id": store_id},
            {"receiver.email": email, "receiver.store_id": store_id}
        ]

    query["$or"] = or_conditions
    
    # Filter based on deleted status
    if show_deleted:
        # Show only soft-deleted notifications (Bin tab)
        query["deletedAt"] = {"$exists": True}
        print(f"🗑️  Query mode: BIN (only deleted notifications)")
    else:
        # Show only non-deleted notifications (default)
        query["deletedAt"] = {"$exists": False}
        print(f"📋 Query mode: ACTIVE (only non-deleted notifications)")
    
    print(f"📋 Final MongoDB query: {query}")

    # ✅ Sort by ObjectId descending (latest first)
    notifications = await notifications_collection.find(query).sort(
        [("_id", -1)]
    ).to_list(length=None)
    
    print(f"✅ Found {len(notifications)} notifications")

    # Convert ObjectId and datetime to string
    for notif in notifications:
        notif["_id"] = str(notif["_id"])
        # Convert created_at datetime to ISO string for JSON serialization
        if "created_at" in notif and notif["created_at"]:
            notif["created_at"] = notif["created_at"].isoformat()
        # Convert deletedAt datetime to ISO string for JSON serialization
        if "deletedAt" in notif and notif["deletedAt"]:
            notif["deletedAt"] = notif["deletedAt"].isoformat()
    
    print(f"========== END GET NOTIFICATIONS DEBUG ==========\n")
    return notifications



    
async def update_notification_by_id(notification_id: str, update_data, user_id: str = None, user_email: str = None):
    """
    Update notification by ID.
    If user_id/user_email is provided, verifies the notification belongs to that user (matches retrieval logic).
    """
    print(f"\n========== UPDATE NOTIFICATION DEBUG ==========")
    print(f"📥 Received notification_id: {notification_id}")
    print(f"📥 Received notification_id type: {type(notification_id)}")
    print(f"📥 Received notification_id length: {len(notification_id)}")
    print(f"📥 Received user_id: {user_id}")
    print(f"📥 Received user_email: {user_email}")
    print(f"📥 Update data: {update_data}")
    
    try:
        # Validate ObjectId format
        try:
            obj_id = ObjectId(notification_id)
            print(f"✅ Successfully converted to ObjectId: {obj_id}")
        except Exception as e:
            print(f"❌ Failed to convert to ObjectId: {e}")
            raise HTTPException(status_code=400, detail="Invalid notification ID format")
        
        # First, find the notification without user check to debug
        print(f"🔍 Searching for notification with _id: {obj_id}")
        notif_check = await notifications_collection.find_one({"_id": obj_id})
        if notif_check:
            print(f"✅ DEBUG: Notification found!")
            print(f"   Notification _id: {notif_check.get('_id')}")
            print(f"   Receiver ID in DB: {notif_check.get('receiver', {}).get('id')}")
            print(f"   User ID from token: {user_id}")
            if user_id:
                print(f"   Match: {str(notif_check.get('receiver', {}).get('id')) == str(user_id)}")
        else:
            print(f"❌ DEBUG: Notification {notification_id} not found in DB at all")
            print(f"   Checked with ObjectId: {obj_id}")
            # Let's also search by notification_id field
            notif_by_custom_id = await notifications_collection.find_one({"notification_id": notification_id})
            if notif_by_custom_id:
                print(f"🔍 Found by custom notification_id field!")
                print(f"   MongoDB _id: {notif_by_custom_id.get('_id')}")
            else:
                print(f"   Also not found by notification_id field")
        
        # Build query - include user verification if user_id/user_email provided
        # This matches the same logic as get_all_notifications (ID OR email)
        if user_id or user_email:
            or_conditions = []
            if user_id:
                or_conditions.append({"receiver.id": user_id})
                or_conditions.append({"receiver.id": str(user_id)})
            if user_email:
                or_conditions.append({"receiver.email": user_email})
            
            query = {
                "_id": obj_id,
                "$or": or_conditions
            }
            print(f"🔍 Query with user verification (ID+Email): {query}")
        else:
            query = {"_id": obj_id}
            print(f"🔍 Query without user verification: {query}")
        
        # Check if notification exists and belongs to user
        existing = await notifications_collection.find_one(query)
        if not existing:
            print(f"❌ No notification found with query: {query}")
            if user_id:
                raise HTTPException(status_code=404, detail="Notification not found or access denied")
            else:
                raise HTTPException(status_code=404, detail="Notification not found")
        
        print(f"✅ Found notification, proceeding with update")
        
        # Convert Pydantic model to dict, exclude unset fields
        update_dict = update_data.dict(exclude_unset=True) if hasattr(update_data, 'dict') else update_data
        
        if not update_dict:
            raise HTTPException(status_code=400, detail="No valid update data provided")
        
        # Update the notification
        result = await notifications_collection.update_one(
            query,
            {"$set": update_dict}
        )
        
        if result.modified_count == 0:
            # Document exists but wasn't modified (same data)
            pass
        
        # Retrieve and return updated document
        updated_doc = await notifications_collection.find_one({"_id": obj_id})
        if updated_doc:
            updated_doc["_id"] = str(updated_doc["_id"])
            if "created_at" in updated_doc and updated_doc["created_at"]:
                updated_doc["created_at"] = updated_doc["created_at"].isoformat()
        
        return updated_doc
            
    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


async def delete_notification_by_id(notification_id: str, user_id: str = None, user_email: str = None):
    """
    Soft delete notification by ID (moves to bin).
    Sets deletedAt timestamp instead of actually deleting.
    If user_id/user_email is provided, verifies the notification belongs to that user.
    """
    try:
        obj_id = ObjectId(notification_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid notification ID format")
    
    # Build query - include user verification if user_id/user_email provided
    # This matches the same logic as get_all_notifications (ID OR email)
    if user_id or user_email:
        or_conditions = []
        if user_id:
            or_conditions.append({"receiver.id": user_id})
            or_conditions.append({"receiver.id": str(user_id)})
        if user_email:
            or_conditions.append({"receiver.email": user_email})
        
        query = {
            "_id": obj_id,
            "$or": or_conditions,
            "deletedAt": {"$exists": False}  # Only soft delete if not already deleted
        }
        # Check if notification exists and belongs to user
        existing = await notifications_collection.find_one(query)
        if not existing:
            raise HTTPException(status_code=404, detail="Notification not found or access denied")
    else:
        query = {"_id": obj_id, "deletedAt": {"$exists": False}}
    
    # Soft delete: Set deletedAt timestamp
    from datetime import datetime
    result = await notifications_collection.update_one(
        query,
        {"$set": {"deletedAt": datetime.utcnow()}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found or already deleted")
    
    return {"message": "Notification moved to bin."}


async def permanently_delete_notification_by_id(notification_id: str, user_id: str = None, user_email: str = None):
    """
    Permanently delete notification by ID (cannot be recovered).
    This is used when user wants to immediately delete from bin.
    If user_id/user_email is provided, verifies the notification belongs to that user.
    """
    try:
        obj_id = ObjectId(notification_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid notification ID format")
    
    # Build query - include user verification if user_id/user_email provided
    if user_id or user_email:
        or_conditions = []
        if user_id:
            or_conditions.append({"receiver.id": user_id})
            or_conditions.append({"receiver.id": str(user_id)})
        if user_email:
            or_conditions.append({"receiver.email": user_email})
        
        query = {
            "_id": obj_id,
            "$or": or_conditions,
            "deletedAt": {"$exists": True}  # Only permanently delete if already soft-deleted
        }
        # Check if notification exists and belongs to user
        existing = await notifications_collection.find_one(query)
        if not existing:
            raise HTTPException(status_code=404, detail="Notification not found in bin or access denied")
    else:
        query = {"_id": obj_id, "deletedAt": {"$exists": True}}
    
    # Permanently delete
    result = await notifications_collection.delete_one(query)
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found in bin")
    
    return {"message": "Notification permanently deleted"}


async def cleanup_old_deleted_notifications():
    """
    Permanently delete notifications that have been soft-deleted for more than 7 days.
    This should be run periodically (e.g., daily via cron job or scheduler).
    """
    from datetime import datetime, timedelta
    
    # Calculate the cutoff date (7 days ago)
    cutoff_date = datetime.utcnow() - timedelta(days=7)
    
    # Find and delete notifications that were soft-deleted before the cutoff date
    query = {
        "deletedAt": {"$exists": True, "$lt": cutoff_date}
    }
    
    result = await notifications_collection.delete_many(query)
    
    deleted_count = result.deleted_count
    if deleted_count > 0:
        print(f"🗑️ Cleanup: Permanently deleted {deleted_count} notification(s) older than 7 days")
    
    return {
        "message": f"Cleanup completed. {deleted_count} notification(s) permanently deleted.",
        "deleted_count": deleted_count
    }
