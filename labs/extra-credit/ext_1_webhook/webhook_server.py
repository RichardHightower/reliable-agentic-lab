#!/usr/bin/env python3
"""Extra credit stub. One webhook for ngrok or a DigitalOcean Droplet."""

from __future__ import annotations

import sys


def main() -> int:
    raise NotImplementedError(
        "Extra credit only. Implement POST /github-webhook with signature checks, "
        "then route issues to the groomer, ready labels to the fulfiller, and "
        "failed checks to the fixer. Copy solutions/extra_credit/s_ext_1_webhook/webhook.py if you stall. "
        "Do not skip the Saturday polling labs."
    )


if __name__ == "__main__":
    sys.exit(main())
