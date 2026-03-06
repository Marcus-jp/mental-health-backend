import os
print("🔑 GROQ_API_KEY present:", bool(os.getenv("GROQ_API_KEY")))
print("🗄️ DATABASE_URL present:", bool(os.getenv("DATABASE_URL")))
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.chat_router import router as chat_router
from database.database import create_tables

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
# Works for: Flutter Web (Chrome), Android, iOS, Postman
# --------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # Allow all origins
    allow_credentials=False,    # Must be False when allow_origins=["*"]
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# --------------------------
# Include Routers
# --------------------------
app.include_router(chat_router, prefix="/api")

# --------------------------
# Root Endpoint
# --------------------------
@app.get("/")
def root():
    return {
        "message": "Welcome to the Mental Health Support API 🌿",
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
    create_tables()
    print("🌿 Mental Health Support Backend is starting up...")
    print("✅ Database tables created/verified successfully.")