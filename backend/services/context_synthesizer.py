"""
Context Synthesizer - Transforms collected signals into a Dharmic Query Object
"""
from typing import List, Optional
import logging

from models.session import SessionState, SignalType
from models.dharmic_query import (
    DharmicQueryObject,
    QueryType,
    UserStage,
    ResponseStyle,
)

logger = logging.getLogger(__name__)

# Mapping rules for dharmic concept selection based on emotion
EMOTION_TO_CONCEPTS = {
    'anxiety': ['vairagya', 'surrender', 'present_moment', 'trust', 'breath'],
    'sadness': ['impermanence', 'acceptance', 'dharma', 'seva', 'compassion'],
    'anger': ['patience', 'forgiveness', 'detachment', 'ahimsa', 'self_control'],
    'confusion': ['viveka', 'clarity', 'svadharma', 'guidance', 'wisdom'],
    'fear': ['courage', 'faith', 'surrender', 'protection', 'strength'],
    'hopelessness': ['hope', 'grace', 'perseverance', 'dharma', 'faith'],
    'frustration': ['patience', 'acceptance', 'karma', 'equanimity', 'detachment'],
    'guilt': ['forgiveness', 'redemption', 'dharma', 'renewal', 'self_compassion'],
    'loneliness': ['connection', 'devotion', 'sangha', 'inner_self', 'love'],
    'stress': ['peace', 'balance', 'karma_yoga', 'detachment', 'breath'],
    'overwhelm': ['surrender', 'one_step', 'trust', 'simplicity', 'present_moment'],
}

# Life domain to relevant scriptures mapping
LIFE_DOMAIN_TO_SCRIPTURES = {
    'work': ['Bhagavad Gita', 'Mahabharata'],
    'family': ['Ramayana', 'Mahabharata', 'Bhagavad Gita'],
    'relationships': ['Ramayana', 'Bhagavad Gita'],
    'health': ['Sanatan Scriptures', 'Bhagavad Gita'],
    'spiritual': ['Bhagavad Gita', 'Sanatan Scriptures'],
    'financial': ['Mahabharata', 'Bhagavad Gita'],
    'career': ['Bhagavad Gita', 'Mahabharata'],
}

# Emotion to guidance type mapping
EMOTION_TO_GUIDANCE_TYPE = {
    'anxiety': 'comfort',
    'sadness': 'comfort',
    'anger': 'understanding',
    'confusion': 'clarity',
    'fear': 'reassurance',
    'hopelessness': 'hope',
    'frustration': 'perspective',
    'guilt': 'forgiveness',
    'loneliness': 'connection',
    'stress': 'relief',
    'overwhelm': 'simplification',
}

# Default scriptures when no domain specified
DEFAULT_SCRIPTURES = ['Bhagavad Gita', 'Ramayana', 'Mahabharata']

# Default concepts when no emotion specified
DEFAULT_CONCEPTS = ['dharma', 'karma', 'peace', 'wisdom']

# Profession-specific dharmic concepts
PROFESSION_TO_CONCEPTS = {
    'student': ['vidya', 'brahmacharya', 'guru_bhakti', 'discipline', 'learning'],
    'professional': ['karma_yoga', 'svadharma', 'nishkama_karma', 'excellence', 'balance'],
    'business': ['artha', 'dharmic_wealth', 'integrity', 'leadership', 'responsibility'],
    'parent': ['pitra_dharma', 'sanskara', 'grihastha_dharma', 'nurturing', 'patience'],
    'homemaker': ['seva', 'grihastha', 'nurturing', 'sacrifice', 'steadfastness'],
    'retired': ['vanaprastha', 'moksha', 'tyaga', 'wisdom_sharing', 'spiritual_practice'],
    'caregiver': ['seva', 'compassion', 'selfless_service', 'patience', 'inner_strength'],
}

# Life stage specific concepts
LIFE_STAGE_TO_CONCEPTS = {
    'education': ['vidya', 'focus', 'discipline', 'growth', 'foundation'],
    'early_career': ['svadharma', 'purpose', 'karma_yoga', 'ambition', 'learning'],
    'mid_career': ['balance', 'leadership', 'dharma', 'responsibility', 'wisdom'],
    'family_raising': ['grihastha_dharma', 'patience', 'sacrifice', 'love', 'teaching'],
    'retirement': ['vanaprastha', 'reflection', 'moksha', 'sharing_wisdom', 'peace'],
}


class ContextSynthesizer:
    """
    Transforms collected signals into a Dharmic Query Object
    for targeted retrieval and response generation.
    """

    async def synthesize(self, session: SessionState) -> DharmicQueryObject:
        """
        Convert session signals into retrieval-ready query object.
        """
        signals = session.signals_collected

        # Extract signal values
        emotion = signals.get(SignalType.EMOTION)
        trigger = signals.get(SignalType.TRIGGER)
        life_domain = signals.get(SignalType.LIFE_DOMAIN)
        mental_state = signals.get(SignalType.MENTAL_STATE)
        user_goal = signals.get(SignalType.USER_GOAL)
        intent = signals.get(SignalType.INTENT)
        severity = signals.get(SignalType.SEVERITY)
        duration = signals.get(SignalType.DURATION)

        # Determine query type based on severity and intent
        query_type = self._determine_query_type(severity, intent, emotion)

        # Get dharmic concepts based on emotion
        dharmic_concepts = self._get_dharmic_concepts(emotion)

        # Determine user stage (default to seeker)
        user_stage = self._infer_user_stage(session)

        # Determine response style based on severity and intent
        response_style = self._determine_response_style(severity, intent, emotion)

        # Get allowed scriptures based on life domain
        allowed_scriptures = self._get_allowed_scriptures(life_domain)

        # Determine guidance type based on emotion
        guidance_type = self._get_guidance_type(emotion)

        # Build conversation summary
        conversation_summary = self._build_conversation_summary(session)

        dharmic_query = DharmicQueryObject(
            query_type=query_type,
            dharmic_concepts=dharmic_concepts,
            user_stage=user_stage,
            response_style=response_style,
            emotion=emotion.value if emotion else 'unknown',
            trigger=trigger.value if trigger else None,
            life_domain=life_domain.value if life_domain else None,
            mental_state=mental_state.value if mental_state else None,
            user_goal=user_goal.value if user_goal else None,
            allowed_scriptures=allowed_scriptures,
            guidance_type=guidance_type,
            conversation_summary=conversation_summary,
        )

        logger.info(
            f"Synthesized dharmic query: type={query_type.value}, "
            f"concepts={dharmic_concepts[:3]}, scriptures={allowed_scriptures[:2]}"
        )

        return dharmic_query

    def _determine_query_type(
        self,
        severity: Optional[any],
        intent: Optional[any],
        emotion: Optional[any]
    ) -> QueryType:
        """Determine the type of query/guidance needed"""
        # Crisis takes priority
        if severity and severity.value == 'crisis':
            return QueryType.CRISIS_SUPPORT

        # Check intent
        if intent:
            intent_value = intent.value
            if intent_value in ['action', 'guidance']:
                return QueryType.PRACTICAL_ADVICE
            if intent_value in ['understanding', 'perspective']:
                return QueryType.PHILOSOPHICAL

        # Check emotion for emotional healing
        if emotion and emotion.value in ['sadness', 'loneliness', 'hopelessness', 'guilt']:
            return QueryType.EMOTIONAL_HEALING

        # Default to life guidance
        return QueryType.LIFE_GUIDANCE

    def _get_dharmic_concepts(self, emotion: Optional[any]) -> List[str]:
        """Get relevant dharmic concepts based on emotion"""
        if emotion:
            concepts = EMOTION_TO_CONCEPTS.get(emotion.value, DEFAULT_CONCEPTS)
            return concepts[:5]  # Return top 5 concepts
        return DEFAULT_CONCEPTS

    def _infer_user_stage(self, session: SessionState) -> UserStage:
        """
        Infer user's spiritual stage from conversation.
        For now, defaults to SEEKER. Could be enhanced with explicit question.
        """
        # Check conversation for spiritual terminology
        spiritual_keywords = [
            'meditation', 'yoga', 'mantra', 'puja', 'dharma', 'karma',
            'bhagavad gita', 'scripture', 'temple', 'guru'
        ]

        conversation_text = ' '.join([
            m.get('content', '').lower()
            for m in session.conversation_history
            if m.get('role') == 'user'
        ])

        keyword_count = sum(1 for kw in spiritual_keywords if kw in conversation_text)

        if keyword_count >= 3:
            return UserStage.PRACTITIONER
        elif keyword_count >= 1:
            return UserStage.SEEKER
        else:
            return UserStage.BEGINNER

    def _determine_response_style(
        self,
        severity: Optional[any],
        intent: Optional[any],
        emotion: Optional[any]
    ) -> ResponseStyle:
        """Determine the response style based on context"""
        # Severe situations need gentle handling
        if severity and severity.value in ['severe', 'crisis']:
            return ResponseStyle.GENTLE_NURTURING

        # Check intent for action-oriented
        if intent and intent.value == 'action':
            return ResponseStyle.DIRECT_PRACTICAL

        # Understanding-seeking gets philosophical
        if intent and intent.value in ['understanding', 'perspective']:
            return ResponseStyle.PHILOSOPHICAL

        # Default to gentle nurturing for emotional support
        return ResponseStyle.GENTLE_NURTURING

    def _get_allowed_scriptures(self, life_domain: Optional[any]) -> List[str]:
        """Get relevant scriptures based on life domain"""
        if life_domain:
            return LIFE_DOMAIN_TO_SCRIPTURES.get(
                life_domain.value,
                DEFAULT_SCRIPTURES
            )
        return DEFAULT_SCRIPTURES

    def _get_guidance_type(self, emotion: Optional[any]) -> str:
        """Get the type of guidance needed based on emotion"""
        if emotion:
            return EMOTION_TO_GUIDANCE_TYPE.get(emotion.value, 'guidance')
        return 'guidance'

    def _build_conversation_summary(self, session: SessionState) -> str:
        """
        Build a rich summary using the memory context.
        This is the key improvement - we use the companion's understanding.
        """
        # Use the rich memory context if available
        if hasattr(session, 'memory') and session.memory:
            memory_summary = session.memory.get_memory_summary()
            if memory_summary:
                return memory_summary

        # Fallback to basic message summary
        user_messages = [
            m.get('content', '')[:150]
            for m in session.conversation_history
            if m.get('role') == 'user'
        ]

        if not user_messages:
            return ""

        # Take last 4 user messages
        recent_messages = user_messages[-4:]
        return " | ".join(recent_messages)

    def synthesize_from_memory(self, session: SessionState) -> DharmicQueryObject:
        """
        Enhanced synthesis using the rich memory context.
        This creates a more personalized dharmic query.
        """
        memory = session.memory
        story = memory.story

        # Extract from memory instead of signals
        emotion_value = story.emotional_state or 'unknown'
        trigger_value = story.trigger_event
        life_domain_value = story.life_area

        # Use memory's dharmic concepts + profile-based concepts
        dharmic_concepts = self._get_personalized_concepts(memory)

        # Determine query type from memory
        query_type = self._determine_query_type_from_memory(story)

        # User stage
        user_stage = self._infer_user_stage(session)

        # Response style based on emotional intensity
        response_style = self._determine_response_style_from_memory(memory)

        # Scriptures based on life area
        allowed_scriptures = LIFE_DOMAIN_TO_SCRIPTURES.get(
            life_domain_value,
            DEFAULT_SCRIPTURES
        ) if life_domain_value else DEFAULT_SCRIPTURES

        # Guidance type
        guidance_type = EMOTION_TO_GUIDANCE_TYPE.get(emotion_value, 'guidance')

        # Rich conversation summary from memory
        conversation_summary = memory.get_memory_summary()

        dharmic_query = DharmicQueryObject(
            query_type=query_type,
            dharmic_concepts=dharmic_concepts,
            user_stage=user_stage,
            response_style=response_style,
            emotion=emotion_value,
            trigger=trigger_value,
            life_domain=life_domain_value,
            mental_state=None,
            user_goal=story.unmet_needs[0] if story.unmet_needs else None,
            allowed_scriptures=allowed_scriptures,
            guidance_type=guidance_type,
            conversation_summary=conversation_summary,
        )

        logger.info(
            f"Synthesized from memory: type={query_type.value}, "
            f"concepts={dharmic_concepts[:3]}, primary_concern={story.primary_concern[:50] if story.primary_concern else 'N/A'}"
        )

        return dharmic_query

    def _determine_query_type_from_memory(self, story) -> QueryType:
        """Determine query type from user story"""
        # Check for crisis indicators in fears
        crisis_words = ['suicide', 'die', 'end it', 'no point', 'give up']
        if any(word in str(story.underlying_fears).lower() for word in crisis_words):
            return QueryType.CRISIS_SUPPORT

        # Check emotion
        emotion = story.emotional_state.lower() if story.emotional_state else ''
        if emotion in ['sadness', 'loneliness', 'hopelessness', 'grief']:
            return QueryType.EMOTIONAL_HEALING

        # Check needs
        needs = ' '.join(story.unmet_needs).lower() if story.unmet_needs else ''
        if 'guidance' in needs or 'direction' in needs:
            return QueryType.LIFE_GUIDANCE
        if 'understanding' in needs or 'meaning' in needs:
            return QueryType.PHILOSOPHICAL
        if 'action' in needs or 'steps' in needs:
            return QueryType.PRACTICAL_ADVICE

        return QueryType.LIFE_GUIDANCE

    def _determine_response_style_from_memory(self, memory) -> ResponseStyle:
        """Determine response style from emotional arc"""
        # Check emotional intensity from arc
        if memory.emotional_arc:
            recent_emotion = memory.emotional_arc[-1]
            if recent_emotion.get('intensity') == 'high':
                return ResponseStyle.GENTLE_NURTURING

        # Check if user seems action-oriented
        needs = ' '.join(memory.story.unmet_needs).lower() if memory.story.unmet_needs else ''
        if 'action' in needs or 'practical' in needs or 'steps' in needs:
            return ResponseStyle.DIRECT_PRACTICAL

        # Check for philosophical interest
        if 'understanding' in needs or 'meaning' in needs or 'why' in needs:
            return ResponseStyle.PHILOSOPHICAL

        return ResponseStyle.GENTLE_NURTURING

    def _get_personalized_concepts(self, memory) -> List[str]:
        """
        Get dharmic concepts personalized to user's profile.
        Combines emotion-based, profession-based, and life-stage-based concepts.
        """
        story = memory.story
        concepts = []

        # Start with memory's already-identified concepts
        if memory.relevant_concepts:
            concepts.extend(memory.relevant_concepts[:3])

        # Add emotion-based concepts
        if story.emotional_state:
            emotion_concepts = EMOTION_TO_CONCEPTS.get(story.emotional_state.lower(), [])
            concepts.extend(emotion_concepts[:2])

        # Add profession-specific concepts
        if story.profession:
            profession_concepts = PROFESSION_TO_CONCEPTS.get(story.profession.lower(), [])
            concepts.extend(profession_concepts[:2])

        # Add life-stage specific concepts
        if story.life_stage:
            stage_concepts = LIFE_STAGE_TO_CONCEPTS.get(story.life_stage.lower(), [])
            concepts.extend(stage_concepts[:2])

        # Remove duplicates while preserving order
        seen = set()
        unique_concepts = []
        for c in concepts:
            if c not in seen:
                seen.add(c)
                unique_concepts.append(c)

        # Return top 7 concepts, or defaults if empty
        return unique_concepts[:7] if unique_concepts else DEFAULT_CONCEPTS


# Singleton instance
_context_synthesizer: Optional[ContextSynthesizer] = None


def get_context_synthesizer() -> ContextSynthesizer:
    """Get or create the singleton ContextSynthesizer instance"""
    global _context_synthesizer
    if _context_synthesizer is None:
        _context_synthesizer = ContextSynthesizer()
    return _context_synthesizer
