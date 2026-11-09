"""2026 poll tables from Wikipedia (CC BY-SA 4.0).

Fetch mode (P02) freezes, for every 2026 Senate, governor, House and overview page, the last
revision before election day 06:00 ET and the current revision. Raw parse HTML and wikitext are
saved under data/raw/wikipedia/<page_slug>/<revid>.{html,wikitext}, with a manifest.csv.

    uv run python -m mp.ingest.wikipedia_polls fetch
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from mp.geo import STATES, race_id
from mp.ingest._http import PoliteClient, sha256, utc_now

API = "https://en.wikipedia.org/w/api.php"
PRE_ELECTION_CUTOFF = "2026-11-03T11:00:00Z"  # 06:00 ET on election day
RAW_DIR = Path("data/raw/wikipedia")
MANIFEST_FIELDS = [
    "title", "page_kind", "race_id", "special", "which", "revid", "rev_timestamp",
    "fetched_at", "sha256_html", "sha256_wikitext", "path_html", "url",
]
OVERVIEW_PAGES = {
    "2026 United States Senate elections": ("overview_senate", None),
    "2026 United States gubernatorial elections": ("overview_governor", None),
    # The House overview page carries the generic-ballot polls and averages.
    "2026 United States House of Representatives elections": ("overview_house", "GEN-US-2026"),
}

_SEN = re.compile(r"^2026 United States Senate (special )?election in (.+)$")
_GOV = re.compile(r"^2026 (.+) gubernatorial election$")
_HOU = re.compile(r"^2026 United States House of Representatives elections? in ([A-Za-z ]+?)( \(districts .*\))?$")


@dataclass(frozen=True)
class Page:
    title: str
    page_kind: str  # senate | governor | house_state | overview_*
    race_id: str | None
    special: bool = False


def classify(title: str) -> Page | None:
    """Map a Wikipedia title to a page kind and race id; None if it isn't a US 2026 race page."""
    if title in OVERVIEW_PAGES:
        kind, rid = OVERVIEW_PAGES[title]
        return Page(title, kind, rid)
    if m := _SEN.match(title):
        st = STATES.get(m.group(2))
        return Page(title, "senate", race_id("SEN", st), bool(m.group(1))) if st else None
    if m := _GOV.match(title):
        st = STATES.get(m.group(1))
        return Page(title, "governor", race_id("GOV", st)) if st else None
    if m := _HOU.match(title):
        st = STATES.get(m.group(1))
        return Page(title, "house_state", None) if st else None
    return None


def slug(title: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", title).strip("_")


def discover_pages(client: PoliteClient) -> list[Page]:
    queries = [
        'intitle:"2026 United States Senate" election',
        'intitle:"2026" intitle:"gubernatorial election"',
        'intitle:"2026 United States House of Representatives"',
    ]
    titles: set[str] = set(OVERVIEW_PAGES)
    for q in queries:
        offset = 0
        while offset is not None:
            r = client.get(API, params={"action": "query", "list": "search", "srsearch": q, "srlimit": 100,
                                            "sroffset": offset, "format": "json"}).json()
            titles.update(x["title"] for x in r["query"]["search"])
            offset = r.get("continue", {}).get("sroffset")
    pages = [p for t in sorted(titles) if (p := classify(t))]
    return pages


def revision_at(client: PoliteClient, title: str, before: str | None) -> dict | None:
    """Latest revision at or before `before` (ISO UTC), or the current revision if None."""
    params = {"action": "query", "prop": "revisions", "titles": title, "rvlimit": 1,
                  "rvprop": "ids|timestamp", "format": "json", "formatversion": 2}
    if before:
        params.update(rvstart=before, rvdir="older")
    page = client.get(API, params=params).json()["query"]["pages"][0]
    revs = page.get("revisions")
    return revs[0] if revs else None


def fetch_revision(client: PoliteClient, page: Page, which: str, rev: dict, root: Path) -> dict:
    d = root / slug(page.title)
    d.mkdir(parents=True, exist_ok=True)
    html_p, wt_p = d / f"{rev['revid']}.html", d / f"{rev['revid']}.wikitext"
    if not (html_p.exists() and wt_p.exists()):
        r = client.get(API, params={"action": "parse", "oldid": rev["revid"], "prop": "text|wikitext",
                                        "format": "json", "formatversion": 2}).json()["parse"]
        html_p.write_text(r["text"])
        wt_p.write_text(r["wikitext"])
    return {
        "title": page.title, "page_kind": page.page_kind, "race_id": page.race_id or "",
        "special": page.special, "which": which, "revid": rev["revid"], "rev_timestamp": rev["timestamp"],
        "fetched_at": utc_now(), "sha256_html": sha256(html_p.read_bytes()),
        "sha256_wikitext": sha256(wt_p.read_bytes()), "path_html": str(html_p),
        "url": f"https://en.wikipedia.org/w/index.php?oldid={rev['revid']}",
    }


def fetch_all(root: Path = RAW_DIR) -> Path:
    client = PoliteClient(min_interval=1.0)
    root.mkdir(parents=True, exist_ok=True)
    manifest = root / "manifest.csv"
    done = set()
    if manifest.exists():
        with manifest.open() as f:
            done = {(r["title"], r["which"]) for r in csv.DictReader(f)}
    pages = discover_pages(client)
    print(f"{len(pages)} pages: " + ", ".join(
        f"{k}={sum(p.page_kind == k for p in pages)}" for k in sorted({p.page_kind for p in pages})))
    new_file = not manifest.exists()
    with manifest.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        if new_file:
            w.writeheader()
        for i, page in enumerate(pages, 1):
            for which, before in (("pre_election", PRE_ELECTION_CUTOFF), ("current", None)):
                if (page.title, which) in done:
                    continue
                rev = revision_at(client, page.title, before)
                if rev is None:
                    print(f"  [{i}/{len(pages)}] {page.title}: no {which} revision", file=sys.stderr)
                    continue
                w.writerow(fetch_revision(client, page, which, rev, root))
                f.flush()
            print(f"  [{i}/{len(pages)}] {page.title}")
    return manifest


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode", choices=["fetch"])
    ap.add_argument("--root", type=Path, default=RAW_DIR)
    a = ap.parse_args(argv)
    if a.mode == "fetch":
        print("manifest:", fetch_all(a.root))


if __name__ == "__main__":
    main()
