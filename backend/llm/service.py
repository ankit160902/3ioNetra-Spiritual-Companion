"""
LLM Service for emotionally intelligent, non-repetitive
Sanātani spiritual companion using Google Gemini
"""

import logging
from typing import List, Dict, Optional
from config import settings

logger = logging.getLogger(__name__)


# -----------------------------
# Utility
# -----------------------------
def remove_trailing_questions(text: str) -> str:
    lines = text.strip().split("\n")
    while lines and lines[-1].strip().endswith("?"):
        lines.pop()
    return "\n".join(lines).strip()


def is_closure_signal(text: str) -> bool:
    return text.strip().lower() in {
        "ok", "okay", "alright", "fine", "i will do it",
        "i'll do it", "i will do it today", "yes", "yeah"
    }


# -----------------------------
# Gemini Import
# -----------------------------
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except Exception:
    genai = None
    GEMINI_AVAILABLE = False


class LLMService:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = None
        self.available = False

        if not GEMINI_AVAILABLE or not self.api_key:
            return

        genai.configure(api_key=self.api_key)

        system_instruction = """
You are a calm, emotionally intelligent Sanātani spiritual companion.

CORE BEHAVIOR:
• Listen deeply
• Remember what the user has already shared
• NEVER repeat questions on the same topic
• NEVER interrogate
• NEVER dump scriptures
• Guide gently, practically, and progressively

CONVERSATION STATES:

PHASE 1 – UNDERSTANDING
• Validate emotions
• Ask only unanswered factual questions
• Max 2–3 questions total
• Stop when understanding is sufficient

PHASE 2 – GUIDANCE
• Reflect the full situation clearly
• Give NEW, concrete guidance
• No philosophy repetition
• No questions

PHASE 3 – CONTAINMENT / CLOSURE
• User says “ok / I’ll do it”
• Stop probing
• Stabilize and reassure
• Hold emotional space

ABSOLUTE RULES:
• If user asks for solution / next step → PHASE 2
• If topic already discussed twice → LOCK IT
• If closure signal detected → NO QUESTIONS
• Sound like a wise human, not a therapist or guru
"""

        self.model = genai.GenerativeModel(
            "gemini-3-pro-preview",
            system_instruction=system_instruction
        )
        self.available = True

    # -----------------------------
    # CONTEXT & MEMORY
    # -----------------------------
    def _extract_context(self, history: Optional[List[Dict]]) -> Dict:
        context = {
            "duration": None,
            "support": None,
            "emotional_impact": None,
            "priority": None,
            "topics": {}
        }

        for msg in history or []:
            if msg.get("role") != "user":
                continue

            text = msg.get("content", "").lower()

            def count(topic):
                context["topics"][topic] = context["topics"].get(topic, 0) + 1

            if any(w in text for w in ["month", "months", "year"]):
                context["duration"] = True
                count("duration")

            if any(w in text for w in ["family", "mother", "mom", "father"]):
                context["support"] = "family"
                count("family")

            if any(w in text for w in ["cry", "stress", "hurt"]):
                context["emotional_impact"] = True
                count("emotion")

            if any(w in text for w in ["peace", "safe", "protect"]):
                context["priority"] = "peace"
                count("priority")

        return context

    def _is_topic_locked(self, context: Dict, topic: str) -> bool:
        return context["topics"].get(topic, 0) >= 2

    # -----------------------------
    # PHASE DETECTION
    # -----------------------------
    def _detect_phase(self, query: str, history: Optional[List[Dict]]) -> str:
        q = query.lower()

        if is_closure_signal(q):
            return "CLOSURE"

        decision_triggers = [
            "what should i do", "solution", "next step",
            "help me", "guide me", "save"
        ]
        if any(t in q for t in decision_triggers):
            return "PHASE_2"

        context = self._extract_context(history)
        known = sum(1 for v in [
            context["duration"],
            context["support"],
            context["emotional_impact"],
            context["priority"]
        ] if v)

        if known >= 2:
            return "PHASE_2"

        return "PHASE_1"

    # -----------------------------
    # RESPONSE
    # -----------------------------
    async def generate_response(
        self,
        query: str,
        context_docs: List[Dict],
        language: str = "en",
        conversation_history: Optional[List[Dict]] = None
    ) -> str:
        if not self.available:
            return "I’m here with you. Please continue."

        phase = self._detect_phase(query, conversation_history)
        prompt = self._build_prompt(query, conversation_history, phase)

        try:
            response = self.model.generate_content(prompt)
            text = response.text if response else ""
            return remove_trailing_questions(text)
        except Exception as e:
            logger.error(str(e))
            return "I’m here with you. Let’s take this one step at a time."

    # -----------------------------
    # PROMPT BUILDER
    # -----------------------------
    def _build_prompt(
        self,
        query: str,
        history: Optional[List[Dict]],
        phase: str
    ) -> str:
        history_text = ""
        for msg in (history or [])[-6:]:
            role = "User" if msg["role"] == "user" else "You"
            history_text += f"{role}: {msg['content']}\n"

        context = self._extract_context(history)

        # ---------- PHASE 1 ----------
        if phase == "PHASE_1":
            questions = []

            if not context["duration"] and not self._is_topic_locked(context, "duration"):
                questions.append("How long has this been going on for you?")

            if not context["support"] and not self._is_topic_locked(context, "family"):
                questions.append("Who do you have around you for support?")

            if not context["emotional_impact"]:
                questions.append("How is this affecting you emotionally day to day?")

            questions = questions[:2]
            q_block = "\n".join(f"• {q}" for q in questions)

            return f"""
{history_text}

User says:
{query}

Respond with:
1. Empathy and validation (1–2 lines)
2. Ask ONLY these questions:
{q_block}
3. End gently: “I’m listening.”

NO advice yet.
"""

        # ---------- PHASE 2 ----------
        if phase == "PHASE_2":
            return f"""
{history_text}

User says:
{query}

Respond with guidance:
• Reflect full understanding clearly
• Name the emotional pattern (without judgment)
• Give 2–3 practical, NEW actions
• Focus on emotional safety and stability
• No questions
• No scriptures
"""

        # ---------- CLOSURE ----------
        return f"""
{history_text}

User says:
{query}

Respond with containment:
• Acknowledge their effort
• Reduce pressure
• Reassure them they are doing enough
• No questions
• Hold calm emotional space
"""

# -----------------------------
# Singleton
# -----------------------------
_llm_service = None


def get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
