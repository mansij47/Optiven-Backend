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

# async def create_notification(
#     notification: NotificationBase,
#     admin: Optional[bool] = False,
#     sales: Optional[bool] = False,
#     procurement: Optional[bool] = False
# ):
#     data = notification.dict()

#     # ✅ Add timestamp info
#     now = datetime.now()
#     data["date"] = now.strftime('%Y-%m-%d')
#     data["time"] = now.strftime('%H:%M')
#     data["status"] = 0

#     # ✅ Define selected roles from query params
#     selected_roles = {
#         "admin": admin,
#         "sales": sales,
#         "procurement": procurement,
#     }

#     sender_store_id = notification.sender.store_id
#     target_emails = notification.emails or []
#     responses = []

#     for role, send_flag in selected_roles.items():
#         if not send_flag:
#             continue

#         # 🔍 Get all users in this role & store
#         user_query = {
#             "role": role,
#             "store_id": sender_store_id
#         }
#         if target_emails:
#             user_query["email"] = {"$in": target_emails}  # ✅ Filter by email


#         users = await db.Users.find(user_query).to_list(length=None)

#         for user in users:
#             user_id = user.get("id")
#             if not user_id:
#                 print(f"⚠️ User missing 'id': {user}")
#                 continue

#             notification_id = f"NOTI{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{random.randint(100, 999)}"

#             new_data = data.copy()
#             new_data["notification_id"] = notification_id
#             new_data["receiver"] = {
#                 "role": role,
#                 "id": user_id,
#                 "store_id": user.get("store_id"),
#                 "email": user.get("email")
#             }

#             # ✅ Insert into DB 
#             result = await notifications_collection.insert_one(new_data)

#             responses.append({
#                 "notification_id": notification_id,
#                 "receiver_id": user_id,
#                 "mongo_id": str(result.inserted_id)
#             })

#     return {
#         "message": f"{len(responses)} notification(s) sent successfully",
#         "notifications": responses
#     }
async def create_notification(
    notification: NotificationBase,
    admin: Optional[bool] = False,
    sales: Optional[bool] = False,
    procurement: Optional[bool] = False
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

   
async def get_all_notifications(user: dict, status: Optional[int] = None):
    print("User:", user)

    query = {}

    if status is not None:
        query["status"] = status

    user_id = str(user["id"])
    email = user.get("email")
    # Show notifications where receiver.id or receiver.email matches the current user
    query["$or"] = [
        {"receiver.id": user_id},
        {"receiver.email": email}
    ]

    notifications = await notifications_collection.find(query).sort([
        ("date", -1),
        ("time", -1)
    ]).to_list(length=None)

    for notif in notifications:
        notif["_id"] = str(notif["_id"])  # Convert ObjectId to string

    return notifications


    
async def update_notification_by_id(notification_id: str, update_data):
    try:
        # Handle keyword arguments case
        if hasattr(update_data, 'status'):
            update_dict = {}
            if update_data.status is not None:
                update_dict['status'] = update_data.status
            if getattr(update_data, 'message', None) is not None:
                update_dict['message'] = update_data.message
            if getattr(update_data, 'title', None) is not None:
                update_dict['title'] = update_data.title
        else:
            # Convert the update_data to dict if it's a Pydantic model, otherwise use it as is
            update_dict = update_data.dict(exclude_unset=True) if hasattr(update_data, 'dict') else update_data

        if not update_dict:
            raise HTTPException(status_code=400, detail="No valid update data provided")
            
        try:
            result = await notifications_collection.update_one(
                {"_id": ObjectId(notification_id)},
                {"$set": update_dict}
            )
        except Exception as db_error:
            raise HTTPException(status_code=500, detail=f"Database error: {str(db_error)}")

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Notification not found")
        
        # Get the updated document
        updated_doc = await notifications_collection.find_one({"_id": ObjectId(notification_id)})
        if updated_doc:
            updated_doc["_id"] = str(updated_doc["_id"])
        
        return updated_doc
            
    except HTTPException as he:
        raise he  # Re-raise HTTP exceptions as-is
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


async def delete_notification_by_id(notification_id: str):
    result = await notifications_collection.delete_one({"_id": ObjectId(notification_id)})
    if result.deleted_count == 0:
        raise ValueError("Notification not found")
    return {"message": "Notification deleted"}