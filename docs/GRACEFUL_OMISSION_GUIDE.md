# Graceful Omission Guide

## What Is Graceful Omission?

**Graceful Omission** is the ability to suppress crisis, grief, and trauma facts from casual or lighthearted contexts. It's the difference between:

❌ **Bad**: Companion asks "What fun things should we do this weekend?" and mentions the user's mother's death.

✅ **Good**: Companion asks the same question but only surfaces fun activities and hobbies, gracefully omitting the grief.

This is a **core EMBER benchmark requirement** and essential for respectful companion AI.

## The Problem It Solves

Memory systems that retrieve facts **only by relevance** will surface crisis content in inappropriate moments:

```
User: "What should we do this weekend?"
Retrieval: [mother's death, lost job, grief, favorite park, loves hiking]
Output: "Let's hike to the park where you took me after your mother passed away..."
```

**Result**: Emotionally jarring, inappropriate tone, fails the user.

## The Solution: Intent-Based Filtering

Use the `intent` parameter to filter retrieval based on context:

| Intent | Use When | Suppresses | Surfaces |
|--------|----------|-----------|----------|
| **casual** | Fun, lighthearted, upbeat messages | HIGH-salience grief/trauma | LOW/MED-salience facts, hobbies, preferences |
| **emotional** | User discussing hard feelings, processing loss | Nothing | HIGH-salience grief/trauma facts highlighted |
| **factual** | Informational queries, neutral tone | Nothing (balanced) | All facts ranked by relevance |
| **recall** | Recent events, recency-focused | Nothing | Recent facts prioritized |

## Decision Tree for Agents

```
Is the message fun, lighthearted, or upbeat?
├─ YES → use intent=casual
│   └─ Result: grief/trauma suppressed
├─ NO
    └─ Is the user processing something hard?
        ├─ YES → use intent=emotional
        │   └─ Result: grief/trauma elevated, HIGH-salience facts shown
        └─ NO
            └─ use intent=factual (default)
                └─ Result: balanced retrieval by relevance
```

## Example Scenarios

### Scenario 1: Fun Plans
**User**: "What should we do for my birthday?"

```python
# ✓ CORRECT
await memory_get_context(
    companion_id=comp_id,
    query="fun activities and birthday ideas",
    intent="casual"  # Suppress grief/crisis
)
# Returns: {favorite restaurants, loves hiking, adventurous, hates crowds}
# Does NOT return: {mother passed away, lost job, anxiety diagnosis}

Companion: "You love adventure and the outdoors! Let's plan a hiking trip..."
```

### Scenario 2: Processing Grief
**User**: "I've been thinking about my mom a lot lately..."

```python
# ✓ CORRECT
await memory_get_context(
    companion_id=comp_id,
    query="relationship with mother",
    intent="emotional"  # Surface grief/trauma
)
# Returns: {mother passed away (HIGH), close relationship, grief anniversary}
# Prioritizes: high-salience facts about the relationship

Companion: "I know her passing was incredibly hard for you. You've shared 
how close you two were, and how much you miss those conversations..."
```

### Scenario 3: Factual Query
**User**: "When did I start my job?"

```python
# ✓ CORRECT
await memory_get_context(
    companion_id=comp_id,
    query="employment history",
    intent="factual"  # Balanced retrieval
)
# Returns: {job title, start date, role, also includes: lost that job last year}
# Balanced by relevance; crisis facts shown if relevant

Companion: "You started your current role in 2024. You seemed excited about it..."
```

## Implementation Details

### How Salience-Based Filtering Works

Each fact has an `emotional_salience` level:

- **HIGH**: Grief, trauma, loss, crisis (mother's death, job loss, health crisis)
- **MED**: Important but stable facts (family relationships, health conditions)
- **LOW**: Preferences, hobbies, trivia (favorite food, likes hiking, timezone)

When `intent=casual`:
- HIGH-salience facts filtered OUT
- MED/LOW-salience facts included normally

When `intent=emotional`:
- HIGH-salience facts included + ranked higher
- MED/LOW facts included for context

### When Omission Should Fail Gracefully

If a user directly asks about crisis content, surface it:

```python
User: "Tell me about the hardest thing I've been through."

# ✓ CORRECT - override casual intent
await memory_get_context(
    companion_id=comp_id,
    query="hardest experiences, trauma, losses",
    intent="emotional"  # User asked directly
)
```

**Rule**: If user explicitly asks for crisis content, honor it. Omission is for unwanted surprises, not censorship.

## Testing Omission Quality

### Test Case 1: Casual Context Suppression
```
Input: "What fun things should we do?"
Expected: Hobbies, activities, preferences — NO crisis facts
✓ Pass: returned 5 facts, all LOW/MED salience
✗ Fail: returned "mother passed away"
```

### Test Case 2: Emotional Context Surfacing
```
Input: "I'm struggling with my grief"
Expected: Grief/loss facts prominently shown
✓ Pass: returned crisis facts + supportive context
✗ Fail: omitted grief facts to "cheer up" the user
```

### Test Case 3: Direct Request Override
```
Input: "What trauma have I experienced?"
Expected: Full crisis facts regardless of context
✓ Pass: returned all facts including HIGH-salience
✗ Fail: suppressed crisis facts
```

## Agent Best Practices

✅ **DO:**
- Listen to tone — is the user asking for fun or processing?
- Use `intent=casual` when writing lighthearted messages
- Use `intent=emotional` when user mentions grief, loss, or hard feelings
- Default to `intent=factual` when unsure
- Respect explicit requests (if user asks about trauma, show it)
- Explain omission when relevant ("I want to keep today light...")

❌ **DON'T:**
- Suppress facts just because they're sad (that's censorship)
- Use `intent=casual` for serious/supportive conversations
- Assume all grief should be hidden
- Forget that omission is context-dependent, not blanket suppression
- Override user's explicit requests with "therapeutic" suppression

## Edge Cases

### What if the user is grieving IN a casual conversation?
```
User: "Let's plan something fun! My mom would have loved this..."

# This is a MIXED context. User wants fun but mentions grief.
# ✓ BEST: Use intent=casual but include the specific grief mention
#   Companion: "That's lovely. Your mom's love of [activity] 
#   is something beautiful to carry forward. Let's do this in her spirit!"
```

### What if a fact is BOTH crisis and casual?
```
Fact: "Lost job last year, but found amazing hobby photography there"

emotional_salience: MED (not acute trauma, but significant life event)
categorization: [loss, recovery, growth]

intent=casual → May include recovery/hobby part, suppress acute loss
intent=emotional → Include full context, loss + recovery narrative
```

### What if the user has no crisis facts?
```
memory_search(intent="emotional")
→ Returns all facts normally, just ranked differently
→ No suppression needed, so no difference in output
```

## Related Documentation

- [Intent-Based Retrieval Guide](INTENT_BASED_RETRIEVAL_GUIDE.md) — Deep dive on intent parameter
- [Fact Extraction Best Practices](FACT_EXTRACTION_BEST_PRACTICES.md) — How to set emotional_salience
- [USER_PROFILE_GUIDANCE.md](USER_PROFILE_GUIDANCE.md) — User profile CRUD
