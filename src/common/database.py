import os
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv

load_dotenv()


class Database:
    client = None
    db = None

    @classmethod
    async def connect(cls, service_name):
        """Connect to MongoDB"""
        mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        database_name = os.getenv("MONGO_DB", "ecommerce_saga")

        try:
            cls.client = AsyncIOMotorClient(mongo_uri)
            cls.db = cls.client[database_name]

            # Create a collection for the service if it doesn't exist
            if service_name not in await cls.db.list_collection_names():
                await cls.db.create_collection(service_name)

            # Ping the server to check connection
            await cls.db.command("ping")
            print(f"Connected to MongoDB: {mongo_uri}/{database_name}")
            return cls.db
        except ConnectionFailure:
            print("MongoDB connection failed")
            raise

    @classmethod
    async def close(cls):
        """Close MongoDB connection"""
        if cls.client:
            cls.client.close()
            print("MongoDB connection closed")
