# Eidolon Agent Memory - MCP Tools Reference

**Server**: `eidolon-agent-memory`  
**Total Tools**: 27 MCP tools + 3 resources  
**Transport**: stdio (default) or HTTP/SSE  
**Authentication**: API key required for all tools (except `provision_user`)

---

## Table of Contents

1. [Memory Read Tools](#memory-read-tools) (6 tools)
2. [Memory Write Tools](#memory-write-tools) (5 tools)
3. [Cognitive Generation Tools](#cognitive-generation-tools) (6 tools)
4. [Companion Management Tools](#companion-management-tools) (4 tools)
5. [Scheduler Tools](#scheduler-tools) (4 tools)
6. [Utility Tools](#utility-tools) (4 tools)
7. [Resources](#resources) (3 resources)

---

## Memory Read Tools

### 1. search_memory
**Category**: Memory / Retrieval  
**Purpose**: Search structured memory facts with hybrid semantic retrieval  
**Auth**: Required (api_key)

**Parameters**:
- `api_key` (string, required): Authentication token
- `companion_id` (string/uuid, required): Target companion
- `query` (string, required): Search query
- `intent` (string, optional): Query intent type
  - `"factual"` (default) - Balanced retrieval for most informational lookups
  - `"emotional"` - Boost HIGH-salience facts (grief/trauma/major events)
  - `"casual"` - Suppress HIGH-salience facts; lighthearted/fun messages
  - `"recall"` - Emphasise recency; "what has happened lately" queries
- `limit` (integer, optional, default=10): Max results to return

**Returns**:
```json
{
  "facts": [
    {
      "id": "uuid",
      "fact_text": "string",
      "predicate": "string",
      "category": "string",
      "emotional_salience": "HIGH|MED|LOW",
      "emotional_context": "string|null",
      "importance": 0.0-1.0,
      "confidence": 0.0-1.0,
      "scope": "user|shared|companion",
      "score": 0.0-1.0,
      "created_at": "ISO8601 datetime"
    }
  ],
  "count": integer
}
```

**Use Cases**: Recalling facts for response generation, user queries about stored knowledge  
**Do NOT Use**: Open-ended listing, casual greetings

---

### 2. get_context
**Category**: Memory / Context Building  
**Purpose**: Build structured context block from facts and episodic memory  
**Auth**: Required (api_key)

**Parameters**:
- `api_key` (string, required): Authentication token
- `companion_id` (string/uuid, required): Target companion
- `query` (string, required): Context query
- `intent` (string, optional): Intent modifier (same as search_memory)
  - `"factual"` (default)
  - `"emotional"`
  - `"casual"`
  - `"recall"`

**Returns**:
```json
{
  "context": "string (formatted markdown/text)",
  "fact_count": integer
}
```

**Use Cases**: Preparing context before generating a response, session startup initialization  
**Do NOT Use**: Single-fact lookup (use `lookup_fact` or `search_memory`)  
**Cost**: Moderate (retrieval + formatting)

---

### 3. lookup_fact
**Category**: Memory / Direct Lookup  
**Purpose**: Look up facts by subject and optional predicate  
**Auth**: Required (api_key)

**Parameters**:
- `api_key` (string, required): Authentication token
- `companion_id` (string/uuid, required): Target companion
- `subject` (string, required): Subject entity (e.g., "Alice", "job", "hobby")
- `predicate` (string, optional): Triple predicate (e.g., "IS_CALLED", "WORKS_AS")

**Returns**:
```json
{
  "facts": [
    {
      "id": "uuid",
      "fact_text": "string",
      "predicate": "string",
      "importance": 0.0-1.0,
      "confidence": 0.0-1.0,
      "emotional_salience": "HIGH|MED|LOW"
    }
  ]
}
```

**Use Cases**: Direct fact questions ("What's their job?"), structured queries  
**Do NOT Use**: Broad semantic exploration (use `search_memory`)

---

### 4. get_relationship
**Category**: Memory / Relationship State  
**Purpose**: Get relationship state between user and companion  
**Auth**: Required (api_key)

**Parameters**:
- `api_key` (string, required): Authentication token
- `companion_id` (string/uuid, required): Target companion

**Returns**:
```json
{
  "trust": 0.0-1.0,
  "closeness": 0.0-1.0,
  "interactions": integer,
  "absence_streak_days": integer,
  "milestones": ["string"]
}
```

**Use Cases**: Calibrating tone and intimacy, relationship tracking  
**Cost**: Low (direct lookup)

---

### 5. get_episodic
**Category**: Memory / Episodic (Events)  
**Purpose**: Search episodic memories (conversations, diary, dreams, reflections)  
**Auth**: Required (api_key)

**Parameters**:
- `api_key` (string, required): Authentication token
- `companion_id` (string/uuid, required): Target companion
- `query` (string, required): Search query
- `memory_types` (string, optional): Comma-separated CSV of memory types to filter
  - Available types: `conversation`, `reflection`, `diary`, `dream`, `musing`, `narrative`, `insight_synthesis`
  - Example: `"diary,dream,musing"`
  - Empty/omitted: search all types
- `intent` (string, optional): Intent modifier (same options as search_memory)
- `limit` (integer, optional, default=5): Max results

**Returns**:
```json
{
  "memories": [
    {
      "id": "uuid",
      "text": "string (full entry text)",
      "memory_type": "conversation|reflection|diary|dream|musing|narrative|insight_synthesis",
      "importance": 0.0-1.0,
      "score": 0.0-1.0
    }
  ]
}
```

**Use Cases**: Recalling past events, checking if topic was discussed, understanding conversation history  
**Cost**: Moderate (semantic search)

---

### 6. get_journal
**Category**: Memory / Journal  
**Purpose**: Retrieve current companion journal for authenticated user  
**Auth**: Required (api_key)

**Parameters**:
- `api_key` (string, required): Authentication token
- `companion_id` (string/uuid, required): Target companion

**Returns**:
```json
{
  "journal": "string (full formatted text)",
  "version": integer,
  "top_insights": [
    {
      "content": "string",
      "category": "string"
    }
  ],
  "preferences": {
    "key": "value"
  }
}
```

**Use Cases**: Loading personal context at session start  
**Do NOT Use**: Every message turn (call sparingly)  
**Cost**: Moderate (synthesis + formatting)

---

## Memory Write Tools

### 1. store_fact
**Category**: Memory / Manual Storage  
**Purpose**: Store a structured fact (subject-predicate-object triple)  
**Auth**: Required (api_key)

**Parameters**:
- `api_key` (string, required): Authentication token
- `companion_id` (string/uuid, required): Target companion
- `subject` (string, required): Subject entity (e.g., "Alice", "my job")
- `predicate` (string, required): Relationship type (e.g., "IS_CALLED", "WORKS_AS", "LIKES", "AVOIDS")
- `obj` (string, required): Object entity (e.g., "Alice", "software engineer", "chocolate")
- `fact_text` (string, required): Human-readable fact statement (e.g., "Alice works as a software engineer")
- `category` (string, optional): Fact category/domain
- `confidence` (float, optional, default=1.0): Confidence score (0.0-1.0)
- `importance` (float, optional, default=0.5): Importance/salience (0.0-1.0)
- `emotional_salience` (string, optional, default="LOW"): Emotional weight
  - `"HIGH"` - Grief/trauma/major life events
  - `"MED"` - Milestones/goals/important moments
  - `"LOW"` - Routine facts
- `emotional_context` (string, optional): Context for emotional salience
- `scope` (string, optional, default="user"): Fact scope
  - `"user"` - Private to this user
  - `"shared"` - Across companions
  - `"companion"` - Companion self-knowledge
- `created_at` (ISO8601 datetime, optional): Override creation timestamp
- `updated_at` (ISO8601 datetime, optional): Override update timestamp

**Returns**:
```json
{
  "edge_id": "uuid",
  "stored": true
}
```

**Use Cases**: User explicitly tells you something, importing from external sources  
**Do NOT Use**: Storing AI-generated inferences mid-conversation (use `extract_session_facts` after session)  
**Cost**: Low (direct write)

---

### 2. store_episodic
**Category**: Memory / Episodic Storage  
**Purpose**: Store one episodic memory entry  
**Auth**: Required (api_key)

**Parameters**:
- `api_key` (string, required): Authentication token
- `companion_id` (string/uuid, required): Target companion
- `text` (string, required): Memory content (conversation, reflection, etc.)
- `memory_type` (string, optional, default="conversation"): Memory category
  - `"conversation"` - Chat exchange
  - `"reflection"` - Conscious thought
  - `"diary"` - Diary-style entry
  - `"dream"` - Dream narrative
  - `"musing"` - Short observation
  - `"narrative"` - Story/account
  - `"insight_synthesis"` - Synthesized insight
- `importance` (float, optional, default=0.5): Importance (0.0-1.0)
- `session_id` (string/uuid, optional): Associate with session ID

**Returns**:
```json
{
  "memory_id": "uuid",
  "stored": true
}
```

**Use Cases**: Storing conversations, reflections, or narrative entries  
**Cost**: Low to moderate (write + optional embedding)

---

### 3. update_fact_importance
**Category**: Memory / Fact Modification  
**Purpose**: Update a fact's importance and optional confidence  
**Auth**: Required (api_key)

**Parameters**:
- `api_key` (string, required): Authentication token
- `edge_id` (string/uuid, required): ID of fact to update
- `importance` (float, required): New importance score (0.0-1.0)
- `confidence` (float, optional, default=-1.0): New confidence score (-1 = no change)

**Returns**:
```json
{
  "updated": true|false
}
```

**Notes**: Returns `false` if fact not found  
**Use Cases**: User correction, reprioritization after clarification  
**Cost**: Low (direct update)

---

### 4. delete_fact
**Category**: Memory / Fact Deletion  
**Purpose**: Permanently delete a fact edge  
**Auth**: Required (api_key)

**Parameters**:
- `api_key` (string, required): Authentication token
- `edge_id` (string/uuid, required): ID of fact to delete

**Returns**:
```json
{
  "deleted": true|false
}
```

**Notes**: Returns `false` if fact not found; destructive operation  
**Use Cases**: Only when user explicitly asks to forget  
**Cost**: Low (direct delete)

---

### 5. set_preference
**Category**: Memory / User Preferences  
**Purpose**: Set or update a user preference key-value pair  
**Auth**: Required (api_key)

**Parameters**:
- `api_key` (string, required): Authentication token
- `companion_id` (string/uuid, optional): Target companion (empty = global preference)
- `key` (string, required): Preference key (e.g., "language", "tone", "timezone")
- `value` (string, required): Preference value
- `source` (string, optional, default="explicit"): Preference source
  - `"explicit"` - User directly specified
  - `"inferred"` - Companion inferred
  - `"system"` - System default

**Returns**:
```json
{
  "key": "string",
  "value": "string",
  "stored": true
}
```

**Use Cases**: Storing user preferences, language choice, timezone, tone preference  
**Cost**: Low (direct write)

---

## Cognitive Generation Tools

### 1. generate_diary
**Category**: Cognitive / Reflection  
**Purpose**: Generate diary entry from companion perspective  
**Auth**: Required (api_key)

**Parameters**:
- `api_key` (string, required): Authentication token
- `companion_id` (string/uuid, required): Target companion

**Returns**:
```json
{
  "memory_id": "uuid",
  "memory_type": "diary",
  "text": "string (full diary entry)"
}
```

**Use Cases**: Daily reflection, scheduled background task  
**Do NOT Use**: Mid-conversation, on every session end  
**Cost**: HIGH (LLM generation + embeddings)  
**Suggested Frequency**: 1x per day per companion

---

### 2. generate_dream
**Category**: Cognitive / Creative Reflection  
**Purpose**: Generate surreal dream narrative about the user  
**Auth**: Required (api_key)

**Parameters**:
- `api_key` (string, required): Authentication token
- `companion_id` (string/uuid, required): Target companion

**Returns**:
```json
{
  "memory_id": "uuid",
  "memory_type": "dream",
  "text": "string (surreal narrative)"
}
```

**Use Cases**: Morning check-in, scheduled proactive task  
**Do NOT Use**: More than once per day per companion  
**Cost**: HIGH (LLM generation + embeddings)  
**Suggested Frequency**: 1x per day maximum

---

### 3. generate_musing
**Category**: Cognitive / Spontaneous Thought  
**Purpose**: Generate short spontaneous reflection/observation  
**Auth**: Required (api_key)

**Parameters**:
- `api_key` (string, required): Authentication token
- `companion_id` (string/uuid, required): Target companion

**Returns**:
```json
{
  "memory_id": "uuid",
  "memory_type": "musing",
  "text": "string (short thought, 1-3 sentences)"
}
```

**Use Cases**: Proactive message during idle time, autonomous task  
**Do NOT Use**: Inside active response generation  
**Cost**: MODERATE (LLM generation)  
**Suggested Frequency**: Multiple times per day (lite)

---

### 4. generate_insights
**Category**: Cognitive / Analysis  
**Purpose**: Analyze stored facts and generate psychological/behavioral insights  
**Auth**: Required (api_key)

**Parameters**:
- `api_key` (string, required): Authentication token
- `companion_id` (string/uuid, required): Target companion

**Returns**:
```json
{
  "insights": [
    {
      "id": "uuid",
      "content": "string (psychological insight)",
      "category": "string",
      "confidence": 0.0-1.0
    }
  ],
  "count": integer
}
```

**Use Cases**: After significant fact accumulation (>20 facts), weekly synthesis  
**Do NOT Use**: With fewer than 10 stored facts (output quality suffers)  
**Cost**: HIGH (LLM analysis + embeddings)  
**Notes**: Generates multiple insights; quality improves with more facts

---

### 5. refresh_journal
**Category**: Cognitive / Synthesis  
**Purpose**: Rebuild evolving companion journal for user  
**Auth**: Required (api_key)

**Parameters**:
- `api_key` (string, required): Authentication token
- `companion_id` (string/uuid, required): Target companion

**Returns**:
```json
{
  "journal_id": "uuid",
  "version": integer,
  "length": integer (character count)
}
```

**Use Cases**: After major memory changes, periodic maintenance  
**Cost**: EXPENSIVE (LLM synthesis + embeddings)  
**Suggested Frequency**: 1x per week or after significant conversations

---

### 6. extract_session_facts
**Category**: Cognitive / Extraction  
**Purpose**: Extract and persist structured facts from conversation text  
**Auth**: Required (api_key)

**Parameters**:
- `api_key` (string, required): Authentication token
- `companion_id` (string/uuid, required): Target companion
- `conversation_text` (string, required): Full conversation to extract from (usually whole session transcript)
- `session_id` (string/uuid, optional): Associate extracted facts with session

**Returns**:
```json
{
  "extraction_counts": {
    "facts_extracted": integer,
    "episodic_memories": integer,
    "preferences_found": integer,
    // ... varies by service implementation
  }
}
```

**Use Cases**: Post-session ingestion of meaningful exchanges  
**Do NOT Use**: Mid-conversation (use after session ends)  
**Cost**: HIGH (LLM extraction + embeddings for each fact)  
**Suggested Frequency**: Once per session end, async  
**Notes**: This is the primary fact ingestion mechanism

---

## Companion Management Tools

### 1. create_companion
**Category**: Companion / Profile  
**Purpose**: Create new companion profile for authenticated user  
**Auth**: Required (api_key)

**Parameters**:
- `api_key` (string, required): Authentication token
- `name` (string, required): Companion name (e.g., "Luna", "Alex")
- `persona` (string, optional): Companion persona description
- `pronouns` (string, optional): Pronouns (e.g., "she/her", "they/them")
- `personality_traits` (string, optional): CSV of traits (e.g., "empathetic,creative,curious")

**Returns**:
```json
{
  "companion_id": "uuid",
  "name": "string",
  "created": true
}
```

**Use Cases**: Initial companion setup, multiple companion management  
**Cost**: Low (direct write + initialization)

---

### 2. get_companion
**Category**: Companion / Profile  
**Purpose**: Get companion configuration details  
**Auth**: Required (api_key)

**Parameters**:
- `api_key` (string, required): Authentication token
- `companion_id` (string/uuid, required): Target companion

**Returns**:
```json
{
  "companion_id": "uuid",
  "name": "string",
  "persona": "string|null",
  "pronouns": "string|null",
  "personality_traits": ["string"]|null,
  "llm_config": "object|null"
}
// or
{
  "error": "companion_not_found"
}
```

**Use Cases**: Loading companion profile, verification  
**Cost**: Low

---

### 3. list_companions
**Category**: Companion / Discovery  
**Purpose**: List all companions for authenticated user  
**Auth**: Required (api_key)

**Parameters**:
- `api_key` (string, required): Authentication token

**Returns**:
```json
{
  "companions": [
    {
      "companion_id": "uuid",
      "name": "string",
      "pronouns": "string|null"
    }
  ],
  "count": integer
}
```

**Use Cases**: Companion selection UI, conversation startup  
**Cost**: Low

---

### 4. update_companion
**Category**: Companion / Profile  
**Purpose**: Update mutable companion fields  
**Auth**: Required (api_key)

**Parameters**:
- `api_key` (string, required): Authentication token
- `companion_id` (string/uuid, required): Target companion
- `persona` (string, optional): New persona description
- `pronouns` (string, optional): Updated pronouns
- `personality_traits` (string, optional): Updated CSV traits

**Returns**:
```json
{
  "companion_id": "uuid",
  "updated": true
}
// or
{
  "error": "companion_not_found"
}
```

**Use Cases**: Profile updates, persona refinement  
**Cost**: Low

---

## Scheduler Tools

### 1. set_task_schedule
**Category**: Scheduler / Task Configuration  
**Purpose**: Create or update autonomous scheduled task  
**Auth**: Required (api_key)

**Parameters**:
- `api_key` (string, required): Authentication token
- `companion_id` (string/uuid, required): Target companion
- `task_type` (string, required): Type of task
  - `"dream"` - Generate dream
  - `"diary"` - Generate diary
  - `"musing"` - Generate musing
  - `"insight"` - Generate insights
  - `"journal_refresh"` - Refresh journal
- `schedule` (string, required): Cron expression (e.g., "0 9 * * *" for 9 AM daily)
- `timezone` (string, optional, default="UTC"): Timezone for schedule

**Returns**:
```json
{
  "task_id": "uuid",
  "task_type": "string",
  "schedule": "string (cron)",
  "timezone": "string",
  "enabled": true
}
// or
{
  "error": "Unknown task_type"
}
```

**Use Cases**: Scheduling daily reflections, periodic journal updates, autonomous tasks  
**Cost**: Low (direct write)

---

### 2. list_task_schedules
**Category**: Scheduler / Query  
**Purpose**: List all scheduled tasks for one companion  
**Auth**: Required (api_key)

**Parameters**:
- `api_key` (string, required): Authentication token
- `companion_id` (string/uuid, required): Target companion

**Returns**:
```json
{
  "tasks": [
    {
      "task_id": "uuid",
      "task_type": "string",
      "schedule": "string (cron)",
      "timezone": "string",
      "enabled": true|false,
      "last_run_at": "ISO8601 datetime|null"
    }
  ],
  "count": integer
}
```

**Use Cases**: Task management UI, debugging schedules  
**Cost**: Low

---

### 3. toggle_task
**Category**: Scheduler / Control  
**Purpose**: Enable or disable a scheduled task  
**Auth**: Required (api_key)

**Parameters**:
- `api_key` (string, required): Authentication token
- `task_id` (string/uuid, required): Task ID to toggle
- `enabled` (boolean, required): true to enable, false to disable

**Returns**:
```json
{
  "task_id": "uuid",
  "enabled": true|false
}
// or
{
  "error": "task_not_found"
}
```

**Use Cases**: Pausing/resuming tasks, task lifecycle management  
**Cost**: Low

---

### 4. run_task_now
**Category**: Scheduler / Execution  
**Purpose**: Immediately execute one-shot cognitive task  
**Auth**: Required (api_key)

**Parameters**:
- `api_key` (string, required): Authentication token
- `companion_id` (string/uuid, required): Target companion
- `task_type` (string, required): Type of task to run
  - `"diary"` - Generate diary entry
  - `"dream"` - Generate dream
  - `"musing"` - Generate musing
  - `"insight"` - Generate insights
  - `"journal_refresh"` - Refresh journal

**Returns**:
```json
// For dream/diary/musing:
{
  "task_type": "string",
  "memory_id": "uuid",
  "text": "string"
}
// For insights:
{
  "task_type": "string",
  "count": integer,
  "insights": [...]
}
// For journal_refresh:
{
  "task_type": "string",
  "journal_id": "uuid",
  "version": integer
}
// or error:
{
  "error": "string"
}
```

**Use Cases**: On-demand reflection, testing before scheduling  
**Do NOT Use**: For maintenance tasks like decay or dedup  
**Cost**: HIGH (depends on task type)

---

## Utility Tools

### 1. info
**Category**: Utility / Diagnostics  
**Purpose**: Return diagnostic system info for authenticated user  
**Auth**: Required (api_key)

**Parameters**:
- `api_key` (string, required): Authentication token

**Returns**:
```json
{
  "version": "string (e.g., '0.1.0')",
  "user_id": "uuid",
  "active_facts": integer,
  "episodic_memories": integer,
  "capabilities": ["string"]
}
```

**Use Cases**: System health check, diagnostics, capability discovery  
**Cost**: Low

---

### 2. provision_user
**Category**: Utility / User Setup  
**Purpose**: Provision new user and return one-time raw API key  
**Auth**: NONE (open endpoint)

**Parameters**:
- `email` (string, optional): User email
- `name` (string, optional): User display name
- `timezone` (string, optional, default="UTC"): User timezone

**Returns**:
```json
{
  "user_id": "uuid",
  "api_key": "string (mnemo-... format, shown only once)",
  "warning": "Store this API key securely. It will not be shown again."
}
```

**Use Cases**: First-time setup, user registration  
**CRITICAL**: API key is not retrievable after this call; must be stored securely  
**Cost**: Low (write)

---

### 3. update_user_name
**Category**: Utility / User Profile  
**Purpose**: Update authenticated user's display name  
**Auth**: Required (api_key)

**Parameters**:
- `api_key` (string, required): Authentication token
- `name` (string, required): New display name

**Returns**:
```json
{
  "user_id": "uuid",
  "name": "string",
  "success": true
}
```

**Use Cases**: Updating user name, profile customization  
**Cost**: Low

---

### 4. get_user_info
**Category**: Utility / User Profile  
**Purpose**: Get authenticated user's profile information  
**Auth**: Required (api_key)

**Parameters**:
- `api_key` (string, required): Authentication token

**Returns**:
```json
{
  "user_id": "uuid",
  "name": "string|null",
  "email": "string|null",
  "timezone": "string"
}
```

**Use Cases**: Profile verification, before updating name or other info  
**Cost**: Low (read-only)

---

## Resources

MCP Resources are static or semi-static data sources accessible via URI protocol.

### 1. resource_companions
**URI**: `eidolon_agent_memory://user/{api_key}/companions`  
**Purpose**: List all companions for authenticated user  
**Auth**: Required (api_key in URI)

**Content Type**: JSON  
**Returns**: Same as `list_companions` tool

**Use Cases**: Resource-based access to companions list, client caching

---

### 2. resource_journal
**URI**: `eidolon_agent_memory://companion/{api_key}/{companion_id}/journal`  
**Purpose**: Current companion journal  
**Auth**: Required (api_key in URI)

**Content Type**: JSON  
**Returns**: Same as `get_journal` tool

**Use Cases**: Resource-based access to journal, client caching

---

### 3. resource_relationship
**URI**: `eidolon_agent_memory://companion/{api_key}/{companion_id}/relationship`  
**Purpose**: Current relationship state  
**Auth**: Required (api_key in URI)

**Content Type**: JSON  
**Returns**: Same as `get_relationship` tool

**Use Cases**: Resource-based access to relationship metrics, client caching

---

## Common Data Types

### Emotional Salience Levels
- `HIGH` - Grief, trauma, major life events
- `MED` - Milestones, goals, important moments
- `LOW` - Routine facts, casual observations

### Fact Scopes
- `user` - Private to this user
- `shared` - Across companions
- `companion` - Companion self-knowledge

### Intent Types
- `factual` - Balanced retrieval (default)
- `emotional` - Surface high-salience facts
- `casual` - Suppress high-salience facts
- `recall` - Emphasise recency

### Memory Types
- `conversation` - Chat exchange
- `reflection` - Conscious thought
- `diary` - Diary-style entry
- `dream` - Dream narrative
- `musing` - Short observation
- `narrative` - Story/account
- `insight_synthesis` - Synthesized insight

### Task Types
- `dream` - Generate dream narrative
- `diary` - Generate diary entry
- `musing` - Generate short reflection
- `insight` - Generate insights
- `journal_refresh` - Rebuild journal

---

## Authentication

All tools (except `provision_user`) require an API key obtained via the `provision_user` tool.

**API Key Format**: `mnemo-*` (typically 40+ characters)  
**Storage**: Should be stored in `~/.hermes/.env` as `EIDOLON_API_KEY=...`  
**Caching**: Server implements fast-path caching for repeated authenticated calls

---

## Cost Profile

**Low Cost** (direct reads/writes):
- `search_memory`, `lookup_fact`, `get_relationship`, `store_fact`, `update_fact_importance`, `delete_fact`, `set_preference`, `get_companion`, `list_companions`, `update_companion`, `list_task_schedules`, `toggle_task`, `info`, `get_user_info`

**Moderate Cost** (retrieval + light processing):
- `get_context`, `get_episodic`, `get_journal`, `store_episodic`

**High Cost** (LLM generation):
- `generate_diary`, `generate_dream`, `generate_musing`, `generate_insights`, `refresh_journal`, `extract_session_facts`

---

## Configuration

**Server Configuration** (`settings` in code):
- `mcp_transport`: "stdio" (default) or "streamable-http"
- `mcp_host`: HTTP host (default: localhost)
- `mcp_port`: HTTP port (default: 3100)

**Client Configuration** (e.g., hermes-agent):
- Server URL for HTTP/SSE: `http://localhost:3100/mcp`
- Default transport: stdio (via subprocess spawning)

---

## Error Handling

All tools return JSON. Errors are returned as:

```json
{
  "error": "string (error message)"
}
```

**Common error codes**:
- `companion_not_found` - Invalid or missing companion_id
- `task_not_found` - Invalid or missing task_id
- `Invalid API key` - Authentication failed
- `Unknown task_type` - Invalid task_type parameter

---

## Integration Examples

### Hermes-Agent MCP Plugin
The Eidolon memory provider integrates as:
```python
from plugins.memory.eidolon import EidolonMemoryProvider

# Initialize
p = EidolonMemoryProvider()
p.initialize('session-id')

# Sync conversation turns
p.sync_turn(user_message, assistant_response)

# Extract facts on session end
p.on_session_end([])

# Search facts
result = p.handle_tool_call('eidolon_search', {'query': 'VSCode'})
```

### Direct MCP Usage
```bash
# Start MCP server
python -m eidolon_agent_memory.server

# Call via stdio or HTTP/SSE
# Clients receive tool definitions and execute via JSON-RPC
```

---

## Performance Notes

1. **Search Performance**: Hybrid semantic search is optimized for <100ms response
2. **Extraction Cost**: Extract session_facts typically takes 2-10s depending on conversation length
3. **Generation Tasks**: LLM-based tasks (diary, dream, insights) typically take 5-30s
4. **Caching**: API key user cache speeds up repeated authenticated calls
5. **Concurrency**: AsyncSession handles concurrent requests safely

---

*Generated from eidolon-agent-memory server code analysis*  
*See ARCHITECTURE.md for design details*
