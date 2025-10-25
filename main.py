from starlette.middleware.sessions import SessionMiddleware
from fastapi import FastAPI, status, HTTPException
from app.db.base import engine, db_dependency
from app.services.auth import user_dependency
from app.db.base import Base
from app.api.v1.auth import router as auth_router
from app.api.v1.calendar import router as calendar_router
from app.api.v1.email_manage import router as email_router
from app.api.v1.task import router as task_router
from app.api.v1.summary import router as summary_router
from app.services.scheduler import start_scheduler, shutdown_scheduler
# from app.services.ai_processor import preload_phi_model
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import logging
import os
import atexit

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
app.include_router(task_router)
app.include_router(summary_router)
# Create tables
Base.metadata.create_all(bind=engine)


# @app.on_event("startup")
# async def startup_event():
#     """Initialize scheduler and warm up Ollama model on startup"""
#     start_scheduler()
#     logging.info("Application started - Task scheduler running")
    
    # # Warm up Ollama model to avoid first-call delay
    # await preload_phi_model()
    # logging.info("Ollama model preloaded and ready")


# @app.on_event("shutdown")
# async def shutdown_event():
#     shutdown_scheduler()
#     logging.info("Application shutdown - Scheduler stopped")


# atexit.register(shutdown_scheduler)


@app.get("/", status_code=status.HTTP_200_OK)
async def root(user: user_dependency, db: db_dependency):
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication failed.")
    return {"user": user, "message": "Welcome to Productivity Assistant API"}


@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    return {"status": "healthy", "scheduler": "running"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app="main:app", host="0.0.0.0", port=8000, reload=True)