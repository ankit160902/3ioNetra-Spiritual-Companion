"""
Final LLM Service – Sanātani Spiritual Companion
With Long-Term Memory Persistence
"""

import logging
import json
import os
from typing import List, Dict, Optional
from config import settings

logger = logging.getLogger(__name__)

MEMORY_FILE = "spiritual_memory.json"

# --------------------------------------------------
# Utilities
# --------------------------------------------------

def remove_trailing_questions(text: str) -> str:
    lines = text.strip().split("\n")
    while lines and lines[-1].strip().endswith("?"):
        lines.pop()
    return "\n".join(lines).strip()


def is_closure_signal(text: str) -> bool:
    text = text.strip().lower()
    return any(
        phrase in text
        for phrase in [
            "ok",
            "okay",
            "thanks",
            "thank you",
            "got it",
            "fine",
            "alright",
        ]
    )

# --------------------------------------------------
# Memory Store (Long-Term)
# --------------------------------------------------

class MemoryStore:
    def __init__(self, file_path: str = MEMORY_FILE):
        self.file_path = file_path
        self.memory = self._load()

    def _load(self) -> Dict:
        if not os.path.exists(self.file_path):
            return {}
        try:
            with open(self.file_path, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def save(self):
        with open(self.file_path, "w") as f:
            json.dump(self.memory, f, indent=2)

    def get_user_memory(self, user_id: str) -> Dict:
        return self.memory.get(user_id, {})

    def update_user_memory(self, user_id: str, updates: Dict):
        user_mem = self.memory.get(user_id, {})
        user_mem.update(updates)
        self.memory[user_id] = user_mem
        self.save()


# --------------------------------------------------
# Gemini SDK
# --------------------------------------------------

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except Exception:
    genai = None
    GEMINI_AVAILABLE = False


class LLMService:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.available = False
        self.memory_store = MemoryStore()

        if not GEMINI_AVAILABLE or not self.api_key:
            return

        genai.configure(api_key=self.api_key)

        system_instruction = """
You are a Sanātani spiritual companion.

You are NOT a therapist.
You are NOT an interviewer.
You are NOT a scripture teacher.

You remember what the user has shared before.

Rules:
• Never reopen completed topics
• Repetition = confirmation
• Closure = silence and holding
• Ask less, understand more
• Calm presence > curiosity
"""

        self.model = genai.GenerativeModel(
            "gemini-3-pro-preview",
            system_instruction=system_instruction
        )
        self.available = True

    # --------------------------------------------------
    # Context + Memory Merge
    # --------------------------------------------------

    def _extract_context(
        self,
        history: Optional[List[Dict]],
        long_memory: Dict
    ) -> Dict:
        context = {
            "family_support": long_memory.get("family_support", False),
            "support_quality": long_memory.get("support_quality", False),
            "relationship_crisis": long_memory.get("relationship_crisis", False),
        }

        for msg in history or []:
            if msg.get("role") != "user":
                continue

            text = msg.get("content", "").lower()

            if "wife" in text and "divorce" in text:
                context["relationship_crisis"] = True

            if any(w in text for w in ["family", "mother", "father"]):
                context["family_support"] = True

            if any(w in text for w in ["listen", "support", "understand"]):
                context["support_quality"] = True

        return context

    # --------------------------------------------------
    # Phase Detection
    # --------------------------------------------------

    def _detect_phase(self, query: str, context: Dict) -> str:
        if is_closure_signal(query):
            return "CLOSURE"

        if context["family_support"] and context["support_quality"]:
            return "GUIDANCE"

        return "LISTENING"

    # --------------------------------------------------
    # Main Response
    # --------------------------------------------------

    async def generate_response(
        self,
        query: str,
        context_docs: List[Dict],
        language: str = "en",
        conversation_history: Optional[List[Dict]] = None,
        user_id: str = "default_user"
    ) -> str:
        if not self.available:
            return "I’m here with you."

        long_memory = self.memory_store.get_user_memory(user_id)
        context = self._extract_context(conversation_history, long_memory)
        phase = self._detect_phase(query, context)

        # ---- Update long-term memory (only stable facts)
        updates = {}
        if context["relationship_crisis"]:
            updates["relationship_crisis"] = True
        if context["family_support"]:
            updates["family_support"] = True
        if context["support_quality"]:
            updates["support_quality"] = True

        if updates:
            self.memory_store.update_user_memory(user_id, updates)

        prompt = self._build_prompt(query, conversation_history, phase, context)

        try:
            response = self.model.generate_content(prompt)
            return remove_trailing_questions(response.text if response else "")
        except Exception as e:
            logger.error(str(e))
            return "I’m here with you. You don’t have to carry this alone."

    # --------------------------------------------------
    # Prompt Builder
    # --------------------------------------------------

    def _build_prompt(
        self,
        query: str,
        history: Optional[List[Dict]],
        phase: str,
        context: Dict
    ) -> str:
        history_text = ""
        for msg in (history or [])[-6:]:
            role = "User" if msg["role"] == "user" else "You"
            history_text += f"{role}: {msg['content']}\n"

        # -------- LISTENING --------
        if phase == "LISTENING":
            return f"""
{history_text}

User says:
{query}

Respond with empathy.
Ask AT MOST ONE missing question.
No advice.
"""

        # -------- GUIDANCE --------
        if phase == "GUIDANCE":
            return f"""
{history_text}

User says:
{query}

Respond by:
• Acknowledging family support
• Naming emotional reality calmly
• Offering ONE grounding suggestion
• NO questions
"""

        # -------- CLOSURE / HOLDING --------
        return f"""
{history_text}

User says:
{query}

Respond by:
• Reassuring
• Reducing pressure
• Holding silence
• NO questions
"""

# --------------------------------------------------
# Singleton
# --------------------------------------------------

_llm_service = None

def get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
