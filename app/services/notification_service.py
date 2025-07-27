from fastapi import HTTPException
from app.models.notification_model import NotificationBase
from datetime import datetime
from app.db import db
from bson import ObjectId

# Accessing Notifications collection without needing db.Notifications
notifications_collection = db.Notifications

# async def create_notifications(notification: NotificationBase):
#     notifications = []

#     for receiver in notification.receiver:
#         doc = {
#             "sender": notification.sender.dict(),
#             "receiver": receiver.dict(),
#             "type_of_notification": notification.type_of_notification,
#             "title": notification.title,
#             "message": notification.message,
#             "status": notification.status,
#             "time": notification.time,
#             "date": notification.date
#         }
#         notifications.append(doc)

#     result = await db["Notifications"].insert_many(notifications)

#     if not result.inserted_ids:
#         raise HTTPException(status_code=500, detail="Failed to create notifications")

#     return {"message": "Notifications created successfully", "count": len(result.inserted_ids)}

async def create_notifications_service(notification: NotificationBase):
    notifications = []

    for receiver in notification.receiver:
        doc = {
            "sender": notification.sender.dict(),
            "receiver": receiver.dict(),
            "type_of_notification": notification.type_of_notification,
            "title": notification.title,
            "message": notification.message,
            "status": notification.status,
            "time": notification.time,
            "date": notification.date
        }
        notifications.append(doc)

    result = await db["Notifications"].insert_many(notifications)

    if not result.inserted_ids:
        raise HTTPException(status_code=500, detail="Failed to create notifications")

    return {
        "message": "Notifications created successfully",
        "count": len(result.inserted_ids)
    }
    
async def get_all_notifications(status: int = None):
    query = {}
    if status is not None:
        query["status"] = status

    notifications = await notifications_collection.find(query).to_list(length=None)

   # Convert ObjectId to string
    for notif in notifications:
        notif["_id"] = str(notif["_id"])

    return notifications

    
async def update_notification_by_id(notification_id: str, update_data):
    result = await notifications_collection.update_one(
        {"_id": ObjectId(notification_id)},
        {"$set": update_data.dict(exclude_unset=True)}
    )

    if result.modified_count == 0:
        raise ValueError("Notification not found or no changes applied")

    # Fetch the updated document
    updated_doc = await notifications_collection.find_one({"_id": ObjectId(notification_id)})

    if updated_doc:
        updated_doc["_id"] = str(updated_doc["_id"])  # ✅ Fix the ObjectId serialization

    return updated_doc


async def delete_notification_by_id(notification_id: str):
    result = await notifications_collection.delete_one({"_id": ObjectId(notification_id)})
    if result.deleted_count == 0:
        raise ValueError("Notification not found")
    return {"message": "Notification deleted"}