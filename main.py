from starlette.middleware.sessions import SessionMiddleware
from fastapi import FastAPI, status, HTTPException
from app.db.base import engine, db_dependency
from app.services.auth import user_dependency
from app.db.base import Base
from app.api.v1.auth import router as auth_router
from app.api.v1.calendar import router as calendar_router
from app.api.v1.email_manage import router as email_router
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import logging
import os

# Import all models to register them with SQLAlchemy
from app.db.models import User, Task, CalendarEvent, EmailSummary, EmailActionItem

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")

origins = ["*"]

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

app = FastAPI(title="Productivity Assistant API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# Include routers
app.include_router(auth_router)
app.include_router(calendar_router)
app.include_router(email_router)

# Create tables
Base.metadata.create_all(bind=engine)


@app.get("/", status_code=status.HTTP_200_OK)
async def root(user: user_dependency, db: db_dependency):
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication failed.")
    return {"user": user, "message": "Welcome to Productivity Assistant API"}


@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app="main:app", host="0.0.0.0", port=8000, reload=True)