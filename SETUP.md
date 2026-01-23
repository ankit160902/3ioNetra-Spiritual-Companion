# 3ioNetra Spiritual Companion - Setup & Configuration Guide

## Overview
3ioNetra is a spiritual companion chatbot that provides personalized guidance based on Sanatan Dharma. The system has two modes of operation:

1. **DEMO MODE** (No LLM required) - Works without API keys using template-based contextual responses
2. **FULL MODE** (With LLM) - Requires Gemini API key for deep personalization and full memory utilization

## Current Status

Your bot is currently running in **DEMO MODE** without an LLM API key. This means:
- ✅ User authentication and profile collection working
- ✅ Conversation memory building contextual responses
- ✅ Emotion detection and dharmic guidance provided
- ✅ Bot can reach "answering" phase and provide wisdom
- ⚠️ Responses are template-based (excellent, but not deeply personalized)
- ⚠️ Verse retrieval limited to emotion-mapped verses (not full RAG retrieval)

## How to Enable Full Mode with Gemini API

### Step 1: Get Gemini API Key

1. Visit [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Sign in with your Google account
3. Click "Create API Key"
4. Select or create a project
5. Copy the generated API key

### Step 2: Configure .env File

Edit `/backend/.env` and replace the placeholder:

```env
# BEFORE (placeholder)
GEMINI_API_KEY=your-gemini-api-key-here

# AFTER (with actual key)
GEMINI_API_KEY=sk-1234567890abcdefghijklmnop...
```

**Important:** 
- Keep your API key secret - never commit it to version control
- Add `.env` to `.gitignore` if not already added

### Step 3: Restart the Backend

```bash
# Stop the running backend
Ctrl+C

# Restart with the new configuration
cd backend
python main.py

# Or if using Docker:
docker-compose up --build backend
```

### Step 4: Verify LLM is Connected

Check the backend logs for:
```
CompanionEngine initialized with Gemini
ResponseComposer initialized with Gemini
```

Once you see these messages, the system is in **FULL MODE** with deep personalization enabled.

---

## System Architecture & How It Works

### Demo Mode (Current - No LLM)

```
User Message
    ↓
[Companion Engine - Basic Analysis]
    ↓
[Memory Context Updated with Emotion/Life Area]
    ↓
[Readiness Check: emotion + context + 2+ quotes → Yes at turn 4+]
    ↓
[Answering Phase Triggered]
    ↓
[Dharmic Query Synthesized from Memory]
    ↓
[Response Composer - Emotion-Based Fallback]
    ↓
Contextual Dharmic Response + Emotion-Specific Verse
    ↓
Response Sent to User
```

**Demo Mode Strengths:**
- Contextual template responses (not repetitive)
- Emotion detection with keyword matching
- Dharmic concept mapping
- Emotion-specific dharmic verses included
- Practical actions tailored to emotion
- Works immediately - no API keys needed

### Full Mode (With Gemini API)

```
User Message
    ↓
[Companion Engine - Gemini Deep Analysis]
    ↓
[Extract: emotion, trigger, fears, needs, quotes, demographics]
    ↓
[Memory Context Updated with Deep Understanding]
    ↓
[Readiness Check: 0.8 readiness + 3 quotes + full context]
    ↓
[Answering Phase Triggered]
    ↓
[Context Synthesizer - Build Dharmic Query]
    ↓
[RAG Pipeline - Vector Search for Relevant Verses]
    ↓
[Response Composer - Gemini Personalization]
    ↓
Deeply Personal Response with Retrieved Verses
    ↓
Response Sent to User with Citations
```

**Full Mode Enhancements:**
- LLM deep analysis (understands nuance and context)
- Full RAG retrieval (finds most relevant scriptures)
- Personalized responses (references user's specific story)
- User demographics used for tailoring
- Multi-turn memory optimization
- Response validation and safety checks

---

## User Journey in Both Modes

### Demo Mode - 4-5 Turn Conversation
1. **Turn 1:** User shares concern → Bot asks opening question
2. **Turn 2:** User clarifies → Bot detects emotion, asks follow-up
3. **Turn 3:** User provides context → Bot builds memory
4. **Turn 4:** User shares impact → Bot transitions to ANSWERING
5. **Turn 5:** Bot provides dharmic wisdom with emotion-specific verse

### Full Mode - 5-7 Turn Conversation
1. **Turn 1:** User shares → LLM analyzes deeply
2. **Turn 2-3:** Bot asks probing questions (emotion, trigger, fears)
3. **Turn 4-5:** Bot clarifies needs and life stage
4. **Turn 6:** LLM reaches 0.8 readiness → Synthesis
5. **Turn 7+:** RAG retrieves relevant verses → Personalized response

---

## Troubleshooting

### Problem: Bot returning same response repeatedly

**Demo Mode:** The bot should now provide contextual responses based on:
- Detected emotion (anxiety → different questions)
- Detected life area (work → work-specific follow-ups)
- Turn number (varied defaults to avoid repetition)

**If still seeing repetition:**
1. Check that emotion is being detected (look in logs for `emotional_state:`)
2. Verify message contains emotion keywords (see `_basic_analysis()` method)
3. Try messages with clearer emotion signals

### Problem: Bot not transitioning to wisdom phase

**Demo Mode:** Should transition at Turn 4 if:
- ✅ Emotion detected (emotional_state set)
- ✅ Primary concern stated (50+ character string)
- ✅ At least 2 user quotes collected

**Full Mode:** Requires at least Turn 5+ with:
- ✅ Emotion detected
- ✅ Clear concern (50+ characters)
- ✅ Life area or trigger event
- ✅ Duration or fears or needs
- ✅ 3+ user quotes
- ✅ Readiness score >= 0.8

**Debug steps:**
1. Check backend logs for `Not ready yet, missing: [list]`
2. Ensure emotion keywords appear in messages
3. Verify messages are clear and detailed

### Problem: API Key Not Recognized

```
Error: Failed to initialize CompanionEngine with Gemini
```

**Solution:**
1. Verify `.env` file is in `/backend/` directory (not elsewhere)
2. Check there's no `#` comment character in the API key line
3. Ensure no extra quotes around the key value
4. Restart the backend process completely
5. Check backend logs for initialization messages

### Problem: Verses Not Being Retrieved (Demo Mode)

In demo mode, verses come from emotion mapping, not RAG:
- Check detected emotion in logs
- Verify emotion is in the emotion_verses dictionary
- If emotion not in dict, add it (see line 405-415 in response_composer.py)

### Problem: No verse suggestions in response

This can happen if:
1. Emotion not detected (try more obvious emotion keywords)
2. Life area unclear
3. RAG pipeline not initialized (Full Mode)

**Quick fix:** Add explicit emotion keywords to test:
- Try: "I'm feeling really anxious" (not just "worried")
- Try: "This is affecting my work" (explicit life area)
- Try: "I'm feeling hopeless" (clear emotion state)

---

## Configuration Options

### Backend Configuration (`config.py`)

```python
# Conversation Flow - Control when bot transitions to wisdom
MIN_SIGNALS_THRESHOLD = 4          # Legacy setting (not used)
MIN_CLARIFICATION_TURNS = 3        # Legacy setting (not used)
MAX_CLARIFICATION_TURNS = 10       # Hard stop - force wisdom at turn 10

# LLM Settings
LLM_TEMPERATURE = 0.7              # 0.0-1.0 (higher = more creative)
LLM_MAX_TOKENS = 512               # Response length limit

# RAG Settings  
RETRIEVAL_TOP_K = 7                # Number of verses to retrieve
RERANK_TOP_K = 3                   # Top N after reranking
MIN_SIMILARITY_SCORE = 0.15         # Minimum match threshold
```

### Environment Variables (`.env`)

```env
# Critical - Leave empty for Demo Mode, add key for Full Mode
GEMINI_API_KEY=                    # Your API key here

# Optional - For future integrations
OPENAI_API_KEY=                    # Not currently used
HUGGINGFACE_TOKEN=                 # Not currently used

# Session Management
SESSION_TTL_MINUTES=60             # How long sessions persist

# Safety
ENABLE_CRISIS_DETECTION=true       # Check for crisis signals
CRISIS_HELPLINE_IN=iCall: 9152987821, Vandrevala: 1860-2662-345
```

---

## Testing the Bot

### Test Case 1: Anxiety (Demo Mode)

**User Messages:**
1. "I'm feeling really anxious about my future"
2. "Everything feels uncertain and I don't know what to do"
3. "It's been like this for a few months"
4. "I just want to feel calm and know that things will be okay"

**Expected Flow:**
- Turn 1-2: Bot detects anxiety
- Turn 3: Bot asks about cause/duration
- Turn 4: Bot transitions to wisdom
- Response: Acknowledgment + Bhagavad Gita verse about steady wisdom + breathing exercise

### Test Case 2: Work Stress

**User Messages:**
1. "Work is really stressful right now"
2. "I'm managing a big project and everything depends on me"
3. "I haven't had a day off in weeks"
4. "I feel exhausted and unmotivated"

**Expected Flow:**
- Turn 1-3: Bot detects stress + work context
- Turn 4: Bot transitions to wisdom
- Response: Acknowledgment + Karma yoga guidance + practical rest suggestion

### Test Case 3: Grief/Loss

**User Messages:**
1. "I lost someone important recently"
2. "It's been hard to accept that they're gone"
3. "I keep expecting to see them"
4. "I don't know how to move forward"

**Expected Flow:**
- Turn 1-3: Bot builds memory of grief
- Turn 4: Bot transitions to wisdom  
- Response: Acknowledgment + Bhagavad Gita on impermanence + meaningful action

---

## Performance Notes

### Demo Mode
- **Response Time:** < 1 second
- **Memory Used:** Minimal
- **Dependencies:** Python standard library only
- **Accuracy:** Good emotion detection, some life area misses

### Full Mode  
- **Response Time:** 2-4 seconds (LLM inference + RAG)
- **Memory Used:** Higher (models loaded)
- **Dependencies:** Gemini API + Qdrant vector DB
- **Accuracy:** Excellent - understands nuance and context

---

## Next Steps

### Immediate
1. ✅ Verify bot works in Demo Mode (should be working now)
2. ✅ Test conversation flow (4+ turns to wisdom)
3. ⏳ [Optional] Get Gemini API key for Full Mode

### Short Term  
- Add more emotion keywords to detection
- Improve life area mapping
- Test with real users
- Collect feedback on verse relevance

### Future Enhancements
- Multi-language support (Sanskrit verses with English)
- Visual scripture cards with explanations
- Meditation/breathing guide integration
- Community features (shared wisdom, mentorship)
- Analytics on conversation patterns

---

## Support

### Common Questions

**Q: Does the bot work without an API key?**  
A: Yes! Demo Mode provides excellent contextual guidance without any API keys.

**Q: Will my API key be secure?**  
A: Yes - keep it only in `.env` (never commit to git). System makes HTTPS calls to Google only.

**Q: How much does the Gemini API cost?**  
A: Free tier available with rate limits. Check [Google AI Pricing](https://ai.google.dev/pricing) for details.

**Q: Can I use OpenAI instead of Gemini?**  
A: Yes - future enhancement. Currently built for Gemini 2.0 Flash.

**Q: What if the bot gives wrong advice?**  
A: Bot provides comfort and scripture context, not medical/legal advice. Always include disclaimers in production.

---

**Last Updated:** 2024
**Mode:** Demo (No LLM)
**Status:** ✅ Working with contextual template responses
