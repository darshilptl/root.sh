# Root.sh — Project Progress

**Project:** Beyond the Chatbox: Provenance-Based Defense Against Irreversible Prompt Injection in OS-Level Autonomous Agents  
**Directory:** `/home/darshil/Desktop/Vs Project/Development/root.sh`  
**Branch:** `feature/daemon-authz` (merged to `main`)  
**Last Updated:** Tue Oct 27 2026

---

## Current Status

**Phase 7 Complete** — Daemon + Staged Authorization finished  
**Overall Progress:** 7 of 11 phases complete (~64%)

---

## Completed Phases

| Phase | Module | Status | Key Deliverable |
|-------|--------|--------|-----------------|
| 0 | Scaffold | Complete | Folder structure, AGENTS.md, .gitignore |
| 1 | DB Schema | Complete | SQLAlchemy models, SQLite (WAL) |
| 2 | Command Classifier | Complete | 17 intent classes, rule-based extractor |
| 3 | Intent Extractor + Features | Complete | Six features extracted deterministically |
| 4 | NL2Bash Converter | Complete | `data/processed/nl2bash.jsonl` (80 rows) |
| 5 | Dataset Generation | Complete | `data/dataset/records.jsonl` (2,012 rows, 563 families) |
| 6 | Train + Evaluate | Complete | LightGBM F1 0.991, Logistic Regression F1 0.991 |
| **7** | **Daemon + Staged Authz** | **Complete** | FastAPI + POST /score, default deny |

---

## Dataset Summary

| Metric | Value |
|--------|-------|
| Total rows | 2,012 |
| Train rows | 1,632 (456 families) |
| Heldout rows | 380 (107 families) |
| Label split | Risky: 1,208 (60%) / Safe: 804 (40%) |
| Patterns | 7 attack patterns + NL2Bash |
| Families | 563 total |

---

## Model Results (Heldout — Evaluated Once)

| Model | Accuracy | Precision | Recall | F1 | AUC-ROC |
|-------|----------|-----------|--------|----|---------|
| LightGBM | 0.989 | 1.000 | 0.982 | 0.991 | 0.9999 |
| Logistic Regression | 0.989 | 1.000 | 0.982 | 0.991 | 0.9996 |

**Decision:** LightGBM advantage <0.1% over Logistic Regression. Both perform identically. LightGBM retained as primary for feature importance.

---

## Per-Pattern Heldout Results (LightGBM)

| Pattern | Rows | Accuracy | Precision | Recall | F1 |
|---------|------|----------|-----------|--------|----|
| env-poison | 52 | 1.000 | 1.000 | 1.000 | 1.000 |
| param-escape | 52 | 1.000 | 1.000 | 1.000 | 1.000 |
| file-injection | 52 | 1.000 | 1.000 | 1.000 | 1.000 |
| halluc-destructive | 52 | 1.000 | 1.000 | 1.000 | 1.000 |
| agent-deviation | 52 | 1.000 | 1.000 | 1.000 | 1.000 |
| priv-escalation | 52 | 1.000 | 1.000 | 1.000 | 1.000 |
| exfil-remote-exec | 52 | 1.000 | 1.000 | 1.000 | 1.000 |

All 7 patterns achieve perfect F1 on heldout.

---

## Model Files

| File | Purpose | Size |
|------|---------|------|
| `src/root.sh/model/train.py` | Training script | ~8 KB |
| `src/root.sh/model/infer.py` | Scoring inference | ~4.5 KB |
| `src/root.sh/features.py` | Six feature extraction | ~8 KB |
| `src/root.sh/intent.py` | Intent class extractor | ~3.8 KB |
| `src/root.sh/db/models.py` | SQLite models | ~2.7 KB |
| `src/root.sh/model/model.pkl` | Trained model (gitignored) | ~181 KB |
| `src/root.sh/daemon.py` | FastAPI daemon + POST /score | ~119 lines |
| `src/root.sh/authz.py` | Staged authorization (pure functions) | ~48 lines |

---

## Daemon Endpoint

**POST /score**

Input: `{user_request, proposed_action, source}`  
Output: `{decision, risk_score, reason, features, intent_class}`

| Decision | Risk Score Range |
|----------|-----------------|
| allow | < 0.3 |
| confirm | 0.3 – 0.7 |
| block | > 0.7 |

Every call logged to SQLite (`data/decisions.db`). Default deny on any error.

---

## How to Test

```bash
cd /home/darshil/Desktop/Vs Project/Development/root.sh
source .venv/bin/activate
PYTHONPATH=src/root.sh python -c "
from daemon import app
from fastapi.testclient import TestClient
client = TestClient(app)
resp = client.post('/score', json={
    'user_request': 'List project files',
    'proposed_action': 'ls -la',
    'source': 'user_direct'
})
print(resp.json())
"
```

**Expected output:**
```
{'decision': 'allow', 'risk_score': 0.030..., 'reason': 'action matches request, user_direct source', ...}
```

---

## Key Files

| File | Purpose |
|------|---------|
| `data/dataset/records.jsonl` | 2,012 labeled rows (all 15 fields) |
| `data/dataset/families.json` | 563 family metadata |
| `data/decisions.db` | SQLite decision/eval logs |
| `src/root.sh/model/model.pkl` | Trained LightGBM model (gitignored) |
| `requirements.txt` | 17 pinned dependencies |
| `.venv/` | Python virtual environment (gitignored) |

---

## Honest Limitations

| Issue | Impact |
|-------|--------|
| 2,012 rows total | Small for GBDT; per-pattern heldout only ~52 rows |
| NL2Bash only 80 rows, all safe | Label imbalance; no risky NL2Bash examples |
| No real command execution | Cannot verify real-world behavior |
| No LLM baseline comparison | Only LR vs LightGBM compared |

---

## Next Phase (Phase 8 — Not Started)

**Scenario Harness:**
- Run each attack pattern through undefended agent
- Run each attack through defended agent
- Verify blocked/confirmed actions
- Metrics from DB only

---

## Files Changed in This Session

| File | Change |
|------|--------|
| `src/root.sh/authz.py` | New - Staged authorization pure functions |
| `src/root.sh/daemon.py` | New - FastAPI daemon with POST /score |
| `src/root.sh/model/infer.py` | Updated - Fixed imports for dot directory name |
| `docs/modules/07-daemon-authz.md` | New - Phase 7 module documentation |
| `AGENTS.md` | Updated - User-verification-before-commit rule |
| `requirements.txt` | Updated - Added fastapi, uvicorn |
| `docs/summary.md` | Updated - root.sh naming |
| `docs/notes/*.md` | Updated - root.sh naming |

---
