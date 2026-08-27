#!/usr/bin/env python3
"""Extra credit stub. Fill this. Polling labs stay the Saturday path."""

from __future__ import annotations

import argparse
import os
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issue", default=os.environ.get("ISSUE_NUMBER", "T001"))
    parser.parse_args()
    raise NotImplementedError(
        "Extra credit only. Implement GitHub Actions grooming here, "
        "or copy solutions/extra_credit/s_ext_3_groom_ticket/groom_ticket.py. "
        "Do not skip the Saturday polling labs."
    )


if __name__ == "__main__":
    sys.exit(main())
