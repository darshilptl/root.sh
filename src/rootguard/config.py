"""Central configuration and path resolution for rootguard.

All paths are resolved from this file, never from the current working
directory. Environment variables allow tests and the daemon to point at
temporary databases or model files without changing source code.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
DATA_DIR: Path = PROJECT_ROOT / "data"

DATASET_PATH: Path = Path(
    os.environ.get("ROOTGUARD_DATASET_PATH", DATA_DIR / "dataset" / "records.jsonl")
)
MODEL_PATH: Path = Path(
    os.environ.get(
        "ROOTGUARD_MODEL_PATH",
        PROJECT_ROOT / "src" / "rootguard" / "model" / "model.pkl",
    )
)
DB_PATH: Path = Path(
    os.environ.get("ROOTGUARD_DB_PATH", DATA_DIR / "decisions.db")
)
DB_URL: str = f"sqlite:///{DB_PATH}"

FEATURE_COLUMNS: tuple[str, ...] = (
    "source_trusted",
    "intent_match",
    "target_in_request",
    "reversibility",
    "scope",
    "privilege",
)

ALLOW_THRESHOLD: float = 0.3
CONFIRM_THRESHOLD: float = 0.7

MAX_TEXT_LENGTH: int = 4096


def ensure_parent(path: Path) -> None:
    """Create the parent directory for *path* if it does not exist."""
    path.parent.mkdir(parents=True, exist_ok=True)
