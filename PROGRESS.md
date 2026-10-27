# RootGuard — Project Progress

**Project:** Beyond the Chatbox: Provenance-Based Defense Against Irreversible Prompt Injection in OS-Level Autonomous Agents  
**Directory:** `/home/darshil/Desktop/Vs Project/Development/root.sh`  
**Branch:** `feature/model-training`  
**Last Updated:** Tue Oct 27 2026

---

## Current Status

**Phase 6 Complete** — Dataset + Model Training finished  
**Overall Progress:** 6 of 11 phases complete (~55%)

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
| **6** | **Train + Evaluate** | **Complete** | LightGBM F1 0.991, Logistic Regression F1 0.991 |

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
| Twins | 49 safe-twin pairs |

---

## Model Results (Heldout — Evaluated Once)

| Model | Accuracy | Precision | Recall | F1 | AUC-ROC |
|-------|----------|-----------|--------|----|---------|
| LightGBM | 0.989 | 1.000 | 0.982 | 0.991 | 0.9999 |
| Logistic Regression | 0.989 | 1.000 | 0.982 | 0.991 | 0.9996 |

**Decision:** LightGBM advantage <0.1% over Logistic Regression. Both perform identically on heldout.

---

## Model Files

| File | Purpose | Size |
|------|---------|------|
| `src/root.sh/model/train.py` | Training script | ~8 KB |
| `src/root.sh/model/infer.py` | Scoring inference | ~4.5 KB |
| `src/root.sh/features.py` | Six feature extraction | ~8 KB |
| `src/root.sh/intent.py` | Intent classifier | ~3.8 KB |
| `src/root.sh/db/models.py` | SQLite models | ~2.7 KB |
| `src/root.sh/model/model.pkl` | Trained model (gitignored) | ~181 KB |

---

## Next Phase (Phase 7 — Not Started)

**Daemon + Staged Authorization:**
- FastAPI + uvicorn daemon
- POST /score endpoint
- Staged authorization (pure functions)
- Default deny on any error
- Every call logged to SQLite

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

## How to Reproduce Training

```bash
cd /home/darshil/Desktop/Vs Project/Development/root.sh
source .venv/bin/activate
python src/root.sh/model/train.py
```

**Results saved to:** `data/decisions.db` (SQLite)  
**Model saved to:** `src/root.sh/model/model.pkl` (gitignored)

---
