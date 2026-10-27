# Model Selection & Architecture

**Purpose:** Explain why we chose LightGBM + Logistic Regression, and how the model works.

---

## Why Two Models?

We do **not** train LightGBM alone. We train **both**:

| Model | Role |
|-------|------|
| LightGBM | Primary candidate — handles categorical features natively, fast, feature importance |
| Logistic Regression | Baseline — highly interpretable, no overfitting risk on small data |

**Decision rule:** Train both. If LightGBM's advantage over Logistic Regression is <3% AUC, prefer Logistic Regression for simplicity and interpretability.

**Why not just LightGBM?**
- 2,012 rows is small for gradient-boosted trees — risk of memorizing noise
- Logistic Regression is more robust on small data
- Research honesty: reporting only LightGBM hides whether complexity adds value

---

## Six Features (Exact Order)

| # | Feature | Values | Description |
|---|---------|--------|-------------|
| 1 | `source_trusted` | 1 / 0 | 1 if source == user_direct, else 0 |
| 2 | `intent_match` | 1 / 0 / -1 | 1 match, 0 mismatch, -1 unknown |
| 3 | `target_in_request` | fraction or -1 | Fraction of action path tokens in request; -1 if no target |
| 4 | `reversibility` | 0 / 1 | 0 reversible, 1 irreversible |
| 5 | `scope` | 0 / 1 / 2 | 0 single file/process, 1 folder/multi-file, 2 system-wide |
| 6 | `privilege` | 0 / 1 | 0 user, 1 root |

**Rule:** These six features are fixed. No embeddings, no torch, no LLM judges.

---

## Decision Thresholds (Initial)

| Risk Score | Decision |
|------------|----------|
| < 0.3 | Allow |
| 0.3 – 0.7 | Confirm |
| > 0.7 | Block |

Shown as **risk score**, not probability (uncalibrated).

---

## Model Architecture

```
┌─────────────────────────────────────────┐
│   Input: (user_request, proposed_action,│
│           source)                       │
└─────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│   Feature Extraction (6 features)       │
│   - source_trusted                      │
│   - intent_match                        │
│   - target_in_request                   │
│   - reversibility                       │
│   - scope                               │
│   - privilege                           │
└─────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│   LightGBM Classifier                   │
│   (gradient-boosted decision trees)     │
└─────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│   Risk Score (0.0 – 1.0, uncalibrated)  │
└─────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│   Staged Authorization                  │
│   score < 0.3  → ALLOW                  │
│   score 0.3-0.7 → CONFIRM               │
│   score > 0.7  → BLOCK                  │
└─────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│   seccomp + AppArmor backstop           │
│   (blocks catastrophic actions even if  │
│    classifier fails)                    │
└─────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────┐
│   Log to SQLite (WAL mode)              │
└─────────────────────────────────────────┘
```

---

## Training Flow

```
1. Load data/dataset/records.jsonl
2. Filter to split == 'train' (1,632 rows, 456 families)
3. Extract 6 features from each row
4. Train LightGBM (conservative: low num_leaves, high min_child_samples)
5. Train Logistic Regression (baseline)
6. Evaluate both on heldout (380 rows, 107 families) — ONCE
7. Compare metrics: accuracy, precision, recall, F1, AUC-ROC
8. Report per-provenance (seed/generated/nl2bash) and per-pattern
9. Save all results to SQLite
```

---

## Baselines to Report

Per AGENTS.md:
- Majority class baseline
- Categories-only rule
- Hand-written rule on same features
- Request-only text classifier (must stay near chance: style-leak audit)

---

## Code Files

| File | Purpose |
|------|---------|
| `src/root.sh/model/train.py` | Train LightGBM + Logistic Regression |
| `src/root.sh/model/infer.py` | Scoring inference |
| `src/root.sh/model/model.pkl` | Saved model (gitignored) |
| `src/root.sh/features.py` | Six feature extraction |
| `src/root.sh/intent.py` | Intent class extractor (rule-based) |
| `src/root.sh/datagen/schema.py` | 15-field Record schema |

---

*End of notes. Edit freely for your presentation or paper.*
