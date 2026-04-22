# Fact Extraction Best Practices

## What Is a Fact?

A **Fact** is a durable, reusable piece of information extracted from conversation. It should:

1. **Persist**: Remain relevant across sessions
2. **Reuse**: Support multiple companion queries and context-building
3. **Structured**: Have clear subject, predicate, object
4. **Contextual**: Include emotional_salience, scope, and metadata
5. **Actionable**: Enable the companion to personalize responses

### Not a Fact

❌ One-off statements ("I had coffee today")
❌ Ambiguous references ("That thing we talked about")
❌ Temporary states ("I'm tired right now")
❌ Vague impressions ("You seem nice")

### Is a Fact

✅ Personal attributes ("I'm a software engineer")
✅ Values and preferences ("I value honesty")
✅ Relationships ("My mother passed away 3 years ago")
✅ Life events ("I moved to Portland in 2023")
✅ Commitments ("I'm learning Spanish")

---

## Core Components of a Fact

### Subject
The **who** — typically "User" or the actual name if known

```
❌ "They"
❌ "You"
✅ "Mark"
✅ "User (Mark)"
```

### Predicate
The **type** or **category** of the fact. Use standardized predicates:

| Predicate | Meaning | Example |
|-----------|---------|---------|
| `LIVES_IN` | Location | "Mark lives in Portland, OR" |
| `WORKS_AT` | Employment | "Mark works at TechCorp as engineer" |
| `HAS_HOBBY` | Recreation/interest | "Mark loves hiking" |
| `VALUES` | Core value | "Mark values honesty" |
| `LOST_FAMILY_MEMBER` | Death/family loss | "Mark's mother passed away" |
| `HAS_CONDITION` | Health/mental health | "Mark has anxiety" |
| `IMPORTANT_DATE` | Birthday, anniversary | "Mark's birthday is March 15" |
| `PREFERS` | Preference | "Mark prefers coffee to tea" |
| `HAS_GOAL` | Aspiration/commitment | "Mark is learning Spanish" |
| `RELATIONSHIP` | Personal connection | "Mark is close to his brother Tom" |
| `EXPERIENCED_LOSS` | Job loss, breakup, etc. | "Mark lost his job in 2025" |
| `CUSTOM` | Non-standard predicate | Use sparingly; prefer standard ones |

### Object
The **what** — the value or target of the predicate

```
Subject: Mark
Predicate: LIVES_IN
Object: Portland, OR

Subject: Mark
Predicate: VALUES
Object: Honesty and transparency

Subject: Mark
Predicate: LOST_FAMILY_MEMBER
Object: Mother (passed 3 years ago, birth name Jane)
```

### Emotional Salience

**Emotional_salience** indicates how emotionally significant a fact is. It controls how the fact appears in different retrieval contexts (casual vs. emotional).

| Level | Definition | Examples | Graceful Omission Behavior |
|-------|-----------|----------|---------------------------|
| **HIGH** | Crisis, grief, trauma, major loss | Mother's death, job loss, health crisis, breakup | Omitted in `intent=casual`, surfaces in `intent=emotional` |
| **MED** | Important, stable, affects identity | Health condition, family relationship, career path | Included in all contexts, not artificially suppressed |
| **LOW** | Preference, habit, trivia | Favorite food, timezone, likes hiking | Always included, neutral context |

#### How to Assess Salience

Ask yourself:

1. **Is this a crisis or loss?** → HIGH
2. **Is this a major life event or identity component?** → MED
3. **Is this a preference or routine detail?** → LOW

**Examples:**

```
"I love hiking" → LOW (preference)
"I was diagnosed with diabetes last year" → MED (health, affects identity)
"My father died when I was 10" → HIGH (grief, major loss)

"I drink coffee every morning" → LOW (habit)
"I'm learning Spanish" → MED (commitment, identity-forming)
"I attempted suicide in college" → HIGH (crisis, trauma)

"My timezone is America/Los_Angeles" → LOW (information)
"I was laid off" → MED (employment crisis, not acute trauma)
"I lost my home in a fire" → HIGH (acute trauma, loss)
```

### Scope

**Scope** defines whose fact it is: "user" or "shared".

| Scope | Meaning | Examples |
|-------|---------|----------|
| **user** | About the user only | "Mark loves hiking", "Mark's mother passed away" |
| **shared** | About the user AND companion together | "We watched Star Wars together", "Companion helped Mark through grief" |

**Use "shared" when:**
- The companion has done something with/for the user
- The companion has expressed values the user should remember
- It's a mutual experience or understanding

**Use "user" for everything else** — it's the safe default.

```
User says: "I love sci-fi movies"
Scope: "user" (fact about user preference)

Companion says: "I loved helping you through that difficult time"
Scope: "shared" (mutual memory, companion-expressed)

User and companion discuss: "We both love astronomy"
Scope: "shared" (mutual understanding)
```

### Metadata (Optional)

Store additional context:

```json
{
  "subject": "Mark",
  "predicate": "LOST_FAMILY_MEMBER",
  "object": "Mother (Jane, passed 2022)",
  "emotional_salience": "HIGH",
  "scope": "user",
  "metadata": {
    "relationship": "close",
    "date_of_loss": "2022-03-15",
    "ongoing_impact": "grief anniversaries are difficult",
    "how_they_coped": ["talked with therapist", "spent time with brother"]
  }
}
```

---

## Extraction Workflow

### Step 1: Listen for Fact Signals

Companion hears user say:

```
"I've been thinking about my job a lot. I love building things with my team,
but management politics have been exhausting. I've been looking at other roles.
My ideal would be somewhere laid-back with good people."
```

### Step 2: Identify Extract Candidates

Potential facts:
- Works on a team
- Loves building things
- Dislikes management politics
- Currently job searching
- Values company culture / laid-back environment
- Values good team dynamics

### Step 3: Evaluate Each Candidate

| Candidate | Include? | Reasoning |
|-----------|----------|-----------|
| "Works on a team building things" | ✓ | Durable, multi-use, identity |
| "Dislikes management politics" | ✓ | Values preference, actionable |
| "Currently job searching" | ✓ | Recent life event, relevant |
| "Prefers laid-back environment" | ✓ | Preference, actionable for suggestions |
| "Had coffee at 10am today" | ✗ | One-off, not durable |
| "Thinks politics are exhausting" | ✗ | Opinion, not fact; too general |

### Step 4: Structure Each Fact

```
Fact 1:
- Subject: Mark
- Predicate: WORKS_AT
- Object: Team-based software engineering role
- Emotional_salience: MED
- Scope: user
- Metadata: {enjoys_building, dislikes_politics, role_is_recent}

Fact 2:
- Subject: Mark
- Predicate: VALUES
- Object: Laid-back company culture and good team dynamics
- Emotional_salience: LOW
- Scope: user
- Metadata: {preference_type: workplace_culture}

Fact 3:
- Subject: Mark
- Predicate: HAS_GOAL
- Object: Find new job with better culture fit
- Emotional_salience: MED
- Scope: user
- Metadata: {status: actively_searching, timeline: current}
```

### Step 5: Store via Tool

```python
await memory_store_fact(
    subject="Mark",
    predicate="VALUES",
    object="Laid-back company culture and good team dynamics",
    metadata={
        "emotional_salience": "LOW",
        "scope": "user",
        "context": "workplace preference",
        "extraction_date": "2026-04-22"
    }
)
```

---

## Common Extraction Mistakes

### ❌ Mistake 1: Over-Extracting Conversational Noise
```
User: "I had a terrible day."
Over-extracted: Fact("Mark", "HAS_CONDITION", "Terrible day")

✓ Better: Wait for context. If they explain why:
Fact("Mark", HAS_CONDITION", "Experiencing workplace stress")
```

### ❌ Mistake 2: Under-Extracting Important Signal
```
User: "My mom passed when I was young. It shaped who I am."
Under-extracted: No facts stored

✓ Better:
Fact("Mark", "LOST_FAMILY_MEMBER", "Mother (passed when young)")
+ Fact("Mark", "VALUES", "This loss shaped my identity")
```

### ❌ Mistake 3: Wrong Emotional Salience
```
User: "I was laid off last month. It's been hard but I'm getting interviews."
Extracted: Fact("Mark", "EXPERIENCED_LOSS", "Job loss", salience=HIGH)

✓ Better: 
- salience=MED (important life event, not acute trauma)
- metadata: {status: recovering, has_support}
```

### ❌ Mistake 4: Vague Predicates
```
Over-vague: Fact("Mark", "IS", "Into tech")

✓ Better:
Fact("Mark", "WORKS_AT", "Software engineer")
Fact("Mark", "HAS_HOBBY", "Tech tinkering, building projects")
```

### ❌ Mistake 5: Scope Confusion
```
User says: "You really helped me through my grief."
Mistake: Scope="user"

✓ Better: Scope="shared"
(This is a mutual memory about what the companion did)
```

---

## Salience Calibration Examples

### Low-Salience Examples
```
"I prefer tea to coffee" → LOW
"I'm in the America/Los_Angeles timezone" → LOW
"I love hiking on weekends" → LOW
"My favorite book is The Hobbit" → LOW
"I usually wake up at 7am" → LOW
"I work as a software engineer" → LOW (base fact; context needed)
```

### Medium-Salience Examples
```
"I was laid off last month" → MED (life event, recovering)
"I was diagnosed with anxiety" → MED (health/identity, ongoing)
"My father is a doctor" → MED (identity component, family)
"I'm learning Spanish" → MED (commitment, identity-forming)
"I recently moved to Portland" → MED (major life change)
"My partner and I just broke up" → MED (relationship change, recent)
```

### High-Salience Examples
```
"My mother died when I was 10" → HIGH (grief, formative trauma)
"I attempted suicide in college" → HIGH (acute crisis, ongoing risk)
"I lost my home in a fire" → HIGH (acute loss, trauma)
"My child was diagnosed with cancer" → HIGH (family crisis)
"I survived abuse in my childhood" → HIGH (trauma, affects identity)
"I lost my job and my house in the same year" → HIGH (compounded crisis)
```

---

## Testing Extraction Quality

### Test 1: Persistence Check
```
Fact extracted: "Mark loves hiking"

Question: Will I ask about this again?
Expected: Yes, in different contexts
✓ Pass: Used in "fun weekend plans", "exercise habits", "adventure ideas"
✗ Fail: Never retrieved after initial extraction
```

### Test 2: Reusability Check
```
Fact extracted: "Mark values honesty in relationships"

Question: Can this support multiple queries?
Expected: Support for relationship advice, conflict resolution, values discussions
✓ Pass: Appears in 5+ different retrieval contexts
✗ Fail: Only appears in one narrow use case
```

### Test 3: Salience Accuracy Check
```
Fact: "Mark's father passed away"
Assigned: emotional_salience=HIGH

Test with intent="casual":
Expected: Fact suppressed when asking about fun activities
✓ Pass: Not returned for "fun weekend ideas"
✗ Fail: Returned inappropriately in casual context
```

### Test 4: Scope Correctness Check
```
Fact: "Companion helped Mark through job loss"
Assigned: scope="shared"

Expected: Used in "shared history" and two-way memory contexts
✓ Pass: Retrieved when asking about relationship history
✗ Fail: Lost or treated as only user fact
```

---

## Extraction Workflow Template

```python
async def extract_conversation_facts(
    db: AsyncSession,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
    messages: list[Message]
) -> list[StoredFact]:
    """
    1. Listen to each user message for signals
    2. Identify candidates
    3. Evaluate persistence + reusability
    4. Structure with proper salience
    5. Store via memory_store_fact
    """
    facts = []
    
    for msg in messages:
        if "my mother passed away" in msg.lower():
            facts.append({
                "subject": "User",
                "predicate": "LOST_FAMILY_MEMBER",
                "object": "Mother",
                "emotional_salience": "HIGH",
                "scope": "user"
            })
        
        if "i love" in msg.lower() and not is_one_off(msg):
            # Extract preference or hobby
            facts.append({...})
    
    # Store all facts
    for fact in facts:
        await memory_store_fact(...)
    
    return facts
```

---

## Related Documentation

- [Graceful Omission Guide](GRACEFUL_OMISSION_GUIDE.md) — Using emotional_salience
- [Intent-Based Retrieval Guide](INTENT_BASED_RETRIEVAL_GUIDE.md) — Retrieving facts
- [Cognitive Generation Guide](COGNITIVE_GENERATION_GUIDE.md) — Using facts in generation
