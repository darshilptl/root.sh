"""Allow ``python -m rootguard`` to behave like the ``root.sh`` command."""

from __future__ import annotations

from rootguard.cli import main

if __name__ == "__main__":  # pragma: no cover - exercised by the CLI test
    raise SystemExit(main())
