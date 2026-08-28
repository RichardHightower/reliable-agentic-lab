#!/usr/bin/env python3
"""Extra credit 1 stub launcher.

Fill this file yourself, or run the filled answer:

    python -m uvicorn solutions.extra_credit.s_ext_1_webhook.webhook:app \\
        --host 127.0.0.1 --port 8000

The Droplet unit file uses that module. This launcher does the same so
`python labs/extra-credit/ext_1_webhook/webhook_server.py` still works.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from solutions.extra_credit.s_ext_1_webhook.webhook import app, main  # noqa: E402

__all__ = ["app", "main"]


if __name__ == "__main__":
    sys.exit(main())
