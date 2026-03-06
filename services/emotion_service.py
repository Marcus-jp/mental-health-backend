from datetime import datetime
from typing import Optional
from database.database import SessionLocal
from database.models import MoodLog, Conversation
import traceback

CRISIS_KEYWORDS = [
    "kill myself", "end my life", "suicide",
    "i want to die", "i don't want to live"
]

class EmotionService:

    def detect_crisis(self, text: str) -> bool:
        try:
            result = any(kw in text.lower() for kw in CRISIS_KEYWORDS)
            print(f"🔍 Crisis detection for text: {text[:30]}... → {result}")
            return result
        except Exception as e:
            print(f"❌ Error in detect_crisis: {e}")
            print(traceback.format_exc())
            return False

    def log_emotion(self, user_id: str, emotion: str, level: int) -> Optional[dict]:
        db = SessionLocal()
        try:
            record = MoodLog(user_id=user_id, emotion=emotion, level=level)
            db.add(record)
            db.commit()
            db.refresh(record)
            print(f"🎭 Logged emotion for {user_id}: {emotion} → level {level}")
            return {
                "user_id": record.user_id,
                "emotion": record.emotion,
                "level": record.level,
                "timestamp": record.timestamp.isoformat()
            }
        except Exception as e:
            db.rollback()
            print(f"❌ Failed to log emotion: {e}")
            print(traceback.format_exc())
            return None
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
                print(f"⚠️ No mood logs found for {user_id}")
                return None
            print(f"📊 Latest mood for {user_id}: {record.emotion} → level {record.level}")
            return {
                "user_id": record.user_id,
                "emotion": record.emotion,
                "level": record.level,
                "timestamp": record.timestamp.isoformat()
            }
        except Exception as e:
            print(f"❌ Failed to fetch latest mood: {e}")
            print(traceback.format_exc())
            return None
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
            if not records:
                print(f"⚠️ No emotion trend data for {user_id}")
                return {"total_logs": 0, "emotions": []}
            emotions = [
                {
                    "emotion": r.emotion,
                    "level": r.level,
                    "timestamp": r.timestamp.isoformat()
                }
                for r in records
            ]
            print(f"📈 Retrieved {len(emotions)} emotion logs for {user_id}")
            return {"total_logs": len(emotions), "emotions": emotions}
        except Exception as e:
            print(f"❌ Failed to fetch emotion trend: {e}")
            print(traceback.format_exc())
            return {"total_logs": 0, "emotions": []}
        finally:
            db.close()

# Initialize singleton
emotion_service = EmotionService()