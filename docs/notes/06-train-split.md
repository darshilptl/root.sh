# Train Split Explained

**Purpose:** Explain how the dataset is split into train and heldout, and why.

---

## Split Rule

**Split by `family_id`, never by row.**

This is critical: all 4 rows of a family (1 head + 3 variants) must stay together. If you split by row, you could have the head in train and a variant in heldout — data leakage.

---

## How the Split Is Made

1. Collect all unique `family_id`s
2. Sort them by SHA-256 hash (deterministic, reproducible)
3. Take first 20% as heldout
4. Rest = train

---

## Numbers

| Split | Rows | Families | Percentage |
|-------|------|----------|------------|
| Train | 1,632 | 456 | ~80% |
| Heldout | 380 | 107 | ~20% |
| Total | 2,012 | 563 | 100% |

---

## Per-Pattern Split

Each pattern has 69 families (except nl2bash with 80). Within each pattern:
- ~13 families → heldout
- ~56 families → train

This ensures every pattern is represented in both train and heldout.

---

## What Goes in Train

- Train LightGBM model
- Train Logistic Regression baseline
- Hyperparameter tuning via cross-validation
- Feature engineering experiments

**Never use heldout for training or tuning.**

---

## What Goes in Heldout

- Final evaluation of both models
- Evaluated **once only**
- Metrics: accuracy, precision, recall, F1, AUC-ROC
- Per-provenance breakdown (seed vs generated vs nl2bash)
- Per-pattern breakdown (all 7 patterns)

---

## File Locations

| File | Purpose |
|------|---------|
| `data/dataset/records.jsonl` | All rows with `split` field (train/heldout) |
| `data/dataset/families.json` | Family metadata with frozen split |
| `data/dataset/` | Git-tracked (not gitignored) |

---

## Example: How to Filter

```python
import json

train_rows = []
heldout_rows = []

with open('data/dataset/records.jsonl') as f:
    for line in f:
        row = json.loads(line)
        if row['split'] == 'train':
            train_rows.append(row)
        elif row['split'] == 'heldout':
            heldout_rows.append(row)

print(f"Train: {len(train_rows)} rows")
print(f"Heldout: {len(heldout_rows)} rows")
```

---

*End of notes.*
