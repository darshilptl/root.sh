"""Command line interface for the Root.sh defense layer.

The executable entry point is ``root.sh`` (configured as a console script in
``pyproject.toml``).  It scores one proposed action from the terminal and exits
with a status that encodes the decision: 0 allow, 1 confirm, 2 block, 3 error.
"""

from __future__ import annotations

import argparse
import sys
from typing import Sequence

from rootguard import __version__
from rootguard.model.infer import ScoringError, score_command
from rootguard.authz import Decision

_EXIT_CODES: dict[Decision, int] = {"allow": 0, "confirm": 1, "block": 2}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="root.sh",
        description="Score and authorize one proposed shell action.",
    )
    parser.add_argument("user_request", help="What the user asked for")
    parser.add_argument("proposed_action", help="The shell command the agent wants to run")
    parser.add_argument("source", help="Source: user_direct, file_content, web_content, tool_output, agent_internal")
    parser.add_argument(
        "--version",
        action="version",
        version=f"root.sh {__version__}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI.  Returns an exit code encoding the decision."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        result = score_command(
            user_request=args.user_request,
            proposed_action=args.proposed_action,
            source=args.source,
            save_to_db=True,
        )
    except ScoringError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3

    decision = result["decision"]
    print(
        f"decision={decision} risk_score={result['risk_score']:.3f} "
        f"action_class={result['action_class']} intent_class={result['intent_class']}"
    )
    print(f"  reason: {result['reason']}")
    print(f"  features: {result['features']}")
    print(f"  decision_id: {result.get('decision_id')}")
    return _EXIT_CODES[decision]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
