from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from database import engine, Base
import models
import routers.reminders
import routers.chat
from services.scheduler import start_scheduler

Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start the background scheduler
    scheduler = start_scheduler()
    yield
    # Shutdown: Stop the scheduler
    scheduler.shutdown()

app = FastAPI(title="AI Reminder App", lifespan=lifespan)


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

app.include_router(routers.chat.router, prefix="/chat", tags=["chat"])
app.include_router(routers.reminders.router, prefix="/reminders", tags=["reminders"])
