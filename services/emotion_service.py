from datetime import datetime
from typing import Optional
from database.database import SessionLocal
from database.models import MoodLog, Conversation

CRISIS_KEYWORDS = [
    "kill myself", "end my life", "suicide",
    "i want to die", "i don't want to live"
]

class EmotionService:

    def detect_crisis(self, text: str) -> bool:
        return any(kw in text.lower() for kw in CRISIS_KEYWORDS)

    def log_emotion(self, user_id: str, emotion: str, level: int):
        db = SessionLocal()
        try:
            record = MoodLog(user_id=user_id, emotion=emotion, level=level)
            db.add(record)
            db.commit()
            db.refresh(record)
            return {
                "user_id": record.user_id,
                "emotion": record.emotion,
                "level": record.level,
                "timestamp": record.timestamp.isoformat()
            }
        finally:
            db.close()

    def get_latest_mood(self, user_id: str) -> Optional[dict]:
        db = SessionLocal()
        try:
            record = (
                db.query(MoodLog)
                .filter(MoodLog.user_id == user_id)
                .order_by(MoodLog.timestamp.desc())
                .first()
            )
            if not record:
                return None
            return {
                "user_id": record.user_id,
                "emotion": record.emotion,
                "level": record.level,
                "timestamp": record.timestamp.isoformat()
            }
        finally:
            db.close()

    def get_emotion_trend(self, user_id: str):
        db = SessionLocal()
        try:
            records = (
                db.query(MoodLog)
                .filter(MoodLog.user_id == user_id)
                .order_by(MoodLog.timestamp.asc())
                .all()
            )
            emotions = [
                {
                    "emotion": r.emotion,
                    "level": r.level,
                    "timestamp": r.timestamp.isoformat()
                }
                for r in records
            ]
            return {"total_logs": len(emotions), "emotions": emotions}
        finally:
            db.close()

emotion_service = EmotionService()