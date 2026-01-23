# User Context Integration for Companion Bot

## Summary
The companion bot now includes full user identification and context data in the memory context during conversations. This enables the companion to personalize responses with authenticated user information.

## Changes Made

### 1. **Enhanced Memory Context Model** 
**File:** `backend/models/memory_context.py`

Added user identification fields to `ConversationMemory` dataclass:
- `user_id: str` - Unique identifier for authenticated users
- `user_name: str` - User's full name for personalized greetings
- `user_email: str` - User's email for reference
- `user_phone: str` - User's contact number
- `user_created_at: str` - When the user account was created

These fields are stored at the beginning of the memory context and available throughout the conversation.

### 2. **Updated Conversation Endpoint**
**File:** `backend/main.py` - `/api/conversation` endpoint

Modified to:
- Accept optional `user` parameter through `get_current_user()` dependency
- Extract authenticated user information from the Authorization header
- Pre-populate session memory with user identification:
  ```python
  session.memory.user_id = user.get('id', '')
  session.memory.user_name = user.get('name', '')
  session.memory.user_email = user.get('email', '')
  session.memory.user_phone = user.get('phone', '')
  session.memory.user_created_at = user.get('created_at', '')
  ```
- Also extract user demographics (age_group, gender, profession) for personalization
- Works seamlessly with both authenticated and unauthenticated requests

### 3. **Updated Streaming Endpoint**
**File:** `backend/main.py` - `/api/conversation/stream` endpoint

Updated to:
- Accept the same `user` parameter
- Pass authenticated user context to the underlying `conversational_query()` function
- Maintains all user context through streaming responses

### 4. **Enhanced Response Composer**
**File:** `backend/services/response_composer.py` - `compose_with_memory()` method

Modified to:
- Include user identification in the system prompt when composing responses
- Displays user context in a dedicated section:
  ```
  USER IDENTIFICATION (Authenticated User):
  - User ID: {user_id}
  - Name: {user_name}
  - Email: {user_email}
  - Member since: {user_created_at}
  ```
- This information guides the LLM to create more personalized responses

## Data Flow

```
User Request (with Authorization header)
    ↓
get_current_user() extracts user info
    ↓
conversational_query() receives user dict
    ↓
Session created and memory populated with:
  - user_id
  - user_name
  - user_email
  - user_phone
  - user_created_at
  - Demographics (age_group, gender, profession)
    ↓
Companion processes message with full context
    ↓
Response composer uses memory with user context
    ↓
LLM generates personalized response
    ↓
Response sent to user
```

## Usage

When a user is authenticated (sends Authorization: Bearer token header):

```json
POST /api/conversation
Authorization: Bearer <token>
Content-Type: application/json

{
  "session_id": "optional-session-id",
  "message": "I'm struggling with work-life balance",
  "language": "en",
  "user_profile": {
    "age_group": "young_adult",
    "gender": "male",
    "profession": "software_engineer",
    "name": "John"
  }
}
```

The companion will have access to:
- Authenticated user's ID and profile
- All conversation history and memory
- User demographics for personalization
- Complete user context for truly personal wisdom

## Benefits

1. **Personalized Responses**: Companion knows who the user is and can tailor responses accordingly
2. **User Continuity**: Can reference user information across conversations
3. **Profile-Based Guidance**: Adjusts dharmic guidance based on user's age, profession, gender
4. **Accountability & Context**: All responses are tied to authenticated users
5. **Better Memory**: Companion remembers not just the story, but who the person is

## Backward Compatibility

- Endpoints still work with unauthenticated requests (user_id will be empty)
- Existing sessions without user context continue to function
- User profile fields default to empty strings if not provided
