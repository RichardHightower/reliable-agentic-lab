from __future__ import annotations

import sys

HELP = """usage: python -m solutions.loops <enhancer|implementer|fixer> [args]

Working PRD loops. No API key required.
"""


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in {"-h", "--help"}:
        print(HELP)
        return 0
    target = sys.argv[1]
    sys.argv = [sys.argv[0], *sys.argv[2:]]
    if target == "enhancer":
        from .enhancer import main as run
    elif target == "implementer":
        from .implementer import main as run
    elif target == "fixer":
        from .fixer import main as run
    else:
        print(HELP, file=sys.stderr)
        return 2
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
