# User Profile Management Guidance

## Overview

This guide teaches agents how to manage user profile information, specifically the user's name, using the available tools.

## User Name CRUD Lifecycle

### 1. Check Current State (READ)

**When:** At the start of any session or before making updates
**Tool:** `get_user_info(api_key)` 
**Returns:** `{user_id, name, email, timezone}`

```
Purpose: Determine if the user's name is already known
Action: Call get_user_info → check if name field is set
Outcome: Decide whether to extract and store the name
```

**Example:**
```
get_user_info() → {"name": null, "email": "user@example.com", ...}
→ Name is not set, should look for it
```

---

### 2. Extract Name (PROACTIVE)

**When:** User mentions their name naturally in conversation
**Patterns to listen for:**
- Direct statements: "I'm Mark", "My name is Sarah", "Call me Alex"
- Contextual mentions: "Mark here", "It's John from yesterday"
- Corrections: "Actually, it's Rebecca, not Rachel"
- Introductions: First message of a session with name included

**Action:** 
```
1. Recognize name mention in user input
2. Call get_user_info() to check current state
3. If name is null or different:
   → Call update_user_name(api_key, name)
4. Confirm to user: "I'll remember you as Mark!"
```

---

### 3. Update Name (CREATE/UPDATE)

**When:** User provides their name and get_user_info shows it's not set, OR user corrects their name
**Tool:** `update_user_name(api_key, name)`
**Returns:** `{user_id, name, success: true}`

**Example agent flow:**
```
User: "Hi, I'm Mark!"
Agent:
  1. Calls get_user_info() → {name: null}
  2. Calls update_user_name("Mark")
  3. Returns: {name: "Mark", success: true}
  4. Says: "Got it! I'll remember you as Mark."
```

**Confirm back to user:** 
- "I'll remember you as [name]"
- "Nice to meet you, [name]!"
- "Noted—[name] it is!"

---

### 4. Use in Context

**Diary/Dream/Musing Generation:**
- System automatically fetches user.name from database
- If name is set → uses it: "recent interactions with Mark"
- If name is null → falls back to: "recent interactions with your user"

**No agent action needed** — name flows automatically into cognitive outputs.

---

## Decision Tree

```
┌─ At session start or name-related message
├─ Call get_user_info()
│  ├─ If name is null or empty
│  │  └─ Listen for name in user message
│  │     ├─ Name found → Call update_user_name(name) + confirm
│  │     └─ Name not found → Optionally ask "What's your name?"
│  ├─ If name is set and matches user context
│  │  └─ Continue normally (name is known ✓)
│  └─ If name is set but user corrects it
│     └─ Call update_user_name(new_name) + confirm
```

---

## Best Practices

### DO:
✅ Extract name on first mention ("I'm Mark" → store immediately)
✅ Confirm back to user ("I'll remember you as Mark")
✅ Check `get_user_info()` before updating (avoid thrashing DB)
✅ Use the stored name in all subsequent outputs
✅ Handle corrections gracefully ("Actually, it's Alex" → update + confirm)

### DON'T:
❌ Ask for name repeatedly if already set
❌ Extract names from pet/family context ("My cat Luna", "sister Minerva")
❌ Update without confirmation
❌ Use regex extraction as primary method (database name is source of truth)

---

## Example Conversations

### Scenario 1: New user provides name
```
User: "Hey, I'm Mark! How are you?"
Agent: 
  - get_user_info() → {name: null}
  - Recognizes "I'm Mark"
  - update_user_name("Mark")
  - Replies: "Great to meet you, Mark! I'm doing well, thanks for asking."
```

### Scenario 2: Name already set
```
User: "How have you been?"
Agent:
  - get_user_info() → {name: "Mark"}
  - Replies naturally, using stored name in diary/musing context
  - (No update needed)
```

### Scenario 3: User corrects their name
```
User: "Actually, I go by Alex, not Mark."
Agent:
  - get_user_info() → {name: "Mark"}
  - Recognizes correction
  - update_user_name("Alex")
  - Replies: "Got it—I'll remember you as Alex from now on."
```

---

## Implementation Notes

### Tools Available
| Tool | Purpose | Auth | Returns |
|------|---------|------|---------|
| `get_user_info()` | Check current user profile | api_key | {user_id, name, email, timezone} |
| `update_user_name(name)` | Set or update user's name | api_key | {user_id, name, success} |

### Integration Points
- **Cognitive generation:** `generate_diary()`, `generate_dream()`, `generate_musing()` automatically use stored name
- **Extraction:** No longer uses regex; reads from `user.name` field
- **Fallback:** If name is null, uses "your user" in prompts

---

## Summary

The user name CRUD lifecycle is **agent-driven**:
1. **Read** → `get_user_info()` to check current state
2. **Create** → `update_user_name()` when user mentions name for first time
3. **Update** → `update_user_name()` when user corrects their name
4. **Use** → Automatically in all diary/dream/musing outputs

This ensures names are stored **once, early, reliably** and used **everywhere consistently**.
