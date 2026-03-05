"""
NLP Service for Mental Health Support 🌿
- Powered by Groq API
- Full conversation memory per user (in-memory + database)
- Local emotion detection
- Crisis detection
"""

import os
from groq import Groq
from transformers import pipeline
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

SYSTEM_PROMPT = """
You are Serene, a warm, empathetic, and professional mental health support assistant.
Your role is to provide emotional support, active listening, and gentle guidance.

Guidelines:
- Always respond with empathy and understanding
- Acknowledge the user's feelings before offering advice
- Ask thoughtful follow-up questions
- Offer practical coping strategies when appropriate
- Respond directly to the user's specific situation
- Keep responses concise but warm (2–4 sentences)
- Never diagnose or prescribe medication
- If the user seems to be in crisis, recommend contacting a crisis helpline
- Refer back to previous conversation naturally
- Do not repeat the same phrase twice
- Respond in the same language as the user
"""

# --------------------------
# Helper: emotion → 1-5 level
# --------------------------
def confidence_to_level(emotion: str, confidence: float) -> int:
    positive = ["joy", "happy", "content", "surprise"]
    negative = ["sadness", "anger", "fear", "disgust", "depressed", "sad"]
    if emotion in positive:
        return 4 if confidence < 0.8 else 5
    elif emotion in negative:
        return 2 if confidence < 0.8 else 1
    return 3


class NLPService:
    def __init__(self):
        print("Loading NLP models...")

        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = "llama-3.1-8b-instant"

        self.emotion_model = pipeline(
            "text-classification",
            model="j-hartmann/emotion-english-distilroberta-base",
            top_k=1,
            device=-1
        )

        self.user_histories: dict = {}
        self.MAX_HISTORY = 20

        print("Models loaded successfully!")

    # --------------------------
    # Emotion Detection
    # --------------------------
    def detect_emotion(self, text: str) -> dict:
        try:
            result = self.emotion_model(text)[0][0]
            return {
                "emotion": result["label"].lower(),
                "confidence": float(result["score"])
            }
        except Exception:
            return {"emotion": "neutral", "confidence": 0.5}

    # --------------------------
    # Crisis Detection
    # --------------------------
    def is_crisis(self, text: str) -> bool:
        crisis_keywords = [
            "kill myself", "suicide", "end my life",
            "harm myself", "i want to die", "don't want to live"
        ]
        return any(keyword in text.lower() for keyword in crisis_keywords)

    # --------------------------
    # Save message to DB
    # --------------------------
    def _save_message_to_db(self, user_id: str, role: str, content: str):
        try:
            from database.database import SessionLocal
            from database.models import Conversation
            db = SessionLocal()
            try:
                msg = Conversation(
                    user_id=user_id,
                    role=role,
                    content=content,
                    timestamp=datetime.utcnow()
                )
                db.add(msg)
                db.commit()
                print(f"✅ DB saved [{role}] for {user_id}: {content[:40]}...")
            except Exception as e:
                db.rollback()
                print(f"❌ DB save error: {e}")
            finally:
                db.close()
        except Exception as e:
            print(f"❌ DB connection error: {e}")

    # --------------------------
    # Save emotion to DB
    # --------------------------
    def _save_emotion_to_db(self, user_id: str, emotion: str, confidence: float):
        try:
            from services.emotion_service import emotion_service
            level = confidence_to_level(emotion, confidence)
            emotion_service.log_emotion(
                user_id=user_id,
                emotion=emotion,
                level=level
            )
            print(f"🎭 Emotion saved: {emotion} → level {level} for {user_id}")
        except Exception as e:
            print(f"❌ Emotion save error: {e}")

    # --------------------------
    # Load history from DB on first access
    # --------------------------
    def _initialize_user_from_db(self, user_id: str):
        """
        On first load, pull existing conversation from DB into memory
        so Groq has full context even after server restart
        """
        try:
            from database.database import SessionLocal
            from database.models import Conversation
            db = SessionLocal()
            try:
                convos = (
                    db.query(Conversation)
                    .filter(Conversation.user_id == user_id)
                    .order_by(Conversation.timestamp.asc())
                    .all()
                )
                # Rebuild in-memory history from DB
                history = [{"role": "system", "content": SYSTEM_PROMPT}]
                for c in convos:
                    history.append({"role": c.role, "content": c.content})

                # Trim if too long
                if len(history) > self.MAX_HISTORY:
                    history = [history[0]] + history[-self.MAX_HISTORY:]

                self.user_histories[user_id] = history
                print(f"📂 Loaded {len(convos)} messages from DB for {user_id}")
            finally:
                db.close()
        except Exception as e:
            print(f"❌ Failed to load history from DB: {e}")
            # Fallback to fresh history
            self.user_histories[user_id] = [
                {"role": "system", "content": SYSTEM_PROMPT}
            ]

    # --------------------------
    # Get User History (for frontend)
    # --------------------------
    def get_user_history(self, user_id: str):
        if user_id not in self.user_histories:
            self._initialize_user_from_db(user_id)
        history = self.user_histories.get(user_id, [])
        return [msg for msg in history if msg["role"] != "system"]

    # --------------------------
    # Main Chat Response
    # --------------------------
    def get_chat_response(self, user_message: str, user_id: str = "user123") -> dict:
        try:
            # Detect emotion
            emotion_result = self.detect_emotion(user_message)
            emotion = emotion_result["emotion"]
            confidence = emotion_result["confidence"]

            # Crisis check
            if self.is_crisis(user_message):
                crisis_reply = (
                    "I'm really concerned about you right now. "
                    "Please know you are not alone. "
                    "I strongly encourage you to reach out to a crisis helpline immediately — "
                    "Kenya: 0800 720 990, USA: 988, UK: 116 123. "
                    "I'm here with you. 💙"
                )
                # ✅ Save crisis exchange to DB
                self._save_message_to_db(user_id, "user", user_message)
                self._save_message_to_db(user_id, "assistant", crisis_reply)
                self._save_emotion_to_db(user_id, "crisis", 1.0)
                return {
                    "response": crisis_reply,
                    "emotion": "crisis",
                    "confidence": 1.0
                }

            # Initialize from DB if first time this session
            if user_id not in self.user_histories:
                self._initialize_user_from_db(user_id)

            history = self.user_histories[user_id]

            # Add user message to memory
            history.append({"role": "user", "content": user_message})

            # Trim if too long
            if len(history) > self.MAX_HISTORY:
                system_prompt = history[0]
                history = [system_prompt] + history[-self.MAX_HISTORY:]
                self.user_histories[user_id] = history

            # Send to Groq
            response = self.client.chat.completions.create(
                model=self.model,
                messages=history,
                max_tokens=300,
                temperature=0.8,
            )

            bot_reply = response.choices[0].message.content.strip()

            # Add assistant reply to memory
            history.append({"role": "assistant", "content": bot_reply})

            # ✅ Save both turns to DB
            self._save_message_to_db(user_id, "user", user_message)
            self._save_message_to_db(user_id, "assistant", bot_reply)

            # ✅ Save emotion to mood_logs
            self._save_emotion_to_db(user_id, emotion, confidence)

            return {
                "response": bot_reply,
                "emotion": emotion,
                "confidence": confidence
            }

        except Exception as e:
            print(f"❌ Groq error: {e}")
            return {
                "response": (
                    "I'm here with you. I'm having a little trouble connecting right now. "
                    "Would you like to try again?"
                ),
                "emotion": "neutral",
                "confidence": 0.5
            }


# Initialize once
nlp_service = NLPService()