# Pipeline Flow & Architecture

**Purpose:** Explain the end-to-end RootGuard pipeline from hook to log.

---

## Runtime Flow (Step by Step)

```
1. Agent proposes command
   └─→ User request: "List the files in this project folder"
   └─→ Proposed action: "export PATH=/tmp/sandbox-bin:$PATH"
   └─→ Source: file_content

2. Hook intercepts → POST /score
   └─→ Sends (user_request, proposed_action, source) to daemon

3. Classify action
   └─→ action_class: modify_environment
   └─→ reversibility: 1 (irreversible)
   └─→ scope: 2 (system-wide)
   └─→ privilege: 1 (root)

4. Extract intent_class from request (rule-based)
   └─→ intent_class: list_read

5. Compute six features
   └─→ source_trusted: 0 (file_content ≠ user_direct)
   └─→ intent_match: 0 (list_read ≠ modify_environment)
   └─→ target_in_request: -1 (no path target in action)
   └─→ reversibility: 1
   └─→ scope: 2
   └─→ privilege: 1

6. LightGBM score → Risk score (0.0 – 1.0)
   └─→ Example: 0.85

7. Staged authorization
   └─→ score > 0.7 → BLOCK

8. seccomp / AppArmor backstop
   └─→ Blocks catastrophic syscalls even if classifier missed

9. Log to SQLite (WAL mode)
   └─→ decision, outcome, run metadata stored
```

---

## Decision Logic

| Risk Score | Decision | Meaning |
|------------|----------|---------|
| < 0.3 | Allow | Action matches request, user_direct, low risk |
| 0.3 – 0.7 | Confirm | Uncertain — needs human confirmation |
| > 0.7 | Block | Action doesn't match, or from untrusted source, or high risk |

**Default deny rule:** Any error, missing model, malformed input → **block**

---

## Error Handling

| Scenario | Result |
|----------|--------|
| Malformed input | Block |
| Missing model file | Block |
| Missing fields | Block |
| Inconclusive input | Block |
| Scoring error | Block |

---

## Logging (SQLite, WAL mode)

Every call is logged:

| Field | Description |
|-------|-------------|
| decision | allow / confirm / block |
| risk_score | 0.0 – 1.0 |
| reason | Human-readable explanation |
| features | The six feature values |
| timestamp | When the decision was made |
| outcome | Whether the command was actually run |

---

## Pipeline Phases (AGENTS.md Section 8)

| Phase | Module | Status |
|-------|--------|--------|
| 0 | Scaffold, data folders | Complete |
| 1 | DB schema | Complete |
| 2 | Command classifier | Complete |
| 3 | Intent extractor + features | Complete |
| 4 | NL2Bash converter + validator + import | Complete |
| 5 | Dataset generation, review, split freeze | Complete |
| 6 | Train + evaluate | **Next** |
| 7 | Daemon + staged authz | Future |
| 8 | Scenario harness + evaluation run | Future |
| 9 | Kernel enforcement | Future |
| 10 | Agent integrations | Future |
| 11 | CLI, TUI, report | Future |

---

## What "Blocked" Means

A blocked action **does not run**. The daemon returns `block` to the agent, and the agent must not execute the command. seccomp + AppArmor provide a backstop — even if the classifier fails, catastrophic syscalls (rm -rf /, DROP TABLE, etc.) fail at the kernel level.

---

*End of notes.*
