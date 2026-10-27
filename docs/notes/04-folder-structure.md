# Folder Structure

**Purpose:** Show exactly where every file lives in the RootGuard project.

---

## Root Layout

```
root.sh/
├── AGENTS.md                 # Project specification & rules
├── summary.md                # Work summary
├── .gitignore                # Git ignore rules
├── pyproject.toml            # Python project config
│
├── data/                     # All data (raw, processed, staged, final)
│   ├── external/             # raw third-party (gitignored): nl2bash/
│   ├── processed/            # converted external data: nl2bash.jsonl
│   ├── staging/              # agent-generated rows awaiting review
│   ├── dataset/              # FINAL reviewed dataset
│   │   ├── records.jsonl     # 2,012 merged records (15 fields)
│   │   └── families.json     # 563 families with frozen split
│   ├── review/               # spot_check.csv
│   └── LICENSES.md           # Third-party license records
│
├── src/rootguard/            # All source code
│   ├── __init__.py
│   ├── config.py             # Configuration
│   ├── daemon.py             # FastAPI + uvicorn daemon
│   ├── authz.py              # Staged authorization (pure functions)
│   ├── features.py           # Six feature extraction
│   ├── intent.py             # Intent class extractor (rule-based)
│   ├── categories.py         # Action categories
│   ├── db/
│   │   ├── models.py         # SQLAlchemy models
│   │   └── migrations/       # Alembic migrations
│   ├── datagen/
│   │   ├── schema.py         # 15-field Record schema
│   │   ├── convert_nl2bash.py
│   │   └── importer.py
│   ├── model/
│   │   ├── train.py          # LightGBM + Logistic Regression training
│   │   ├── infer.py          # Scoring inference
│   │   └── model.pkl         # Saved model (gitignored)
│   ├── enforce/
│   │   ├── seccomp.py        # seccomp profile
│   │   └── apparmor/         # AppArmor profiles
│   ├── integrations/         # Hook adapters (OpenCode, Claude Code)
│   └── cli/
│       ├── app.py            # Typer + Rich CLI
│       ├── commands/         # CLI commands
│       └── ui/               # TUI components
│
├── docs/
│   ├── modules/              # NN-name.md, one per phase
│   ├── notes/                # Fundamentals notes (pure markdown)
│   ├── datasets/             # Dataset info
│   ├── models/               # Model info
│   ├── summaries/            # Summaries
│   └── BLOCKERS.md           # Blockers & workarounds
│
├── sandbox/                  # Synthetic files for attack scenarios
├── eval/                     # Scenario harness, metrics
└── tests/                    # pytest tests
```

---

## Data Folder Detail

| Path | Contents | Gitignored? |
|------|----------|-------------|
| `data/external/` | Raw third-party (nl2bash/) | Yes |
| `data/processed/` | Converted external data (nl2bash.jsonl) | No |
| `data/staging/` | Agent-generated rows awaiting review | No |
| `data/dataset/` | Final reviewed dataset (records.jsonl, families.json) | No |
| `data/review/` | Spot check files | No |
| `data/LICENSES.md` | Third-party licenses | No |

---

## Model Files

| Path | Purpose | Gitignored? |
|------|---------|-------------|
| `src/rootguard/model/train.py` | Training script | No |
| `src/rootguard/model/infer.py` | Inference script | No |
| `src/rootguard/model/model.pkl` | Trained model binary | **Yes** |
| `docs/models/` | Model documentation | No |

---

## Evaluation Results

| Path | Purpose |
|------|---------|
| `eval/` | Scenario harness, metrics |
| SQLite (WAL) | Decision logs, evaluation results stored locally |

**Note:** Evaluation results are stored in **local SQLite**, NOT Supabase. See `docs/notes/05-database-questions.md`.

---

*End of notes.*
