"""Download the Smart Dublin archive months into .cache/archive (idempotent)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bikes.archive import download_months, resolve_month_urls  # noqa: E402

MONTHS = [f"{y}-{m:02d}" for y in (2024, 2025, 2026) for m in range(1, 13)
          if not (y == 2026 and m > 6)]

if __name__ == "__main__":
    cache = Path(__file__).resolve().parents[1] / ".cache" / "archive"
    urls = resolve_month_urls()
    print(f"resolved {len(urls)} monthly resources; attempting {len(MONTHS)} months")
    missing = [m for m in MONTHS if m not in urls]
    if missing:
        print("not in portal:", ",".join(missing))
    for month in MONTHS:
        if month not in urls:
            continue
        paths = download_months(urls, [month], cache)
        size_mb = paths[month].stat().st_size / 1e6
        print(f"{month}: {size_mb:.1f} MB")
    print("download complete")
