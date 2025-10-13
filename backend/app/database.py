import os
import logging
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# 1) Determine root path reliably (two levels up from this file -> project/backend)
BASE_DIR = Path(__file__).resolve().parent.parent  # adjust if your layout differs
env_path = BASE_DIR / ".env"

# 2) Try to load .env explicitly, fall back to find_dotenv()
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    log.info(f"Loaded .env from {env_path}")
else:
    # tries to find upwards from cwd
    found = find_dotenv()
    if found:
        load_dotenv(found)
        log.info(f"Loaded .env from {found}")
    else:
        log.warning(".env not found by path or find_dotenv(); relying on process env")

# 3) Read the DATABASE_URL (with safe fallback)
DATABASE_URL = os.getenv("DATABASE_URL") or "sqlite:///./dev.db"
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
