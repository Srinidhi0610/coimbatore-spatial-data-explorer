import os
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=True)

DB_NAME = "coimbatore_spatial_db"
_client = None


def get_db():
    global _client
    uri = os.getenv("MONGODB_URI")
    if not uri:
        raise RuntimeError(
            "MONGODB_URI is not set. Copy .env.example to .env and paste your "
            "MongoDB Atlas connection string into it."
        )
    if _client is None:
        _client = MongoClient(uri, serverSelectionTimeoutMS=8000)
    return _client[DB_NAME]


if __name__ == "__main__":
    # Quick connection test:  python src/database.py
    database = get_db()
    database.command("ping")
    print("Connected to MongoDB Atlas. Database:", DB_NAME)
