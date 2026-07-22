"""Nightly scoring entry point (VM cron, 23:45 UTC)."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))  # bikes.score imports the scoring/ package

from bikes.score import evaluate_gate, score_ledger, write_summary  # noqa: E402


def main() -> None:
    now = datetime.now(timezone.utc)
    counts = score_ledger(ROOT / "ledger", ROOT / "data" / "raw", now)
    write_summary(ROOT / "ledger")
    evaluate_gate(ROOT / "ledger")
    print(f"scored={counts['scored']} gap={counts['gap']} "
          f"excluded={counts['excluded']}")


if __name__ == "__main__":
    main()
