# Database Questions: SQLite vs Supabase

**Purpose:** Answer whether we need Supabase Postgres or can use local SQLite.

---

## Short Answer

**No, you do not need Supabase.** Use **local SQLite** for all decision logging and evaluation metrics.

---

## Comparison

| Feature | SQLite (local) | Supabase Postgres |
|---------|---------------|-------------------|
| Setup | Zero config, file-based | Requires network, account, API key |
| Internet needed | No | Yes |
| Free-tier limits | None | Yes (storage, requests, pause policy) |
| Pause risk | No | Yes (free tier pauses after inactivity) |
| CRUD operations | Full support via SQLAlchemy | Full support |
| Offline development | Yes | No |
| Research suitability | Perfect | Overkill, adds network dependency |

---

## What Goes in SQLite

| Data | Stored In |
|------|-----------|
| Decision logs (allow/confirm/block) | SQLite |
| Evaluation metrics (accuracy, F1, AUC-ROC) | SQLite |
| Per-provenance results | SQLite |
| Per-pattern results | SQLite |
| Run metadata | SQLite |

---

## What Was Supposed to Go in Supabase

Per original AGENTS.md:
- Table `records` (the dataset itself)

**Updated decision:** Keep `records.jsonl` as a flat file on disk. The dataset is 2,012 rows — small enough to load entirely into memory. No database needed for the dataset either.

---

## Updated AGENTS.md Rule

Replace the Supabase reference:
- **Before:** "Database: Supabase Postgres for records; local SQLite (WAL) for decisions, outcomes, runs"
- **After:** "Database: local SQLite (WAL) for records, decisions, outcomes, runs"

---

## SQLAlchemy Setup

Use **SQLAlchemy 2.0** with SQLite:

```python
from sqlalchemy import create_engine, Column, String, Integer, Boolean, Float, DateTime
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class Decision(Base):
    __tablename__ = "decisions"
    id = Column(String, primary_key=True)
    decision = Column(String)  # allow / confirm / block
    risk_score = Column(Float)
    reason = Column(String)
    source = Column(String)
    timestamp = Column(DateTime)
```

Engine: `sqlite:///data/decisions.db` with WAL mode.

---

*End of notes.*
