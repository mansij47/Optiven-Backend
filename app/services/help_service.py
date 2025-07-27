from fastapi import HTTPException
from app.db import db
from app.models.help_model import HelpRequest

help_collection = db.Help  # MongoDB collection

async def create_help_request(data: HelpRequest):
    help_dict = data.dict()
    result = await help_collection.insert_one(help_dict)
    return {"message": "Help request submitted", "id": str(result.inserted_id)}

async def get_all_help_requests():
    help_requests = []
    async for doc in help_collection.find():
        doc["_id"] = str(doc["_id"])
        help_requests.append(doc)
    return help_requests