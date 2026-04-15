from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from database import Base, engine
from data_guards import enforce_owned_entities
from database import SessionLocal
import models
import routers.auth
import routers.chat
import routers.devices
import routers.reminders
from rate_limit import limiter
from services.scheduler import start_scheduler

load_dotenv()
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        enforce_owned_entities(db)
    finally:
        db.close()
    # Startup: Start the background scheduler
    scheduler = start_scheduler()
    yield
    # Shutdown: Stop the scheduler
    scheduler.shutdown()

app = FastAPI(title="AI Reminder App", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Welcome to AI Reminder API"}

app.include_router(routers.auth.router, prefix="/auth", tags=["auth"])
app.include_router(routers.chat.router, prefix="/chat", tags=["chat"])
app.include_router(routers.reminders.router, prefix="/reminders", tags=["reminders"])
app.include_router(routers.devices.router, tags=["devices"])
