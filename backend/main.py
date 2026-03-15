from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
import models
import routers.reminders
import routers.chat

Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Reminder App MVP")

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
