"""Capture final pre-election forecast data that its publishers offer as downloads.

Split Ticket publishes its 2026 model through Datawrapper charts with "Get the data" enabled.
Datawrapper keeps every published version at /<chart>/<version>/dataset.csv with a Last-Modified
header, so we take the LAST version modified before election day 06:00 ET. That is the final
pre-election forecast even if the chart is republished later.

    uv run python -m mp.ingest.snapshot
"""

from __future__ import annotations

import json
import re
from email.utils import parsedate_to_datetime
from pathlib import Path

import httpx

from mp.ingest._http import PoliteClient, sha256, utc_now

CUTOFF = "2026-11-03T11:00:00+00:00"
DW = "https://datawrapper.dwcdn.net"
# Charts embedded in theargumentmag.com/p/split-ticket-2026-midterms-model (Nov 3 Wayback capture).
SPLIT_TICKET_CHARTS = {
    "g4hHM": ("SEN", "race table"),
    "Hus3x": ("SEN", "race map"),
    "toEMi": ("SEN-CONTROL", "chamber control probability"),
    "u9EZf": ("HOU", "district table"),
    "Cy0fK": ("HOU", "district map"),
    "5UEYH": ("HOU-CONTROL", "chamber control probability"),
}
OUT = Path("data/raw/forecasts/splitticket")


def latest_version(client: PoliteClient, chart: str) -> int:
    stub = client.get(f"{DW}/{chart}/").text
    m = re.search(rf"{DW}/{chart}/(\d+)/", stub)
    if not m:
        raise RuntimeError(f"no version redirect for {chart}")
    return int(m.group(1))


def final_before_cutoff(client: PoliteClient, chart: str, cutoff: str = CUTOFF) -> tuple[int, str, str]:
    """(version, last_modified_iso, csv_text) of the last version modified before `cutoff`."""
    from datetime import datetime

    cut = datetime.fromisoformat(cutoff)
    for v in range(latest_version(client, chart), 0, -1):
        try:
            r = client.get(f"{DW}/{chart}/{v}/dataset.csv")
        except httpx.HTTPStatusError:
            continue
        lm = parsedate_to_datetime(r.headers["last-modified"])
        if lm <= cut:
            return v, lm.isoformat(), r.text
    raise RuntimeError(f"no pre-cutoff version for {chart}")


def capture_split_ticket(out: Path = OUT) -> Path:
    client = PoliteClient(min_interval=1.0)
    out.mkdir(parents=True, exist_ok=True)
    meta = {}
    for chart, (office, desc) in SPLIT_TICKET_CHARTS.items():
        v, lm, text = final_before_cutoff(client, chart)
        f = f"{chart}_v{v}.csv"
        (out / f).write_text(text)
        meta[chart] = {"office": office, "description": desc, "version": v, "last_modified": lm, "file": f,
                           "url": f"{DW}/{chart}/{v}/dataset.csv", "sha256": sha256(text), "fetched_at": utc_now()}
        print(f"{chart} ({desc}): v{v}, modified {lm}")
    (out / "meta.json").write_text(json.dumps(meta, indent=1))
    return out / "meta.json"


if __name__ == "__main__":
    capture_split_ticket()
