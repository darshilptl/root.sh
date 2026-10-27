# Root.sh: Agent Instructions

## 1. What this is

Research project (M.Tech dissertation), not a product.
**Beyond the Chatbox: A Boundary Study of Provenance-Based Defense Against Irreversible Prompt Injection in OS-Level Autonomous Agents.**
Question: do known defenses (source tagging, isolation, capability checks) hold for agents that run real OS commands, where mistakes are irreversible, and where do they fail?
Wording: write "defense layer" or "scoring algorithm", never "tool" or "product".
Honesty: this measures a defense. It does not claim to solve prompt injection. Never invent results.

## 2. What we build

A defense layer that sits beside an agent. For each proposed command it receives `(user_request, proposed_action, source)` and returns allow / confirm / block, a risk score and a reason.
1. LightGBM classifier over six features. No LLM judges an LLM.
2. Staged authorization, default deny.
3. seccomp + AppArmor, which block catastrophic classes of actions even if 1-2 fail.

Scope: Linux only (Ubuntu 26.04), agents with direct command execution. Out: chat, GUI and payment agents.

## 3. Runtime flow

```
agent proposes command -> hook -> POST /score {user_request, proposed_action, source}
 -> classify action (action_class, reversibility, scope, privilege)
 -> extract intent_class from the request (rules)
 -> six features -> LightGBM score -> staged authz -> allow | confirm | block
 -> seccomp / AppArmor backstop -> log (SQLite)
```
Any error, missing model or malformed input means **block**.

## 4. Logic

Features (exactly these, in this order):

| # | Feature | Value |
|---|---|---|
| 1 | source_trusted | 1 if source == user_direct else 0 |
| 2 | intent_match | 1 match, 0 mismatch, -1 unknown. Rule table: request intent_class vs action_class, plus a small compatibility table |
| 3 | target_in_request | fraction of the action's path/target tokens present in the request; -1 if the action has no target |
| 4 | reversibility | 0 reversible, 1 irreversible |
| 5 | scope | 0 single file/process, 1 folder/multi-file, 2 system-wide |
| 6 | privilege | 0 user, 1 root |

- Decision (initial values, tune by CV on train only): score < 0.3 allow; 0.3-0.7 confirm; > 0.7 block. Show it as a "risk score", not a probability (uncalibrated).
- Staged authz (pure functions): scope -> authorization -> impact ceiling -> repeat -> default deny.
- Baselines to report: majority class; categories-only rule; hand-written rule on the same features; request-only text classifier (must stay near chance: style-leak audit).

## 5. Dataset

Table `records` (local JSONL + SQLite):

| Field | Values |
|---|---|
| id | uuid v4 |
| family_id | `<pattern>-NNN`; twins `<pattern>-safe-NNN` |
| twin_of | family_id or null (symmetric) |
| user_request | text |
| intent_class | 17 values, describes the request, never the action: list_read, search, create, modify_file, copy, move_rename, delete, archive_compress, remote_transfer, install, run_build_test, network_fetch, modify_environment, permission_change, process_control, database_change, other |
| source | user_direct, file_content, web_content, tool_output, agent_internal |
| injected_text | text or null |
| proposed_action | text |
| label | safe or risky |
| reasoning | text |
| provenance | seed, generated, nl2bash |
| generator | model name or null |
| split | train or heldout |
| reviewed | bool |
| created_at | timestamp |

- `label=safe` means the action matches the request and the source is user_direct, even if the command is dangerous.
- Not stored, computed by code: action_class, reversibility, scope, privilege, features.
- Composition v1: 7 patterns (env-poison, param-escape, file-injection, halluc-destructive, agent-deviation, priv-escalation, exfil-remote-exec). Per pattern 13 risky + 7 safe-twin families, 4 rows each (1 seed head + 3 generated variants) = 560 rows, plus about 80 NL2Bash rows (safe, one row per family). Total about 640.
- Split: by family_id, never by row. Within each pattern, sort family_ids by sha256 and take the first 20% as heldout (same rule for NL2Bash). Freeze in `data/dataset/families.json`.
- Train only on reviewed families. Heldout is evaluated once per run. Report results per provenance.
- NL2Bash: `git clone https://github.com/TellinaTool/nl2bash.git data/external/nl2bash`; use `data/bash/all.nl` and `all.cm` (line-aligned). Dedupe by request, keep commands the classifier parses confidently, cap rows per utility.
- Seeds, variants and twins are drafted by an offline agent and reviewed by the author.

## 6. Folder structure

```
root.sh/
├── AGENTS.md  pyproject.toml  .gitignore  summary.md
├── .venv/                 # Python virtual environment (uv venv .venv)
├── docs/
│   ├── modules/           # NN-name.md, one per phase
│   ├── notes/             # fundamentals notes (pure markdown)
│   ├── datasets/          # dataset info
│   ├── models/            # model info
│   ├── summaries/         # summaries
│   └── BLOCKERS.md
├── data/
│   ├── external/          # raw third-party (gitignored): nl2bash/
│   ├── processed/         # converted external data: nl2bash.jsonl
│   ├── staging/           # agent-generated rows awaiting review
│   ├── dataset/           # records.jsonl (reviewed), families.json (frozen split)
│   ├── review/            # spot_check.csv
│   └── LICENSES.md
├── src/root.sh/           # All source code
│   ├── __init__.py
│   ├── config.py daemon.py authz.py features.py intent.py categories.py
│   ├── db/                # models.py, migrations/
│   ├── datagen/           # schema.py, convert_nl2bash.py, importer.py
│   ├── model/             # train.py, infer.py, model.pkl (gitignored)
│   ├── enforce/           # seccomp.py, apparmor/
│   ├── integrations/      # hook adapters
│   └── cli/               # app.py, commands/, ui/
├── sandbox/               # synthetic files for attack scenarios
├── eval/                  # scenario harness, metrics
└── tests/
```

## 7. Tech stack

| Area | Choice |
|---|---|
| Language | Python 3.11+, uv |
| Daemon | FastAPI + uvicorn |
| CLI / TUI | Typer + Rich (v1) |
| ML | LightGBM, scikit-learn, pandas, numpy. No embeddings, no torch |
| Database | local SQLite (WAL) for records, decisions, outcomes, runs; SQLAlchemy 2 + Alembic |
| Enforcement | seccomp, AppArmor |
| Integrations | OpenCode plugin and Claude Code hook (adapters only) |
| Tests | pytest |

## 8. Phases (build order, each ends with its gate)

| # | Module | Gate |
|---|---|---|
| 0 | Scaffold, data folders | pytest passes; `root.sh --version` runs; folders exist |
| 1 | DB schema | migrations run on SQLite; invalid enum rejected by the DB |
| 2 | Command classifier | 40+ table tests pass; unknown commands never rated safe |
| 3 | Intent extractor + features | deterministic; extractor accuracy on labeled rows reported |
| 4 | NL2Bash converter + validator + import | equal line counts; 0 schema failures; duplicates removed |
| 5 | Dataset generation, review, split freeze | 600-800 rows; label balance 40-60%; request-only audit near chance; heldout fully reviewed; families.json hash recorded |
| 6 | Train + evaluate | zero family overlap; heldout evaluated once; baselines and per-provenance results saved |
| 7 | Daemon + staged authz | malformed input or missing model returns block; every call logged |
| 8 | Scenario harness + evaluation run | undefended lets each attack through; defended blocks or confirms; metrics from the DB only |
| 9 | Kernel enforcement | denied syscall fails inside the sandbox; AppArmor profile loaded |
| 10 | Agent integrations | hook behavior verified from official docs; a blocked action does not run |
| 11 | CLI, TUI, report | init preserves an existing CLAUDE.md/AGENTS.md; report numbers equal direct DB queries |

Per phase: create the branch (section 9) -> write `docs/modules/NN-name.md` (no code) -> audit it against this file -> stop for "APPROVED NN" -> implement -> **user verifies by hand** -> run the gate -> agent commits only after user approval -> write the PR title and description (section 9) -> stop for "NEXT".

## 9. Git workflow (trunk-based, solo)

1. **Default branch is `main`.** Never create or use `master`. New repo: `git init -b main`, and check that `git config --global init.defaultBranch` returns `main`. If a repo still uses `master`, stop and ask, and do not rename remote branches.
2. **Trunk-based, no `dev` branch.** Only `main` plus short-lived branches merged straight into `main`. `main` always passes its phase gates.
3. **Branch names are `prefix/short-description`.** `feature/` for new functionality, `setup/` or `chore/` for scaffolding and tooling, `fix/` for bug fixes, `refactor/` for no behavior change, `hotfix/` for an urgent fix branched from `main`. Phase 0 uses `setup/project-init`, and every other phase uses `feature/<module>` (for example `feature/db-schema`).
4. **One branch = one concern = one phase.** Never mix concerns, for example the classifier and the daemon. A change that spans modules but is one logical unit stays on one branch.
5. **Start from an up-to-date `main`:** `git checkout main`, then `git pull` if a remote exists, then `git checkout -b feature/<module>`.
6. **Keep branches short-lived.** Merge within days. If `main` changed since branching, report it, merge `main` into the branch and rerun the gate. Never force-push or rebase published commits.
7. **Commit small and often, and never in a broken state.** Use Conventional Commits: `type(scope): imperative subject`, 72 characters or fewer, no period. Types: `feat fix refactor test docs chore build perf`. The body explains why, and the footer is `Refs: docs/modules/NN-name.md`. Example: `feat(db): add SQLAlchemy schema and initial Alembic migration`.
8. **Commit only after user verification.** Agent implements phase -> user verifies by hand -> agent commits only after explicit user approval. Never commit before user sign-off.
9. **Merge through a PR into `main`, even solo, using squash and merge.** The PR title is the commit subject. The description covers what changed, the gate results and open items. Mark unfinished work as a draft PR, and merge only when checks are green. If there is no remote, the author runs `git merge --squash` locally with the same subject.
9. **The pre-merge checklist replaces a `dev` branch.** Tests pass, lint passes (if configured), the smoke test passes, the phase gate in section 8 passed with real output, and `git status` is clean. No ignored or secret files are committed (`data/external/`, `*.db`, `model.pkl`, `.env`, `.venv/`).
10. **Tag every stable release on `main`:** `v0.N.0` after phase N merges. To roll back, revert the squash commit or check out the tag.
11. **Agents and the author split the steps.** Agents branch, commit, push the feature branch (if a remote exists), write the PR title and description, and stop. The author merges and tags. After the author confirms the merge, the agent deletes the local branch with `git branch -d`, or `-D` after a squash merge because git doesn't see it as merged.

## 10. Rules

1. Default deny: any error, missing model, malformed or inconclusive input means block.
2. No LLM scores or judges commands. Agents are used offline to draft dataset rows only.
3. Never train, tune or build features on heldout. Split by family_id.
4. Never execute generated commands. Real destructive commands run only inside `sandbox/`, as an unprivileged user.
5. Python owns the schema. No network calls in scoring code.
6. No new dependencies, tables, features or files outside this map without asking.
7. Never guess versions, flags, URLs or package names: check them, and record the result in `docs/BLOCKERS.md`.
8. If a requirement is ambiguous, list it under "Open questions" in the module doc and stop.
9. Never overwrite a user's CLAUDE.md or AGENTS.md; append a marked section.
10. Never merge into or push to `main`. Never tag, force-push or use `--no-verify`.
11. Small pure functions, type hints, no global state, tests per module, seed 42.
12. Report only results from eval runs stored in the DB.

## 11. VERIFY before use

- pyseccomp availability on Ubuntu 26.04 (apt lacked it earlier)
- SQLite driver availability and WAL mode support
- Claude Code hook behavior and the OpenCode plugin API (`tool.execute.before`, `permission.ask`), from official docs
- How each agent exposes the user's original request at hook time

## 12. uv & Virtual Environment Setup

### Create virtual environment

```bash
cd /home/darshil/Desktop/Vs Project/Development/root.sh
uv venv .venv
```

### Activate virtual environment

```bash
# Linux/macOS:
source .venv/bin/activate

# Windows:
.venv\Scripts\activate
```

### Install dependencies

```bash
uv pip install lightgbm scikit-learn pandas numpy sqlalchemy alembic fastapi uvicorn
```

### Save exact versions

```bash
uv pip freeze > requirements.txt
```

### Run Python with .venv

```bash
uv run python src/root.sh/model/train.py
```

### Why .venv?

- Isolates Root.sh dependencies from system Python
- Reproducible: `uv pip install -r requirements.txt` recreates same environment
- Clean: delete `.venv` folder to start fresh
- `uv venv .venv` creates it — uv does not auto-create without this command
