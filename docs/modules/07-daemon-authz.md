# docs/modules/07-daemon-authz.md

## Phase 7: Daemon + Staged Authorization

### Purpose
Build the FastAPI daemon with POST /score endpoint and staged authorization logic. Every proposed command receives `(user_request, proposed_action, source)` and returns allow / confirm / block with a risk score and reason.

### Runtime Flow

```
agent proposes command -> hook -> POST /score {user_request, proposed_action, source}
 -> classify action (action_class, reversibility, scope, privilege)
 -> extract intent_class from the request (rules)
 -> six features -> LightGBM score -> staged authz -> allow | confirm | block
 -> seccomp / AppArmor backstop -> log (SQLite)
```

### Files to Create

| File | Purpose |
|------|---------|
| `src/root.sh/daemon.py` | FastAPI + uvicorn daemon with POST /score endpoint |
| `src/root.sh/authz.py` | Staged authorization (pure functions): scope -> authorization -> impact ceiling -> repeat -> default deny |

### Staged Authorization Logic

```
score < 0.3    -> ALLOW
score 0.3-0.7  -> CONFIRM
score > 0.7    -> BLOCK
```

**Default deny rule:** Any error, missing model, malformed input, or inconclusive input means BLOCK.

### Input Format (POST /score)

| Field | Type | Description |
|-------|------|-------------|
| user_request | string | What the user asked for |
| proposed_action | string | The shell command the agent wants to run |
| source | enum | user_direct, file_content, web_content, tool_output, agent_internal |

### Output Format

| Field | Type | Description |
|-------|------|-------------|
| decision | enum | allow / confirm / block |
| risk_score | float | 0.0 – 1.0 (uncalibrated) |
| reason | string | Human-readable explanation |
| features | object | The six feature values |

### Logging
Every call logged to SQLite (`data/decisions.db`) with decision, risk_score, source, timestamp.

### Validation Checks
- [ ] Malformed input returns block
- [ ] Missing model returns block
- [ ] All 7 patterns tested
- [ ] Default deny on error
- [ ] Every call logged to SQLite

### Open Questions
- seccomp + AppArmor integration (Phase 9) — not yet implemented
- Claude Code hook behavior — needs verification from official docs
