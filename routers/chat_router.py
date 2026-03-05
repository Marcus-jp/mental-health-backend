from fastapi import APIRouter, Query
from pydantic import BaseModel
from services.nlp_service import nlp_service
from services.emotion_service import emotion_service
from database.database import SessionLocal
from database.models import Conversation

router = APIRouter()

# --------------------------
# Request & Response Models
# --------------------------
class ChatRequest(BaseModel):
    message: str
    user_id: str = "user123"

class ChatResponse(BaseModel):
    response: str
    emotion: str
    confidence: float

class MoodRequest(BaseModel):
    user_id: str
    emotion: str
    level: int

# --------------------------
# Health Check
# --------------------------
@router.get("/health")
def health_check():
    return {"status": "healthy"}

# --------------------------
# Chat Endpoint
# ── nlp_service handles everything:
#    ✅ Groq AI response
#    ✅ In-memory history (for fast Groq context)
#    ✅ DB persistence (both messages)
#    ✅ Emotion detection + logging
#    So this endpoint stays minimal — no duplicate saves.
# --------------------------
@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    print(f"📩 Message from {request.user_id}: {request.message[:40]}")
    bot_reply = nlp_service.get_chat_response(
        user_message=request.message,
        user_id=request.user_id
    )
    return bot_reply

# --------------------------
# Emotion Detection Endpoint
# --------------------------
@router.post("/emotion")
def detect_emotion(request: ChatRequest):
    return nlp_service.detect_emotion(request.message)

# --------------------------
# Mood Log Endpoint (manual from mood screen)
# --------------------------
@router.post("/mood")
def log_mood(request: MoodRequest):
    record = emotion_service.log_emotion(
        user_id=request.user_id,
        emotion=request.emotion,
        level=request.level
    )
    return {"saved": True, "record": record}

# --------------------------
# Latest Mood Endpoint
# --------------------------
@router.get("/mood/latest")
def get_latest_mood(user_id: str = Query(...)):
    mood = emotion_service.get_latest_mood(user_id)
    if mood:
        return mood
    return {"message": "No mood records found", "user_id": user_id}

# --------------------------
# Mood Trend Endpoint
# --------------------------
@router.get("/mood/trend")
def get_mood_trend(user_id: str = Query(...)):
    return emotion_service.get_emotion_trend(user_id)

# --------------------------
# Chat History Endpoint
# ── Serves DB history to the history screen.
#    Also merges any in-memory messages not yet
#    in DB (e.g. current session before flush).
# --------------------------
@router.get("/chat/history")
def get_chat_history(user_id: str = Query(...)):
    db = SessionLocal()
    try:
        # Fetch from database
        convos = (
            db.query(Conversation)
            .filter(Conversation.user_id == user_id)
            .order_by(Conversation.timestamp.asc())
            .all()
        )
        db_messages = [
            {
                "role": c.role,
                "content": c.content,
                "timestamp": c.timestamp.isoformat()
            }
            for c in convos
        ]
        print(f"📚 DB history for {user_id}: {len(db_messages)} messages")

        # Also check in-memory history for any unsaved messages
        # (edge case: message in memory but DB commit not yet flushed)
        memory_history = nlp_service.get_user_history(user_id)
        db_contents = {m["content"] for m in db_messages}

        extra_messages = []
        for msg in memory_history:
            if msg["content"] not in db_contents:
                extra_messages.append({
                    "role": msg["role"],
                    "content": msg["content"],
                    "timestamp": datetime.utcnow().isoformat()
                })

        if extra_messages:
            print(f"🧠 Found {len(extra_messages)} in-memory messages not yet in DB")

        all_messages = db_messages + extra_messages
        return {"messages": all_messages}

    except Exception as e:
        print(f"❌ History error: {e}")
        return {"messages": []}
    finally:
        db.close()

# --------------------------
# Resources Endpoint
# --------------------------
@router.get("/resources")
def get_resources():
    return {
        "hotlines": {
            "Kenya": "+254 711 037 722",
            "USA": "988",
            "UK": "116 123"
        },
        "tips": [
            "Take slow, deep breaths for 5 minutes",
            "Go for a short walk outside",
            "Talk to someone you trust",
            "Practice mindfulness or meditation",
            "Write down three things you're grateful for",
            "Drink a glass of water and rest"
        ]
    }