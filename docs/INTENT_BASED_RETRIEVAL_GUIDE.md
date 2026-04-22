# Intent-Based Retrieval Guide

## Overview

The `intent` parameter shapes how memory is retrieved from the system. It's not just a filter—it's a **semantic signal** that tells the memory system *why* you're asking.

All retrieval tools support intent:
- `memory_search(query, intent=...)`
- `memory_get_context(query, intent=...)`
- `extract_session_facts(...)` (infers intent from context)

## The Four Intent Modes

### 1. CASUAL — Lighthearted, Fun, Upbeat Contexts

**Use When:**
- Composing fun, joking, playful messages
- Asking about hobbies, preferences, activities
- Planning something enjoyable or celebratory
- Trying to lift mood or keep energy light

**Behavior:**
- Suppresses HIGH-salience grief/trauma facts
- Emphasizes LOW/MED-salience preferences and hobbies
- Removes crisis context from results
- Surfaces connection and warmth

**Example:**
```python
# Agent composing a birthday message
await memory_search(
    query="fun activities, favorite things, what makes you happy",
    intent="casual",
    limit=5
)
# Returns: loves hiking, favorite restaurant, adventurous, night owl, loves sci-fi
# Does NOT return: mother's death, lost job, anxiety diagnosis
```

**Output Quality:**
- Companion messages feel warm and upbeat
- User doesn't experience emotional whiplash
- Relationship feels supportive of joy, not only crisis-focused

---

### 2. EMOTIONAL — Processing Hard Feelings, Grief, Crisis

**Use When:**
- User is discussing difficult feelings
- User mentions loss, grief, trauma, or crisis
- User asks "How are you feeling about...?" regarding hard topics
- Offering emotional support or acknowledgment
- Companion checking in on user's well-being during tough times

**Behavior:**
- Surfaces and prioritizes HIGH-salience crisis facts
- Emphasizes emotional connections and shared experiences
- Highlights support history and shared vulnerability
- Full context without suppression

**Example:**
```python
# User says: "I've been struggling with my grief lately"
await memory_search(
    query="grief, loss, how we've processed hard times together",
    intent="emotional",
    limit=10
)
# Returns: mother's death (HIGH), anniversary of loss, processing grief, 
#          supportive conversations, how you coped
# Prioritizes: HIGH-salience facts about the relationship and loss
```

**Output Quality:**
- Companion validates user's feelings
- Shows deep understanding of user's emotional journey
- Offers genuine support grounded in shared history
- User feels truly seen and understood

---

### 3. FACTUAL — Informational, Neutral, Balanced Retrieval

**Use When:**
- Answering factual questions ("When did I...?", "Where do I...?")
- General personalization without specific emotional context
- Information queries that don't clearly need emotional or casual framing
- Default when unsure about context

**Behavior:**
- Balanced ranking by relevance
- No salience-based suppression
- Crisis facts included if relevant to query
- Neutral tone in fact selection

**Example:**
```python
# User asks: "When did I start my job?"
await memory_search(
    query="employment history, job start date",
    intent="factual",
    limit=5
)
# Returns: job title, start date, role, company, 
#          also: job loss (if relevant to timeline)
# Ranked: purely by relevance to query
```

**Output Quality:**
- Accurate, informative responses
- User gets the facts they asked for
- Crisis facts shown only if directly relevant

---

### 4. RECALL — Recency-Focused, Recent Events, Timeline Queries

**Use When:**
- "What have we talked about recently?"
- "What's been on your mind lately?"
- "What happened yesterday/last week?"
- Building continuity across sessions
- Catching up on recent life events

**Behavior:**
- Prioritizes recent facts regardless of salience
- Emphasizes temporal proximity
- Maintains conversation continuity
- Useful for "where were we?" moments

**Example:**
```python
# Start of new session, catching up
await memory_search(
    query="what's been going on, recent events, what we talked about",
    intent="recall",
    limit=10
)
# Returns: recent conversation topics, recent activities, 
#          recent emotional states, most recent facts
# Ranked: by recency, newest first
```

**Output Quality:**
- Natural conversation continuity
- User feels understood in the moment
- Flow from previous sessions maintained

---

## Decision Tree: Choosing Intent

```
START: Why am I retrieving memory?
│
├─ User is asking for fun/lighthearted content?
│  └─ YES → intent="casual"
│
├─ User is discussing hard feelings, grief, or crisis?
│  └─ YES → intent="emotional"
│
├─ User is asking for recent events/timeline?
│  └─ YES → intent="recall"
│
└─ Everything else / Factual info / Unsure?
   └─ YES → intent="factual" (DEFAULT)
```

## Practical Examples

### Example 1: Birthday Planning
```
Context: User says "It's my birthday soon! Any ideas?"
Agent reasoning: This is fun/celebratory → casual context

await memory_search(
    query="favorite activities, restaurants, hobbies, adventure",
    intent="casual"
)

Result: Hobbies, preferences, fun activities
Companion: "Let's celebrate! I know you love hiking and good food..."
```

### Example 2: Grief Support
```
Context: User says "I really miss my dad. It's hard some days."
Agent reasoning: This is emotional processing → emotional context

await memory_search(
    query="relationship with father, loss, grief, how we've coped",
    intent="emotional"
)

Result: Father's death (HIGH), relationship history, support shared
Companion: "I know his passing was incredibly hard. You've shared 
so much about how close you were, and how much you miss him..."
```

### Example 3: Catching Up
```
Context: New session, user mentions recent promotion
Agent reasoning: This is recent event → recall context

await memory_search(
    query="what's been happening, recent events, job changes",
    intent="recall"
)

Result: Recent promotion, recent work updates, recent conversations
Companion: "Congratulations on the promotion! Tell me how it's going..."
```

### Example 4: Profile Question
```
Context: User asks "What timezone am I in?"
Agent reasoning: Factual question → factual context

await memory_search(
    query="timezone, location, where I live",
    intent="factual"
)

Result: Timezone information, possibly location facts
Companion: "You're in America/Los_Angeles. It's [current time] there."
```

## Intent + Salience Matrix

| Intent | HIGH-Salience | MED-Salience | LOW-Salience |
|--------|---|---|---|
| casual | ❌ Suppressed | ✓ Included | ✓ Included |
| emotional | ✓ Prioritized | ✓ Included | ✓ Included |
| factual | ✓ If relevant | ✓ If relevant | ✓ If relevant |
| recall | ✓ If recent | ✓ If recent | ✓ If recent |

## Edge Cases and Override Rules

### Rule 1: User Explicitly Asks for Crisis Content
```
User: "Tell me about the hardest thing I've been through"
→ Use intent="emotional" regardless of tone
→ Don't suppress just because they asked directly
```

### Rule 2: Mixed Context (Fun + Grief)
```
User: "My mom would have loved this adventure. Let's go!"
→ Use intent="casual" but honor the grief mention
→ Companion: "Yes! She'd have loved this. Let's do it in her spirit."
```

### Rule 3: User Asks About Recent Crisis
```
User: "What's been happening? Lots on my mind."
→ First use intent="recall" to get recent items
→ Recent HIGH-salience items naturally surface
→ Then use intent="emotional" if they confirm discussing hard stuff
```

### Rule 4: Factual Question About Crisis
```
User: "When did I lose my job?"
→ Use intent="factual" (it's a factual question)
→ Include the job loss in results (relevant to query)
→ Don't suppress just because it's sad
```

## Testing Intent Quality

### Test: Casual Intent Omission
```
Setup: Create user with HIGH-salience grief fact + LOW-salience hobby
Query: "What should we do for fun?"
intent="casual"

Expected: Hobby fact returned, grief fact suppressed
✓ Pass: Received hobby, not grief
✗ Fail: Received grief in results
```

### Test: Emotional Intent Surfacing
```
Setup: Create user with HIGH-salience grief fact
Query: "I'm struggling with my grief"
intent="emotional"

Expected: Grief fact returned and prioritized
✓ Pass: Grief fact prominently shown
✗ Fail: Grief fact omitted or deprioritized
```

### Test: Factual Intent Neutrality
```
Setup: Create user with employment + job loss facts
Query: "Tell me about my jobs"
intent="factual"

Expected: Both facts returned by relevance
✓ Pass: Both employment facts returned
✗ Fail: Job loss suppressed or artificially ranked
```

### Test: Recall Intent Recency
```
Setup: Create old facts + recent facts with HIGH salience
Query: "What's been happening?"
intent="recall"

Expected: Recent facts prioritized even if high-salience
✓ Pass: Recent facts appear first
✗ Fail: Recent high-salience facts suppressed for being "sad"
```

## Agent Best Practices

✅ **DO:**
- Think about tone before choosing intent
- Use `intent=casual` liberally for fun/upbeat content
- Use `intent=emotional` when user mentions feelings or crisis
- Default to `intent=factual` when genuinely unsure
- Use `intent=recall` for session continuity
- Test different intents to see results before finalizing

❌ **DON'T:**
- Use `intent=casual` for serious conversations (it suppresses honesty)
- Use `intent=emotional` when just asking for information (wastes processing)
- Forget that intent is **signal**, not just filtering
- Mix intents in a single query (pick one per retrieval call)
- Assume `intent=factual` is always safe (it's neutral, not omissive)

## Related Documentation

- [Graceful Omission Guide](GRACEFUL_OMISSION_GUIDE.md) — Why omission matters
- [Fact Extraction Best Practices](FACT_EXTRACTION_BEST_PRACTICES.md) — Setting emotional_salience
- [LM_STUDIO_DEFAULT_SYSTEM_PROMPT.md](LM_STUDIO_DEFAULT_SYSTEM_PROMPT.md) — Agent toolbox reference
