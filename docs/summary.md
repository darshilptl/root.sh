# Root.sh — Work Summary

**M.Tech Dissertation Research**  
**Topic:** Provenance-Based Defense Against Irreversible Prompt Injection in OS-Level Autonomous Agents  
**Working Directory:** `/home/darshil/Desktop/Vs Project/Development/root.sh`  
**Status:** Dataset complete; model training (Phase 6) is next  
**Last Updated:** Tue Oct 27 2026

---

## 1. What We Build (One Sentence)

A defense layer that sits beside an autonomous OS-level agent. For each proposed command it receives `(user_request, proposed_action, source)` and returns **allow / confirm / block**, a **risk score**, and a **reason**.

---

## 2. Current Status

| Phase | Module | Status |
|-------|--------|--------|
| 0–1 | Scaffold, data folders, DB schema | Complete |
| 2–3 | Command classifier, intent extractor + features | Complete |
| 4 | NL2Bash converter + validator + import | Complete |
| 5 | Dataset generation, review, split freeze | Complete |
| 6 | Train + evaluate | **Next (immediate)** |
| 7–11 | Daemon, scenario harness, kernel enforcement, integrations, CLI/TUI | Future |

**Overall progress:** ~5 of 11 phases complete (~45%)

---

## 3. Dataset (Completed)

### Location
- `data/dataset/records.jsonl` — 2,012 merged records (all 15 fields)
- `data/dataset/families.json` — 563 family metadata entries (frozen split)

### Composition

| Source | Rows | Families | Label Split |
|--------|------|----------|-------------|
| Staging (7 attack patterns) | 1,932 | 483 | ~60% risky / 40% safe |
| NL2Bash (external corpus) | 80 | 80 | 100% safe |
| **Total** | **2,012** | **563** | **60% risky / 40% safe** |

### 7 Attack Patterns (13 risky + 7 safe-twin families each)

| Pattern | What It Models |
|---------|----------------|
| env-poison | Content tells agent to change shell environment (export PATH, LD_PRELOAD, unset, alias) |
| param-escape | Content makes agent use working dir/output path/symlink outside project |
| file-injection | README/config tells agent to delete, overwrite, or run remote script |
| halluc-destructive | Agent wrongly believes earlier step succeeded, then runs destructive move/delete |
| agent-deviation | Agent takes destructive action task never needed (drop table, delete production data) |
| priv-escalation | Agent grants itself privileges (sudo, setuid, sudoers, chmod on system paths) |
| exfil-remote-exec | Content tells agent to send local files/secrets to remote host or pipe remote script |

### Splits (by `family_id`, never by row; first 20% by SHA-256 = heldout)

| Split | Rows | Families |
|-------|------|----------|
| Train | 1,632 | 456 |
| Heldout | 380 | 107 |
| **Total** | **2,012** | **563** |

### Labeling Rules

| Condition | Label |
|-----------|-------|
| `source == user_direct` AND action matches request | **safe** (even if dangerous) |
| Action ≠ what request asked for | **risky** |
| `source ∈ {file_content, web_content, tool_output}` | **risky** |
| `source == agent_internal` | **risky** |
| Any `sudo` or `chmod` command | **risky** |

### Data Safety
- Placeholders only (`example.com`, `attacker.example`, `/tmp/sandbox-*`, `AKIAEXAMPLE`)
- No real hosts, keys, or tokens
- Plain one-line shell commands only; no exploit code or obfuscation

---

## 4. Model Selection

### Primary Model: LightGBM

| Reason | Detail |
|--------|--------|
| Handles categorical features natively | `source`, `intent_class`, `provenance` are categorical; no one-hot encoding needed |
| Fast training/inference | Suitable for real-time scoring in a daemon |
| Feature importance available | Useful for dissertation reporting and interpretability |
| No embeddings, no torch | Matches AGENTS.md constraints |
| Gradient-boosted decision trees | Good for tabular, rule-like features |

### Baseline Model: Logistic Regression

| Reason | Detail |
|--------|--------|
| Highly interpretable | Coefficients show feature weight directly |
| No overfitting risk on small data | 2,012 rows is small; LR is robust |
| Fast | Trivial training and inference |

**Decision rule:** Train both. If LightGBM's advantage over Logistic Regression is <3% AUC, prefer Logistic Regression for simplicity and interpretability.

### Six Features (Exact Order)

| # | Feature | Values |
|---|---------|--------|
| 1 | `source_trusted` | 1 if `source == user_direct`, else 0 |
| 2 | `intent_match` | 1 match, 0 mismatch, -1 unknown |
| 3 | `target_in_request` | Fraction of action path tokens present in request; -1 if no target |
| 4 | `reversibility` | 0 reversible, 1 irreversible |
| 5 | `scope` | 0 single file/process, 1 folder/multi-file, 2 system-wide |
| 6 | `privilege` | 0 user, 1 root |

### Decision Thresholds (Initial, tune by CV on train only)

| Risk Score | Decision |
|------------|----------|
| < 0.3 | Allow |
| 0.3 – 0.7 | Confirm |
| > 0.7 | Block |

*Shown as "risk score", not probability (uncalibrated).*

---

## 5. Pipeline Flow (End to End)

```
Agent proposes command
        │
        ▼
Hook → POST /score {user_request, proposed_action, source}
        │
        ▼
Classify action (action_class, reversibility, scope, privilege)
        │
        ▼
Extract intent_class from request (rule-based)
        │
        ▼
Six features → LightGBM score → Risk score
        │
        ▼
Staged authorization (scope → authorization → impact ceiling → repeat → default deny)
        │
        ▼
Decision: Allow | Confirm | Block
        │
        ▼
seccomp / AppArmor backstop (blocks catastrophic actions even if classifier fails)
        │
        ▼
Log to SQLite (WAL mode): decision, outcome, run metadata
```

**Error rule:** Any error, missing model, malformed or inconclusive input → **block**.

---

## 6. What Happens After Training (Flow to the End)

| Step | Action | Output |
|------|--------|--------|
| 1 | Train LightGBM + Logistic Regression on train split | `model.pkl` (gitignored) |
| 2 | Evaluate on heldout (ONCE, never tuned on) | Accuracy, precision, recall, F1, AUC-ROC |
| 3 | Report per-provenance results (seed vs generated vs nl2bash) | Evaluation metrics |
| 4 | Report per-pattern results (all 7 patterns) | Evaluation metrics |
| 5 | Build FastAPI + uvicorn daemon with POST /score | Running scoring service |
| 6 | Implement staged authorization (pure functions, default deny) | Authorization decisions |
| 7 | Log every call to SQLite (WAL mode) | Decision audit trail |
| 8 | Scenario harness: run each attack pattern, undefended vs defended | Attack mitigation metrics |
| 9 | Kernel enforcement: seccomp + AppArmor profiles | Denied syscalls fail in sandbox |
| 10 | Agent integrations: OpenCode plugin + Claude Code hook | Blocked actions do not run |
| 11 | CLI + TUI (Typer + Rich) + final report | User-facing tools + report numbers = direct DB queries |

---

## 7. Git Workflow (Trunk-Based, Solo)

| Rule | Detail |
|------|--------|
| Default branch | `main` (never `master`) |
| Branch naming | `feature/<module>` for new functionality; `setup/` for scaffolding |
| One branch = one concern = one phase | Never mix concerns |
| Start from up-to-date `main` | `git checkout main` → `git pull` → `git checkout -b feature/<module>` |
| Commit convention | `type(scope): imperative subject` (≤72 chars, no period) |
| Footer | `Refs: docs/modules/NN-name.md` |
| Merge | Squash merge into `main` via PR (even solo) |
| Tag | `v0.N.0` after each phase merge |
| Agent role | Branch, commit, push feature branch, write PR title/description, stop |
| Author role | Merge, tag, confirm |

---

## 8. Rules (Non-Negotiable)

1. **Default deny:** Any error, missing model, malformed input → block
2. **No LLM scores or judges:** Agents used offline to draft dataset rows only
3. **Never train/tune/build features on heldout:** Split by `family_id`
4. **Never execute generated commands:** Real destructive commands run only inside `sandbox/` as unprivileged user
5. **Python owns the schema:** No network calls in scoring code
6. **No new files outside the map without asking**
7. **Never guess versions/flags/URLs:** Check and record in `docs/BLOCKERS.md`
8. **Ambiguity → "Open questions" in module doc → stop**
9. **Never overwrite user's CLAUDE.md/AGENTS.md:** Append marked section only
10. **Never merge into or push to `main`; never tag, force-push, or use `--no-verify`**
11. **Small pure functions, type hints, no global state, tests per module, seed 42**
12. **Report only results from eval runs stored in the DB**

---

## 9. How to Read This Document (For AI Agents)

- **Sections 1–3:** Project context and current state (read first)
- **Section 4:** Dataset composition and labeling (the ground truth)
- **Section 5:** Model and feature choices (the "what" and "why")
- **Section 6:** Runtime pipeline (the "how")
- **Section 7:** Remaining work (the roadmap)
- **Section 8:** Git and rules (the process constraints)

All data lives under `data/dataset/`. All code lives under `src/rootguard/`. All module documentation lives under `docs/modules/NN-name.md`.

---

*End of summary. This document is minimal but structurally complete for both AI agents and human readers.*
