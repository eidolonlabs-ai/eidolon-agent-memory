# Eidolon Agent Memory - Quick Reference

## Tool Summary Table

| Tool Name | Category | Purpose | Auth | Cost | Use Case |
|-----------|----------|---------|------|------|----------|
| **search_memory** | Memory Read | Hybrid semantic search | ✓ | Low | Recalling facts for responses |
| **get_context** | Memory Read | Build context blocks | ✓ | Moderate | Session startup, response prep |
| **lookup_fact** | Memory Read | Direct S-P-O lookup | ✓ | Low | Specific fact queries |
| **get_relationship** | Memory Read | User-companion relationship | ✓ | Low | Tone calibration |
| **get_episodic** | Memory Read | Search conversations/dreams/diary | ✓ | Moderate | Event recall, history search |
| **get_journal** | Memory Read | Fetch companion journal | ✓ | Moderate | Session startup (sparingly) |
| **store_fact** | Memory Write | Manual fact storage | ✓ | Low | User-provided facts |
| **store_episodic** | Memory Write | Store conversations/reflections | ✓ | Low-Moderate | Conversation logging |
| **update_fact_importance** | Memory Write | Update fact priority | ✓ | Low | User corrections |
| **delete_fact** | Memory Write | Permanent deletion | ✓ | Low | User forget requests |
| **set_preference** | Memory Write | Store user preferences | ✓ | Low | Preferences, tone, timezone |
| **generate_diary** | Cognitive | Diary entry generation | ✓ | HIGH | Daily reflection task |
| **generate_dream** | Cognitive | Dream narrative generation | ✓ | HIGH | Morning proactive content |
| **generate_musing** | Cognitive | Short reflection generation | ✓ | MODERATE | Idle-time engagement |
| **generate_insights** | Cognitive | Psychological insight analysis | ✓ | HIGH | Weekly synthesis (>20 facts) |
| **refresh_journal** | Cognitive | Journal rebuild | ✓ | HIGH | After major memory changes |
| **extract_session_facts** | Cognitive | Extract facts from conversation | ✓ | HIGH | Post-session ingestion |
| **create_companion** | Companion | Create companion profile | ✓ | Low | First-time setup |
| **get_companion** | Companion | Fetch companion config | ✓ | Low | Profile loading |
| **list_companions** | Companion | List user's companions | ✓ | Low | Companion selection |
| **update_companion** | Companion | Update companion profile | ✓ | Low | Profile refinement |
| **set_task_schedule** | Scheduler | Create scheduled task | ✓ | Low | Daily/weekly tasks |
| **list_task_schedules** | Scheduler | List scheduled tasks | ✓ | Low | Task management |
| **toggle_task** | Scheduler | Enable/disable task | ✓ | Low | Task lifecycle |
| **run_task_now** | Scheduler | Execute task immediately | ✓ | HIGH | On-demand reflection |
| **info** | Utility | System diagnostics | ✓ | Low | Health check |
| **provision_user** | Utility | Create user & get API key | ✗ | Low | First-time registration |
| **update_user_name** | Utility | Update user name | ✓ | Low | Profile customization |
| **get_user_info** | Utility | Fetch user profile | ✓ | Low | Profile verification |

## Tool Categories at a Glance

### Memory Read (6 tools)
Retrieval operations - read-only, low-moderate cost
- **search_memory**: Semantic search across facts with intent filtering (factual/emotional/casual/recall)
- **get_context**: Formatted context block for response generation
- **lookup_fact**: Direct triple-based lookup (subject + predicate)
- **get_relationship**: Relationship metrics (trust, closeness, milestones)
- **get_episodic**: Search conversations, diary, dreams, reflections
- **get_journal**: Current journal with top insights

### Memory Write (5 tools)
Persistence operations - write facts, preferences, updates
- **store_fact**: Manual fact storage (subject-predicate-object + metadata)
- **store_episodic**: Store conversations, reflections, diary entries
- **update_fact_importance**: Adjust fact priority/confidence
- **delete_fact**: Permanent deletion (user forget)
- **set_preference**: Store user preferences (timezone, tone, language, etc.)

### Cognitive Generation (6 tools)
LLM-powered synthesis and generation - high cost
- **generate_diary**: Diary entry from companion perspective
- **generate_dream**: Surreal narrative about user
- **generate_musing**: Short spontaneous reflection
- **generate_insights**: Psychological/behavioral insights from facts
- **refresh_journal**: Rebuild evolving companion journal
- **extract_session_facts**: Extract structured facts from conversation

### Companion Management (4 tools)
Companion profile CRUD operations
- **create_companion**: New companion setup
- **get_companion**: Fetch companion details
- **list_companions**: List user's companions
- **update_companion**: Update persona/pronouns/traits

### Scheduler (4 tools)
Autonomous task management
- **set_task_schedule**: Create cron-scheduled task (dream/diary/musing/insight/journal_refresh)
- **list_task_schedules**: View all scheduled tasks
- **toggle_task**: Enable/disable task
- **run_task_now**: Execute task immediately

### Utility (4 tools)
System operations and user management
- **info**: System diagnostics (version, fact counts, capabilities)
- **provision_user**: Register new user (returns API key)
- **update_user_name**: Update user display name
- **get_user_info**: Get user profile

---

## Common Workflow Patterns

### Conversation Session

```
1. list_companions() 
   → select companion_id

2. get_context(query="how am I doing?", intent="factual")
   → load relevant facts for response generation

3. [LLM generates response]

4. store_episodic(text="user: ..., assistant: ...", memory_type="conversation")
   → log the exchange

5. [After session ends]

6. extract_session_facts(conversation_text="full session transcript")
   → automatically extract & store facts
```

### Autonomous Background Tasks

```
1. set_task_schedule(task_type="diary", schedule="0 9 * * *", timezone="UTC")
   → schedule daily 9 AM diary generation

2. [Cron executor calls run_task_now("diary")]

3. [Result stored as episodic memory]

4. [Companion can mention diary entry in next conversation]
```

### User Preference Management

```
1. set_preference(key="language", value="en")
   → store language preference

2. set_preference(key="tone", value="casual_friendly")
   → store communication tone

3. [Later retrieval can filter results based on preferences]
```

### Fact Lifecycle

```
1. store_fact(subject="Alice", predicate="WORKS_AS", obj="engineer")
   → user tells you something

2. [Later] get_context(query="work")
   → fact retrieved in context

3. [User correction] update_fact_importance(edge_id=X, importance=0.8)
   → user clarifies importance

4. [User asks to forget] delete_fact(edge_id=X)
   → permanently removed
```

---

## Intent Parameter Guide

Used in `search_memory`, `get_context`, `get_episodic`

| Intent | Behavior | When to Use |
|--------|----------|------------|
| `factual` | Balanced retrieval | Default for most lookups |
| `emotional` | Boost HIGH-salience facts | When user discusses difficult emotions |
| `casual` | Suppress HIGH-salience facts | For lighthearted/fun messages |
| `recall` | Emphasize recency | "What's been happening lately?" queries |

---

## Emotional Salience Guide

Used in `store_fact` and filtering

| Level | Examples | When to Use |
|-------|----------|------------|
| `HIGH` | Grief, trauma, major life events | Significant emotional weight |
| `MED` | Milestones, goals, important moments | Medium importance |
| `LOW` | Routine facts, casual observations | Default for most facts |

---

## Memory Type Reference

Used in `store_episodic`, `get_episodic`

| Type | Purpose | Example |
|------|---------|---------|
| `conversation` | Chat exchange | User message + assistant response |
| `reflection` | Conscious thought | User's own reflection |
| `diary` | Diary-style entry | Companion reflecting on interactions |
| `dream` | Dream narrative | Surreal story about user |
| `musing` | Short observation | One-liner thought |
| `narrative` | Story/account | Narrative account of events |
| `insight_synthesis` | Synthesized insight | Psychological insight from analysis |

---

## Cost Analysis

### Batch Operation Economics

**Low-cost batch** (10 ops = ~milliseconds):
```
list_companions()
lookup_fact() × 5
get_user_info()
```

**Moderate-cost batch** (3 ops = ~500ms-2s):
```
get_context()
get_episodic(limit=10)
get_journal()
```

**High-cost batch** (1-2 ops = ~5-30s, LLM required):
```
generate_diary()
extract_session_facts()
generate_insights()
```

**Never batch high-cost operations** - queue them separately.

---

## Authentication Checklist

- [ ] Call `provision_user()` once per new user (no auth required)
- [ ] Store returned `api_key` securely (NOT retrievable afterward)
- [ ] Include `api_key` in all other tool calls
- [ ] Store in environment: `EIDOLON_API_KEY=...` in `~/.hermes/.env`
- [ ] Verify with `info()` - if successful, auth is working

---

## Scope Parameter Guide

Used in `store_fact`

| Scope | Visibility | Use Case |
|-------|------------|----------|
| `user` (default) | Private to this user | Personal facts, preferences |
| `shared` | Visible across companions | Shared user facts |
| `companion` | Companion self-knowledge | Things companion knows about itself |

---

## Error Responses

All tools return JSON. Errors follow pattern:

```json
{
  "error": "string describing problem"
}
```

**Common errors**:
- `"Invalid API key"` - Authentication failed
- `"companion_not_found"` - Invalid companion_id
- `"task_not_found"` - Invalid task_id
- `"Unknown task_type"` - Invalid task_type for scheduler

---

## Performance Tips

1. **Batch reads together**: Multiple `search_memory()` or `lookup_fact()` calls OK
2. **Serialize generations**: Only one LLM task per minute recommended
3. **Cache companions**: Call `list_companions()` once per session
4. **Defer extraction**: `extract_session_facts()` should run async after session
5. **Use intent filtering**: Reduces irrelevant results in `search_memory()`
6. **Limit episodic results**: Default 5 results usually sufficient; adjust if needed

---

## Integration with Hermes-Agent

```python
# In hermes-agent plugin system
from plugins.memory.eidolon import EidolonMemoryProvider

provider = EidolonMemoryProvider()
provider.initialize(session_id)

# Each turn
provider.sync_turn(user_msg, assistant_response)

# At session end
provider.on_session_end([])

# Fact retrieval (injected into system prompt)
facts = provider.get_prefetched_facts()
```

---

## Server Configuration

Start the MCP server:

```bash
python -m eidolon_agent_memory.server
```

**Environment variables**:
- `MCP_TRANSPORT`: "stdio" (default) or "streamable-http"
- `MCP_HOST`: HTTP host (default: localhost)
- `MCP_PORT`: HTTP port (default: 3100)

**Clients connect via**:
- stdio: subprocess spawn
- HTTP/SSE: `http://localhost:3100/mcp`

---

*Quick reference for 27 MCP tools across 6 categories*  
*Full documentation: see MCP_TOOLS_REFERENCE.md*
