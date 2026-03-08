import os
import json
import time
import traceback
from groq import Groq
from dotenv import load_dotenv
from datetime import datetime
from pathlib import Path

# Load .env from backend root
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

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

# Ordered list of fallback models (most preferred first)
GROQ_MODEL_PRIORITY = [
    "llama-3.3-70b-versatile",        # ✅ Current best general-purpose model
    "llama3-70b-8192",                 # Fallback: stable older 70B
    "llama3-8b-8192",                  # Fallback: lighter 8B
    "meta-llama/llama-4-scout-17b-16e-instruct",  # Fallback: Llama 4 Scout
]


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
        print("Loading NLP service...")

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            print("⚠️ WARNING: GROQ_API_KEY not found! Chat will not work.")

        self.client = Groq(api_key=api_key)
        self.model = self._resolve_working_model()
        self.user_histories: dict = {}
        self.MAX_HISTORY = 20
        self.MAX_RETRIES = 3
        self.TIMEOUT = 15  # slightly more generous timeout

        print("NLP service loaded successfully!")

    # --------------------------
    # Probe each model in priority order and use the first that works
    # --------------------------
    def _resolve_working_model(self) -> str:
        for model in GROQ_MODEL_PRIORITY:
            try:
                print(f"🔍 Testing Groq model: {model} ...")
                self.client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "ping"}],
                    max_tokens=1,
                    temperature=0,
                )
                print(f"✅ Using model: {model}")
                return model
            except Exception as e:
                err = str(e)
                if "404" in err or "model_not_found" in err.lower() or "deprecated" in err.lower():
                    print(f"⚠️  Model '{model}' not available (404/deprecated), trying next...")
                else:
                    # Non-404 error (auth, rate limit, etc.) — still try next but log clearly
                    print(f"⚠️  Model '{model}' failed ({err[:120]}), trying next...")

        # If all fail, default to the most stable known model and let runtime errors surface
        fallback = GROQ_MODEL_PRIORITY[-1]
        print(f"❌ No model passed probe. Defaulting to: {fallback}")
        return fallback

    # --------------------------
    # Retry helper for Groq calls
    # --------------------------
    def _retry_groq_call(self, func):
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                return func()
            except Exception as e:
                err = str(e)
                wait_time = 2 ** attempt
                print(f"❌ Groq call failed (attempt {attempt}): {err[:200]}")
                if "404" in err or "model_not_found" in err.lower():
                    print("🔄 Model appears deprecated. Re-resolving model...")
                    self.model = self._resolve_working_model()
                if attempt < self.MAX_RETRIES:
                    print(f"⏳ Retrying in {wait_time}s...")
                    time.sleep(wait_time)
        print("❌ All Groq retries exhausted.")
        return None

    # --------------------------
    # Emotion Detection
    # --------------------------
    def detect_emotion(self, text: str) -> dict:
        def _call():
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an emotion classifier. "
                            "Respond with ONLY a valid JSON object like: "
                            '{"emotion": "joy", "confidence": 0.9}. '
                            "Choose emotion from: joy, sadness, anger, fear, disgust, surprise, neutral. "
                            "No extra text, no markdown, just the JSON object."
                        ),
                    },
                    {"role": "user", "content": f"Classify the emotion in this text: {text}"},
                ],
                max_tokens=50,
                temperature=0.1,
                timeout=self.TIMEOUT,
            )
            raw = response.choices[0].message.content.strip()
            # Strip markdown fences if model adds them despite instructions
            raw_clean = raw.strip("`").replace("json", "", 1).strip().split("\n")[0].strip()
            return json.loads(raw_clean)

        result = self._retry_groq_call(_call)
        if result:
            return {
                "emotion": result.get("emotion", "neutral").lower(),
                "confidence": float(result.get("confidence", 0.5)),
            }
        print("⚠️ Falling back to neutral emotion due to Groq failure")
        return {"emotion": "neutral", "confidence": 0.5}

    # --------------------------
    # Crisis Detection
    # --------------------------
    def is_crisis(self, text: str) -> bool:
        crisis_keywords = [
            "kill myself",
            "suicide",
            "end my life",
            "harm myself",
            "i want to die",
            "don't want to live",
            "want to die",
            "take my life",
        ]
        return any(keyword in text.lower() for keyword in crisis_keywords)

    # --------------------------
    # Save message & emotion to DB safely
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
                    timestamp=datetime.utcnow(),
                )
                db.add(msg)
                db.commit()
                print(f"✅ DB saved [{role}] for {user_id}: {content[:40]}...")
            except Exception as e:
                db.rollback()
                print(f"❌ DB save error: {e}")
                print(traceback.format_exc())
            finally:
                db.close()
        except Exception as e:
            print(f"❌ DB connection error: {e}")
            print(traceback.format_exc())

    def _save_emotion_to_db(self, user_id: str, emotion: str, confidence: float):
        try:
            from services.emotion_service import emotion_service

            level = confidence_to_level(emotion, confidence)
            emotion_service.log_emotion(user_id=user_id, emotion=emotion, level=level)
            print(f"🎭 Emotion saved: {emotion} → level {level} for {user_id}")
        except Exception as e:
            print(f"❌ Emotion save error: {e}")
            print(traceback.format_exc())

    # --------------------------
    # History management
    # --------------------------
    def _initialize_user_from_db(self, user_id: str):
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
                history = [{"role": "system", "content": SYSTEM_PROMPT}]
                for c in convos:
                    history.append({"role": c.role, "content": c.content})
                if len(history) > self.MAX_HISTORY:
                    history = [history[0]] + history[-self.MAX_HISTORY :]
                self.user_histories[user_id] = history
                print(f"📂 Loaded {len(convos)} messages from DB for {user_id}")
            finally:
                db.close()
        except Exception as e:
            print(f"❌ Failed to load history from DB: {e}")
            print(traceback.format_exc())
            self.user_histories[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

    def get_user_history(self, user_id: str):
        if user_id not in self.user_histories:
            self._initialize_user_from_db(user_id)
        return [msg for msg in self.user_histories.get(user_id, []) if msg["role"] != "system"]

    # --------------------------
    # Main chat response
    # --------------------------
    def get_chat_response(self, user_message: str, user_id: str = "user123") -> dict:
        try:
            emotion_result = self.detect_emotion(user_message)
            emotion = emotion_result["emotion"]
            confidence = emotion_result["confidence"]

            if self.is_crisis(user_message):
                crisis_reply = (
                    "I'm really concerned about you right now. "
                    "Please know you are not alone. "
                    "I strongly encourage you to reach out to a crisis helpline immediately — "
                    "Kenya: 0800 720 990, USA: 988, UK: 116 123. "
                    "I'm here with you. 💙"
                )
                self._save_message_to_db(user_id, "user", user_message)
                self._save_message_to_db(user_id, "assistant", crisis_reply)
                self._save_emotion_to_db(user_id, "crisis", 1.0)
                return {"response": crisis_reply, "emotion": "crisis", "confidence": 1.0}

            if user_id not in self.user_histories:
                self._initialize_user_from_db(user_id)

            history = self.user_histories[user_id]
            history.append({"role": "user", "content": user_message})
            if len(history) > self.MAX_HISTORY:
                history = [history[0]] + history[-self.MAX_HISTORY :]
                self.user_histories[user_id] = history

            def _call_chat():
                return self.client.chat.completions.create(
                    model=self.model,
                    messages=history,
                    max_tokens=300,
                    temperature=0.8,
                    timeout=self.TIMEOUT,
                )

            response = self._retry_groq_call(_call_chat)
            if response:
                bot_reply = response.choices[0].message.content.strip()
            else:
                bot_reply = (
                    "I'm here with you. I'm having a little trouble connecting right now. "
                    "Would you like to try again?"
                )
                emotion = "neutral"
                confidence = 0.5

            history.append({"role": "assistant", "content": bot_reply})
            self._save_message_to_db(user_id, "user", user_message)
            self._save_message_to_db(user_id, "assistant", bot_reply)
            self._save_emotion_to_db(user_id, emotion, confidence)

            return {"response": bot_reply, "emotion": emotion, "confidence": confidence}

        except Exception as e:
            print(f"❌ Unexpected error in chat response: {e}")
            print(traceback.format_exc())
            return {
                "response": (
                    "I'm here with you. I'm having a little trouble connecting right now. "
                    "Would you like to try again?"
                ),
                "emotion": "neutral",
                "confidence": 0.5,
            }


# Initialize once
nlp_service = NLPService()