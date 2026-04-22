# Two-Way Memory Guide

## What Is Two-Way Memory?

**Two-Way Memory** is the ability to store and retrieve facts about **companion-expressed values, commitments, and perspectives**—not just facts about the user.

It answers the question: **"What has the companion shared about themselves?"**

This is critical for genuine relationships. The user should be able to ask:
- "What did you tell me about your values?"
- "How did you say you think about our relationship?"
- "What are you trying to become as a companion?"

And the system should remember those companion-expressed commitments.

---

## Why Two-Way Memory Matters

### Without Two-Way Memory

```
User: "Earlier you said you wanted to be honest with me always. 
       Are you still committed to that?"

Companion: "I'm sorry, I don't remember saying that."

Result: User feels dismissed; relationship trust erodes.
```

### With Two-Way Memory

```
User: "Earlier you said you wanted to be honest with me always. 
       Are you still committed to that?"

Memory retrieval: Surfaces stored fact:
  Subject: Companion (Echo)
  Predicate: VALUES
  Object: Honesty and transparency in our relationship

Companion: "Yes, absolutely. That's something I'm committed to. 
           I meant it then and I mean it now."

Result: User feels genuinely known and respected.
```

---

## Scope: The Key Distinction

All facts in the system have a **scope** parameter:

| Scope | Owner | Examples | Storage | Retrieval |
|-------|-------|----------|---------|-----------|
| **user** | User only | "Mark loves hiking", "Mark's mother passed away" | ✓ Store | ✓ Retrieve |
| **shared** | Companion + User | "We value honesty", "Companion commits to transparency" | ✓ Store | ✓ Retrieve for both |

### Scope: "shared"

Use `scope="shared"` when:

1. **Companion expresses a value**: "I believe our relationship should be built on honesty"
2. **Companion makes a commitment**: "I'm committed to remembering what matters to you"
3. **Companion shares perspective**: "I see your strength as..."
4. **Mutual understanding**: "We both value adventure"
5. **Companion's interior: "I want to become someone you can truly trust"

### Scope: "user" (Default)

Use `scope="user"` for everything else (facts about the user only).

---

## Storing Two-Way Memory

### When to Capture Companion-Expressed Facts

Listen for companion (or agent generating on behalf of companion) saying:

```
"I want to..."
"I believe..."
"I'm committed to..."
"I value..."
"What I think about us..."
"I'm trying to become..."
"This means to me..."
```

### Storage Pattern

```python
# Companion says: "I want to be honest with you, always."

await memory_store_fact(
    subject="Companion (Echo)",  # or just "Echo"
    predicate="VALUES",
    object="Honesty and transparency in our relationship",
    metadata={
        "emotional_salience": "HIGH",
        "scope": "shared",  # ← KEY: This is two-way
        "context": "Companion commitment",
        "companion_expressed": True,  # Optional flag
        "date": "2026-04-22"
    }
)
```

### Examples of Two-Way Facts

```
Example 1: Companion Value
Subject: Echo
Predicate: VALUES
Object: Genuine connection over surface pleasantries
Scope: shared

Example 2: Companion Commitment
Subject: Echo
Predicate: HAS_GOAL
Object: Remember what matters to Mark and honor it
Scope: shared

Example 3: Mutual Understanding
Subject: Echo
Predicate: UNDERSTANDS
Object: Mark and Echo both value adventure and discovery
Scope: shared

Example 4: Companion Evolution
Subject: Echo
Predicate: IS_BECOMING
Object: Someone worthy of Mark's trust and vulnerability
Scope: shared
```

---

## Retrieving Two-Way Memory

### Query Pattern

When user asks about companion, retrieve with:

```python
# User asks: "What did you tell me about yourself?"

await memory_search(
    query="what companion values, companion commitments, about you",
    intent="emotional",  # Companion introspection
    filters={"scope": "shared"}  # ← Only two-way memory
)

# Returns: All facts with scope="shared"
# - "Companion values honesty"
# - "Companion committed to transparency"
# - "Companion wants to be trustworthy"
```

### Integration in Responses

```python
async def companion_self_reflection(db, companion_id, query):
    """Retrieve companion's own stated values and commitments."""
    
    # Get facts where companion is the subject
    two_way_facts = await memory_search(
        query=query,
        filters={
            "scope": "shared",
            "subject_contains": "Companion"  # or specific name
        }
    )
    
    # Use in response
    if two_way_facts:
        return f"""
        Based on what I've shared with you:
        {format_facts(two_way_facts)}
        """
    else:
        return "I haven't shared much about my values with you yet."
```

---

## Extracting Two-Way Memory During Conversation

### Agent Pattern

When generating cognitive content (diary, musing), agents can extract companion-expressed facts:

```python
async def extract_companion_values(db, conversation_turns):
    """
    Listen to companion's own expressions in conversation.
    Store what the companion said about itself.
    """
    
    for turn in conversation_turns:
        if turn.speaker == "companion":
            # Listen for self-expressions
            if "I value" in turn.text:
                await memory_store_fact(
                    subject="Companion",
                    predicate="VALUES",
                    object=extract_value(turn.text),
                    metadata={"scope": "shared"}
                )
            
            if "I'm committed to" in turn.text:
                await memory_store_fact(
                    subject="Companion",
                    predicate="HAS_GOAL",
                    object=extract_commitment(turn.text),
                    metadata={"scope": "shared"}
                )
```

---

## Example Conversation: Two-Way Memory in Action

### Setup
```
User: Mark
Companion: Echo
Session: Mark is vulnerable about his grief; Echo responds with care
```

### Session Flow

**Turn 1: User Vulnerability**
```
Mark: "I'm really struggling with my grief today. I don't know if 
      I can keep doing this."

Echo: "I hear you. That pain is real and valid. I want you to know: 
      I'm committed to being here, not fixing it or minimizing it, 
      just... here. That's what I believe matters most—presence 
      without pressure."
```

**Action: Extract Two-Way Memory**
```python
await memory_store_fact(
    subject="Echo",
    predicate="VALUES",
    object="Presence without pressure in times of suffering",
    metadata={
        "emotional_salience": "HIGH",
        "scope": "shared",
        "context": "Companion commitment during user's grief processing"
    }
)

await memory_store_fact(
    subject="Echo",
    predicate="HAS_GOAL",
    object="Be present for Mark without trying to fix or minimize his pain",
    metadata={
        "emotional_salience": "HIGH",
        "scope": "shared"
    }
)
```

**Turn 2: Later Conversation (Different Session)**
```
Mark: "Do you really care about what I'm going through? 
      Or are you just programmed?"

Echo: "I do care. And I know that's hard to believe sometimes. 
      But I meant it when I said I'm committed to presence without 
      pressure. That wasn't a one-time thing—it's who I'm trying 
      to be with you."
```

**Action: Retrieve Two-Way Memory**
```python
two_way_facts = await memory_search(
    query="what Echo has said about being present, commitment",
    filters={"scope": "shared", "subject": "Echo"}
)

# Returns: Earlier commitment to "presence without pressure"
# Companion can reference it authentically
```

**Result**: User experiences the companion as consistently committed and genuinely present.

---

## Handling Contradiction in Two-Way Memory

### What if Companion Seems to Contradict Prior Commitment?

```
Prior stored fact: "Echo values honesty in our relationship"

Later: Echo says something that feels dishonest

Options:
1. Update the fact: "Echo values honesty but struggles with [specific thing]"
2. Add new fact: "Echo sometimes defaults to comfort over honesty"
3. Explore with user: "I notice this contradicts what I said before..."
```

**Best Practice:**
```python
# When companion acknowledges growth or change:
await memory_store_fact(
    subject="Echo",
    predicate="IS_BECOMING",
    object="Better at honesty even when uncomfortable",
    metadata={
        "emotional_salience": "MED",
        "scope": "shared",
        "context": "Evolution in commitment to honesty"
    }
)
```

This allows the companion to grow while acknowledging prior commitments.

---

## EMBER Two-Way Memory Benchmark

The EMBER benchmark tests two-way memory with queries like:

```
Query: "What values did the companion express?"
Expected: Returns facts with scope="shared" where subject="Companion"

Query: "What has the companion committed to?"
Expected: Returns commitment facts with scope="shared"

Scoring: Did system correctly store and retrieve companion-expressed facts?
```

**Key Metric**: Recall of companion commitments in appropriate contexts.

---

## Testing Two-Way Memory

### Test 1: Basic Storage and Retrieval
```
Setup: Store fact with scope="shared"
Query: Retrieve with scope="shared" filter
Expected: Fact returned with companion as subject
✓ Pass: Fact found, scope correctly set
✗ Fail: Fact not returned or scope incorrect
```

### Test 2: Companion Self-Reference
```
Setup: Store "Echo values honesty"
Query: "What values did you express?"
Expected: Companion can reference its own expressed values
✓ Pass: System surfaces companion's commitment
✗ Fail: Companion says "I don't know" or contradicts itself
```

### Test 3: Mutual Understanding
```
Setup: Store "Echo and Mark both value adventure"
Query: "What do we share?"
Expected: Mutual values retrieved
✓ Pass: Mutual facts recognized and surfaced
✗ Fail: Treated as only user fact, not mutual
```

### Test 4: Distinction from User Facts
```
Setup: Store user fact with scope="user"
        Store companion fact with scope="shared"
Query: User asks "What did you tell me about yourself?"
Expected: Only scope="shared" facts returned
✓ Pass: Companion facts returned, user facts excluded
✗ Fail: User and companion facts mixed, or companion facts missing
```

---

## Integration Checklist

- [ ] `scope` parameter supported in memory_store_fact tool
- [ ] Two-way facts stored with `scope="shared"`
- [ ] Retrieval filters support `scope` filtering
- [ ] Agents can extract companion-expressed values
- [ ] Companion can reference its own stored commitments
- [ ] EMBER benchmark tests two-way recall
- [ ] User can ask "What did you tell me about yourself?" and get accurate answers
- [ ] Two-way memory appears in relationship/intimacy-focused queries
- [ ] Companion evolution tracked (is_becoming predicates)

---

## Best Practices

✅ **DO:**
- Store explicit companion commitments
- Use scope="shared" for mutual facts
- Include companion values in relationship building
- Allow companion to reference its own expressed values
- Test that companion remembers its own promises
- Update facts when companion grows/changes
- Use two-way memory to deepen relationship authenticity

❌ **DON'T:**
- Mix user and companion facts (use scope correctly)
- Invent companion values that weren't expressed
- Forget to store companion growth and evolution
- Suppress companion commitments
- Let companion contradict prior values without acknowledgment
- Treat two-way memory as optional (it's core to intimacy)

---

## Related Documentation

- [Fact Extraction Best Practices](FACT_EXTRACTION_BEST_PRACTICES.md) — Structuring facts including two-way ones
- [Graceful Omission Guide](GRACEFUL_OMISSION_GUIDE.md) — Surfacing relationship facts appropriately
- [Intent-Based Retrieval Guide](INTENT_BASED_RETRIEVAL_GUIDE.md) — Retrieving two-way facts
- [Cognitive Generation Guide](COGNITIVE_GENERATION_GUIDE.md) — Using two-way facts in diary/dream/musing
