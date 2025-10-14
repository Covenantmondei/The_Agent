from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
import dotenv
dotenv.load_dotenv()
#  "sqlite:///./test.db"
DATABASE_URL = os.environ.get("DATABASE_URL")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
