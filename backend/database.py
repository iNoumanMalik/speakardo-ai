import env_config  # noqa: F401 — load repository root .env before reading os.environ

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# We default to sqlite locally for ease of testing since Docker isn't available
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ai_reminder.db")

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
