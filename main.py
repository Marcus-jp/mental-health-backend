import os
import sys
import traceback
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.chat_router import router as chat_router
from database.database import create_tables, SessionLocal

# --------------------------
# Environment Variable Checks
# --------------------------
GROQ_KEY_PRESENT = bool(os.getenv("GROQ_API_KEY"))
DB_URL_PRESENT = bool(os.getenv("DATABASE_URL"))

print("🔑 GROQ_API_KEY present:", GROQ_KEY_PRESENT)
print("🗄️ DATABASE_URL present:", DB_URL_PRESENT)

# --------------------------
# Optional: Groq API test
# --------------------------
def test_groq_api():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return "❌ GROQ_API_KEY missing, cannot test Groq connection"
    try:
        # Simple health check (replace with actual endpoint if available)
        r = requests.get(
            "https://api.groq.com/health",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=5
        )
        if r.status_code == 200:
            return "✅ Groq API reachable"
        return f"❌ Groq API returned status {r.status_code}"
    except Exception as e:
        return f"❌ Groq API connection failed: {e}"

# --------------------------
# Optional: Database connection test
# --------------------------
def test_database():
    try:
        db = SessionLocal()
        result = db.execute("SELECT 1").fetchone()
        db.close()
        if result:
            return "✅ Database connection successful"
        return "❌ Database query failed (no result)"
    except Exception as e:
        traceback.print_exc()
        return f"❌ Database connection failed: {e}"

# --------------------------
# Initialize FastAPI app
# --------------------------
app = FastAPI(
    title="Mental Health Support API 🌿",
    description="Emotion-aware, multi-turn supportive chatbot backend",
    version="1.0.0"
)

# --------------------------
# CORS Settings
# --------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development; restrict in production
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# --------------------------
# Include Routers
# --------------------------
app.include_router(chat_router, prefix="/api")

# --------------------------
# Root Endpoint with Checks
# --------------------------
@app.get("/")
def root():
    return {
        "message": "Welcome to the Mental Health Support API 🌿",
        "checks": {
            "GROQ_API_KEY_present": GROQ_KEY_PRESENT,
            "DATABASE_URL_present": DB_URL_PRESENT,
            "Groq_API_status": test_groq_api(),
            "Database_status": test_database()
        },
        "endpoints": {
            "health": "/api/health",
            "chat": "/api/chat",
            "emotion": "/api/emotion",
            "mood": "/api/mood",
            "mood_latest": "/api/mood/latest",
            "history": "/api/chat/history",
            "resources": "/api/resources"
        }
    }

# --------------------------
# Startup Event
# --------------------------
@app.on_event("startup")
def startup_event():
    try:
        create_tables()
        print("🌿 Mental Health Support Backend is starting up...")
        print("✅ Database tables created/verified successfully.")
    except Exception as e:
        print(f"❌ Failed to create/verify tables: {e}")
        traceback.print_exc()

    # Run full startup checks for logs
    print("🔍 Startup Checks:")
    print("   • GROQ_API_KEY present:", GROQ_KEY_PRESENT)
    print("   • DATABASE_URL present:", DB_URL_PRESENT)
    print("   • Groq API test:", test_groq_api())
    print("   • Database test:", test_database())