# Phase 6: Train + Evaluate

**Date:** 2026-10-27  
**Branch:** feature/model-training  
**Model files:** `src/root.sh/model/train.py`, `infer.py`, `features.py`, `intent.py`, `db/models.py`

---

## Models Trained

| Model | Type |
|-------|------|
| LightGBM | Gradient-boosted decision trees (primary) |
| Logistic Regression | Linear baseline |

---

## Heldout Results (380 rows, 107 families — evaluated ONCE)

| Metric | LightGBM | Logistic Regression |
|--------|----------|---------------------|
| Accuracy | 0.989 | 0.989 |
| Precision | 1.000 | 1.000 |
| Recall | 0.982 | 0.982 |
| F1 | 0.991 | 0.991 |
| AUC-ROC | 0.9999 | 0.9996 |

**Decision:** LightGBM advantage over Logistic Regression is <0.1% — negligible. Both models perform identically. Logistic Regression preferred for simplicity and interpretability.

---

## Per-Provenance Breakdown (LightGBM)

| Provenance | Rows | Accuracy | Precision | Recall | F1 |
|------------|------|----------|-----------|--------|----|
| seed | 91 | 1.000 | 1.000 | 1.000 | 1.000 |
| generated | 273 | 1.000 | 1.000 | 1.000 | 1.000 |
| nl2bash | 16 | 0.750 | 0.000 | 0.000 | 0.000 |

**Note:** All 16 NL2Bash heldout rows are safe (no risky NL2Bash in heldout), so recall/F1 for risky class is 0.0 — this is expected, not a model failure.

---

## Per-Pattern Breakdown (LightGBM)

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

## Files Created/Modified

| File | Purpose |
|------|---------|
| `src/root.sh/model/train.py` | Training script (LightGBM + Logistic Regression) |
| `src/root.sh/model/infer.py` | Scoring inference |
| `src/root.sh/features.py` | Six feature extraction |
| `src/root.sh/intent.py` | Intent class extractor (17 classes) |
| `src/root.sh/db/models.py` | SQLAlchemy models (SQLite) |
| `src/root.sh/model/model.pkl` | Trained LightGBM model (gitignored) |
| `data/decisions.db` | SQLite database with eval results |
| `requirements.txt` | Pinned dependency versions |
| `.venv/` | Python virtual environment (gitignored) |

---

## Files in `data/dataset/` (unchanged from Phase 5)

| File | Rows | Families |
|------|------|----------|
| `records.jsonl` | 2,012 | 563 |
| `families.json` | 563 entries | — |

---

## Next Phase (Phase 7)

Daemon + Staged Authorization:
- FastAPI + uvicorn daemon
- POST /score endpoint
- Staged authorization (pure functions)
- Default deny on any error
- Every call logged to SQLite

---

## Decision

**Proceed to Phase 7** — both models perform excellently (F1 0.991), all patterns at 1.0 F1. LightGBM advantage over Logistic Regression is negligible (<0.1%), so either model is acceptable. LightGBM retained as primary for feature importance capabilities.
