"""Scheduler entry point for a saved lens.

Examples:
    python scripts/run_saved_lens.py hospital

Use this command from Windows Task Scheduler, cron, or another local runner.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from main import run  # noqa: E402


if len(sys.argv) != 2:
    raise SystemExit("usage: python scripts/run_saved_lens.py LENS_NAME")

print(run(lens_name=sys.argv[1]))
