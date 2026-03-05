from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

# Locally uses SQLite, on Render uses Supabase PostgreSQL
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./mental_health.db")

# Fix URL format (Supabase sometimes gives postgres:// but SQLAlchemy needs postgresql://)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# SQLite needs extra argument, PostgreSQL does not
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

def create_tables():
    from database.models import Conversation, MoodLog
    Base.metadata.create_all(bind=engine)