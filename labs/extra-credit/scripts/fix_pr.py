#!/usr/bin/env python3
"""Extra credit stub. Fill this. Polling labs stay the Saturday path."""
from __future__ import annotations

import argparse
import os
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pr", default=os.environ.get("PR_NUMBER", "T001"))
    parser.parse_args()
    raise NotImplementedError(
        "Extra credit only. Implement GitHub Actions PR repair here, "
        "or copy solutions/extra_credit/fix_pr.py. "
        "Do not skip the Saturday polling labs."
    )


if __name__ == "__main__":
    sys.exit(main())
