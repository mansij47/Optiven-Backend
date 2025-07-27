from motor.motor_asyncio import AsyncIOMotorClient
from app.config import DATABASE_NAME, MONGO_URI

client = AsyncIOMotorClient(MONGO_URI)
db = client[DATABASE_NAME]  # MentAI Cluster/Database
 