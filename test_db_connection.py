import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")

print(f"Testing connection to: {DATABASE_URL}")

try:
    engine = create_engine(DATABASE_URL)
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        print("✅ Database connection successful!")
        print(f"Result: {result.fetchone()}")
except Exception as e:
    print(f"❌ Database connection failed: {e}")