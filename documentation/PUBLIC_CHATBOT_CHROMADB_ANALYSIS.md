# Public Chatbot with ChromaDB - Architecture & Conversation Flow Analysis

## Overview

The public chatbot is a **completely isolated** system that uses ChromaDB for knowledge base search and integrates with the existing LLM infrastructure. It operates independently from the main AI Catalogue system.

## Architecture Components

### 1. **ChromaDB Integration** (`backend/public_chatbot/services.py`)

**Purpose**: ChromaDB is used **exclusively for knowledge base vector search**, NOT for storing conversations.

**Key Features**:
- **Isolated Service**: `PublicKnowledgeService` - singleton pattern
- **Connection**: Connects to ChromaDB via HTTP client (default: `localhost:8000`)
- **Fallback**: Falls back to persistent local mode if HTTP connection fails
- **Embeddings**: Uses SentenceTransformer embeddings (or default if unavailable)
- **Collection**: Uses a dedicated collection `public_knowledge_base` (separate from Milvus)

**Knowledge Base Management**:
- Documents are stored in `PublicKnowledgeDocument` model (Django)
- Admin can approve/review documents before syncing to ChromaDB
- Documents are chunked and embedded when synced to ChromaDB
- Supports document deletion and smart sync

### 2. **Request Tracking** (`backend/public_chatbot/models.py`)

**PublicChatRequest Model**:
- Tracks **individual requests**, not full conversations
- Stores: `request_id`, `session_id`, `message`, `response`, metrics
- **session_id**: Optional field for grouping requests, but NOT used to retrieve conversation history
- **message**: Full message content is stored
- **response**: Response length tracked, but full response NOT stored (privacy-focused)

**Key Fields**:
- `session_id`: For optional client-side conversation tracking
- `message`: Full user message (stored)
- `message_preview`: First 100 chars (for admin display)
- `response_length`: Length of response (not full content)
- ChromaDB metrics: `chroma_search_time_ms`, `chroma_results_found`, `chroma_context_used`
- LLM metrics: `llm_provider_used`, `llm_model_used`, `llm_tokens_used`

### 3. **API Endpoints** (`backend/public_chatbot/views.py`)

**Two Endpoints**:
1. **`/api/public-chatbot/`** - Standard request/response
2. **`/api/public-chatbot/stream/`** - Streaming response (OpenAI only)

## Conversation Flow

### Current Implementation: **Client-Side Conversation Management**

```
┌─────────────┐
│   Client    │
│  (Browser)  │
└──────┬──────┘
       │
       │ 1. POST /api/public-chatbot/
       │    {
       │      "message": "User question",
       │      "session_id": "abc123",  // Optional
       │      "conversation": [        // REQUIRED - Client sends full history
       │        {"role": "user", "content": "Previous question"},
       │        {"role": "assistant", "content": "Previous answer"}
       │      ]
       │    }
       │
       ▼
┌─────────────────────────────────────┐
│  Backend: public_chat_api()         │
│                                      │
│  1. Extract conversation_context     │
│  2. Search ChromaDB (if enabled)     │
│  3. Generate LLM response            │
│  4. Save PublicChatRequest record    │
│  5. Return response                  │
└──────┬──────────────────────────────┘
       │
       │ 2. Response
       │    {
       │      "status": "success",
       │      "response": "AI answer",
       │      "metadata": {...}
       │    }
       │
       ▼
┌─────────────┐
│   Client    │
│  Updates    │
│  Local      │
│  History    │
└─────────────┘
```

### Key Points:

1. **Conversation Context is Client-Responsibility**:
   - Client must send the **full conversation history** in each request
   - Backend does NOT retrieve conversation history from database
   - `session_id` is stored but NOT used to reconstruct conversations

2. **ChromaDB Search Flow**:
   ```
   User Message → ChromaDB Vector Search → Top 10 Results → Context Injection → LLM
   ```

3. **Query Enhancement** (for subsequent queries):
   - **First Query**: Uses context-aware query building (appends conversation history)
   - **Subsequent Queries**: Can use LLM-based query rephrasing (if enabled)
   - Rephrasing makes queries more complete and searchable

4. **Response Generation**:
   - Builds structured messages array from `conversation_context`
   - Injects ChromaDB search results into system prompt
   - Calls LLM with full conversation history + knowledge base context

## Conversation Storage Analysis

### ✅ **What IS Captured**:

1. **Individual Request Records**:
   - Each request/response pair is saved to `PublicChatRequest`
   - Full user message is stored
   - Response metadata (length, tokens, time) is stored
   - ChromaDB search metrics are stored

2. **Session Tracking**:
   - `session_id` is stored and indexed
   - Can be used for analytics/grouping requests
   - **BUT**: Not used to retrieve conversation history automatically

### ❌ **What is NOT Captured**:

1. **Full Conversation History**:
   - Full responses are NOT stored (only length)
   - No automatic conversation reconstruction from database
   - No endpoint to retrieve conversation by `session_id`

2. **Conversation State**:
   - No server-side conversation state management
   - No conversation persistence between sessions
   - Client must manage conversation history locally

### 🔍 **How to Reconstruct Conversations** (Manual):

If you need to reconstruct a conversation, you would need to:

```python
# Query all requests for a session_id
requests = PublicChatRequest.objects.filter(
    session_id='abc123'
).order_by('created_at')

# Reconstruct conversation
conversation = []
for req in requests:
    conversation.append({
        'role': 'user',
        'content': req.message
    })
    # Note: Full response not stored, only length
    conversation.append({
        'role': 'assistant',
        'content': f'[Response length: {req.response_length} chars]'
    })
```

**Limitation**: Full assistant responses are NOT stored, so reconstruction is incomplete.

## ChromaDB Usage Summary

### What ChromaDB Stores:
- ✅ **Knowledge Base Documents**: Chunked and embedded documents for RAG
- ✅ **Document Metadata**: Title, category, source, etc.
- ✅ **Vector Embeddings**: For semantic search

### What ChromaDB Does NOT Store:
- ❌ **Conversations**: Not used for conversation storage
- ❌ **User Messages**: Not stored in ChromaDB
- ❌ **Chat History**: No conversation persistence in ChromaDB

## Configuration

**ChatbotConfiguration Model**:
- `enable_vector_search`: Enable/disable ChromaDB search
- `enable_query_rephrasing`: Enable LLM-based query rephrasing for subsequent queries
- `max_search_results`: Max results from ChromaDB (default: 5)
- `similarity_threshold`: Minimum similarity score (default: 0.7)
- `log_full_conversations`: Boolean flag (default: False) - **Currently not implemented**

## Recommendations

### If You Want Full Conversation Storage:

1. **Add Response Storage**:
   ```python
   # In PublicChatRequest model
   response = models.TextField(blank=True)  # Store full response
   ```

2. **Add Conversation Retrieval Endpoint**:
   ```python
   def get_conversation_by_session(session_id: str):
       requests = PublicChatRequest.objects.filter(
           session_id=session_id
       ).order_by('created_at')
       
       conversation = []
       for req in requests:
           conversation.append({
               'role': 'user',
               'content': req.message,
               'timestamp': req.created_at
           })
           conversation.append({
               'role': 'assistant',
               'content': req.response,  # If stored
               'timestamp': req.completed_at
           })
       return conversation
   ```

3. **Auto-Load Conversation Context**:
   - Modify `public_chat_api()` to check if `session_id` provided
   - If yes, retrieve conversation from database
   - Merge with client-provided `conversation_context` (client takes precedence)

## Summary

**Current State**:
- ✅ ChromaDB: Used for knowledge base search (RAG)
- ✅ Request Tracking: Individual requests are logged
- ✅ Session Tracking: `session_id` stored but not used for retrieval
- ❌ Conversation Storage: Full conversations NOT automatically stored/retrieved
- ❌ Server-Side State: No conversation state management

**Conversation Flow**:
- Client sends full conversation history with each request
- Backend processes request and returns response
- Client updates local conversation history
- Backend saves request/response metadata (not full conversation)

**ChromaDB Role**:
- **Purpose**: Vector search for knowledge base (RAG)
- **NOT used for**: Conversation storage or retrieval
- **Isolation**: Completely separate from main Milvus system
