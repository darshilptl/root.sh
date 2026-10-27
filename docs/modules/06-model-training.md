# docs/modules/06-model-training.md

## Phase 6: Train + Evaluate

### Purpose
Train LightGBM + Logistic Regression models on train split, evaluate on heldout once, save results to SQLite.

### Input Data
- **File:** `data/dataset/records.jsonl`
- **Train:** 1,632 rows / 456 families (split == 'train')
- **Heldout:** 380 rows / 107 families (split == 'heldout') — evaluated ONCE only
- **Label split:** Risky: 1,208 (60%) / Safe: 804 (40%)

### Model Architecture

| Component | Choice | Reason |
|-----------|--------|--------|
| Primary | LightGBM | Handles categorical features natively, fast |
| Baseline | Logistic Regression | Interpretable, no overfitting risk on small data |
| Features | 6 features (source_trusted, intent_match, target_in_request, reversibility, scope, privilege) | Fixed per AGENTS.md |
| No embeddings, no torch | Per AGENTS.md rule | Keeps model small and interpretable |

### Decision Thresholds
| Risk Score | Decision |
|------------|----------|
| < 0.3 | Allow |
| 0.3 – 0.7 | Confirm |
| > 0.7 | Block |

### Implementation Steps

1. **Create `src/root.sh/model/train.py`**
   - Load `data/dataset/records.jsonl`
   - Filter train split, extract 6 features
   - Train LightGBM (conservative: num_leaves=15, min_child_samples=10)
   - Train Logistic Regression (baseline)
   - Evaluate both on heldout
   - Per-provenance breakdown (seed/generated/nl2bash)
   - Per-pattern breakdown (7 patterns)
   - Save `model.pkl` (gitignored)
   - Save metrics to SQLite

2. **Create `src/root.sh/model/infer.py`**
   - Load model.pkl
   - Score single `(user_request, proposed_action, source)` tuple
   - Return risk_score + decision + reasoning

3. **Create `src/root.sh/features.py`**
   - Extract six features from user_request + proposed_action + source

4. **Create `src/root.sh/intent.py`**
   - Rule-based intent class extractor (17 classes)

5. **Create `src/root.sh/db/models.py`**
   - SQLAlchemy models: Decision, Run
   - SQLite WAL mode

### Validation Checks
- [ ] No family overlap between train and heldout
- [ ] Heldout evaluated exactly once
- [ ] No tuning on heldout
- [ ] Baselines reported (Logistic Regression)
- [ ] Per-provenance results saved
- [ ] Per-pattern results saved
- [ ] Results stored in SQLite

### Expected Output
- `src/root.sh/model/model.pkl` (gitignored)
- `data/decisions.db` (SQLite with eval runs)
- `docs/summaries/06-train-evaluate.md`

### Open Questions
- NL2Bash rows are all safe (no risky examples) — affects per-provenance metrics for risky class
- 2,012 rows total — small for GBDT, may overfit
- Per-pattern heldout only ~52 rows per pattern
