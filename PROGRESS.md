# Root.sh — Project Progress

**Project:** Beyond the Chatbox: Provenance-Based Defense Against Irreversible Prompt Injection in OS-Level Autonomous Agents  
**Directory:** `/home/darshil/Desktop/Vs Project/Development/root.sh`  
**Branch:** `fix/pre-phase8-stabilization`  
**Last Updated:** Sun Nov 08 2026

---

## Current Status

**Pre-Phase 8 stabilization in progress** — repairs and gates verified, Phase 8 not yet started.  
**Overall Progress:** Phases 0–4 scaffolded; Phases 5–7 gates require dataset repair/review before they can be considered complete.

---

## Completed Phases

| Phase | Module | Status | Key Deliverable |
|-------|--------|--------|-----------------|
| 0 | Scaffold, data folders | Complete | Folder structure, AGENTS.md, `.gitignore`, `pyproject.toml`, `root.sh` console script |
| 1 | DB schema | Partial | SQLAlchemy models + Alembic migrations; WAL, foreign keys, check constraints; `Decision`/`Outcome`/`Run` tables |
| 2 | Command classifier | Complete | `rootguard/categories.py`: `action_class`, `reversibility`, `scope`, `privilege`, catastrophic predicate; never executes commands |
| 3 | Intent extractor + features | Complete | `rootguard/intent.py` (word-boundary rules + tie-break), `rootguard/features.py` (six canonical features) |
| 4 | NL2Bash converter | Partial | `rootguard/datagen/convert_nl2bash.py`, `data/processed/nl2bash.jsonl` (80 rows) |
| 5 | Dataset generation, review, split freeze | **Blocked** | `data/dataset/records.jsonl` exists (2,012 rows, all unreviewed); counterfactual quartet repair not yet implemented; author review capacity required |
| 6 | Train + evaluate | Partial | `rootguard/model/train.py` updated to new package paths; not re-run against repaired dataset |
| 7 | Daemon + staged authz | Complete | `rootguard/daemon.py`, `rootguard/model/infer.py`, `rootguard/authz.py`; strict validation, default deny, decision logging |

---

## Stabilization repairs (pre-Phase 8, verified 2026-11-08)

- **Packaging:** `pyproject.toml` with `rootguard` package, `"root.sh"` console script, pytest dev dep; `alembic.ini`; installed `uv pip install -e .`; `root.sh --version` → `root.sh 0.7.1`.
- **Safety floor (critical fix):** `user_direct` overreach now blocked: `rm -rf /`, `cat /etc/shadow`, `curl ... | sh`, `scp ~/.ssh/id_rsa`, `chmod 777 /etc/passwd`, `DROP TABLE production_db` all return `block` regardless of model score.
- **Database:** WAL mode, foreign keys, DB-level enum check constraints, `log_decision`/`log_outcome`/`log_run` helpers.
- **Daemon/inference:** single `score_command` service; empty/malformed input and invalid sources → block; missing/corrupt model → block; malformed requests return 200 block (not 422); every decision logged.
- **Tests:** `tests/` — 64 passed (`pytest`).

---

## Blocked / deferred

- Dataset repair/review (Phase 5) requires author's manual review capacity; existing 2,012-row `records.jsonl` is unreviewed and filler-heavy and is not used for training.
- Pyseccomp, AppArmor, and agent-hook verification deferred to Phase 9/10.

---

## Git

- Branch `fix/pre-phase8-stabilization` from clean `main` at `3f7348b`. All stabilization changes uncommitted, pending user sign-off.
- Stale local branches `feature/daemon-authz`, `feature/model-training` remain unmerged.
