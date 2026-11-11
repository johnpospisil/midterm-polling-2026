"""Race registry: data/reference/races.csv (one row per 2026 Senate, governor, House race + generic ballot).

Nominees come from each statewide page's election-eve infobox; House nominees from Split Ticket's
final district table (names as of 2026-11-03). The "principals" are the two candidates whose
margin we score: the D side (the Democrat, or the independent where no Democrat runs, e.g.
NE Senate) and the R side. Where a party has several nominees (Alaska top-4), the principal is
the one appearing most often in general-election poll headers.

    uv run python -m mp.build.races
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path

from bs4 import BeautifulSoup

from mp.geo import STATES
from mp.ingest.aggregators import (
    clean,
    nominees_from_infobox,
    parse_splitticket,
    party_of,
    table_grid,
)
from mp.ingest.wikipedia_polls import section_path
from mp.names import NomineeMatcher

STATE_NAME = {v: k for k, v in STATES.items()}
FIELDS = ["race_id", "office", "state", "district", "special", "d_side_name", "d_side_party",
          "r_side_name", "nominee_placeholder", "nominees", "rcv", "top_two", "top_four", "replacement_note",
          "consensus_rating", "n_raters", "nominee_source", "source_url"]
# Split Ticket probabilities/margins are NOT written here: races.csv is committed to the public
# repo and our terms rule forbids bulk redistribution (they stay in final_forecasts.parquet).


def choose_principals(nominees: dict[str, str], header_counts: dict[str, int]) -> tuple:
    """(d_side_name, d_side_party, r_side_name); D side = Democrat, else independent."""

    def pick(party):
        c = [n for n, p in nominees.items() if p == party]
        return max(c, key=lambda n: header_counts.get(n, 0)) if c else None

    r = pick("R")
    d = pick("D")
    d_party = "D"
    if d is None:
        d, d_party = pick("I"), "I"
    if d is None or r is None:
        return None, None, None
    return d, d_party, r


def flags_for(office: str, state: str) -> dict[str, bool]:
    return {
        "rcv": state == "AK" or (state == "ME" and office in ("SEN", "HOU")),
        "top_two": state in ("CA", "WA"),
        "top_four": state == "AK",
    }


def replacement_notes(html: str) -> list[str]:
    ib = BeautifulSoup(html, "lxml").select_one("table.infobox")
    if ib is None:
        return []
    out = []
    for td in ib.find_all("td"):
        if td.find("table"):
            continue
        t = clean(td.get_text(" "))
        if m := re.match(r"^(.*?)\s*\(\s*(replacing [^)]*?)\s*\)$", t):
            out.append(f"{m.group(1)} {m.group(2)}")
    return sorted(set(out))


def _ge_header_counts(html: str, nominees: dict[str, str]) -> dict[str, int]:
    """How often each nominee appears as a column in general-election poll tables."""
    m = NomineeMatcher(nominees)
    counts: Counter = Counter()
    for t in BeautifulSoup(html, "lxml").select("table.wikitable"):
        g = table_grid(t)
        if not g or not clean(g[0][0].get_text(" ")).lower().startswith("poll source"):
            continue
        if re.search(r"primary|convention|lieutenant", " > ".join(section_path(t)), re.IGNORECASE):
            continue
        for c in g[0][4:]:
            hit = m.match(party_of(clean(c.get_text(" ")))[0])
            if hit:
                counts[hit[0]] += len(g) - 1
    return dict(counts)


RATING_SCALE = {"Safe D": -4, "Likely D": -3, "Lean D": -2, "Tilt D": -1, "Tossup": 0,
                "Tilt R": 1, "Lean R": 2, "Likely R": 3, "Safe R": 4}
_SCALE_NAME = {v: k for k, v in RATING_SCALE.items()}


def consensus_rating(ratings: list[str]) -> str | None:
    """Most common rating across raters. A tie goes to the tied rating nearest the median
    rating; if two are equally near (e.g. Lean D vs Lean R), the median itself. Symmetric
    for both parties and independent of input order."""
    vals = sorted(RATING_SCALE[r] for r in ratings if r in RATING_SCALE)
    if not vals:
        return None
    counts = {v: vals.count(v) for v in set(vals)}
    top = max(counts.values())
    tied = sorted(v for v, c in counts.items() if c == top)
    if len(tied) == 1:
        return _SCALE_NAME[tied[0]]
    n = len(vals)
    median = (vals[(n - 1) // 2] + vals[n // 2]) / 2
    dist = {v: abs(v - median) for v in tied}
    nearest = [v for v in tied if dist[v] == min(dist.values())]
    if len(nearest) == 1:
        return _SCALE_NAME[nearest[0]]
    return _SCALE_NAME[int(median)]  # int() truncates toward Tossup


def build(manifest: Path = Path("data/raw/wikipedia/manifest.csv"),
          forecasts: Path = Path("data/processed/final_forecasts.parquet"),
          st_meta: Path = Path("data/raw/forecasts/splitticket/meta.json"),
          out: Path = Path("data/reference/races.csv")) -> Path:
    import polars as pl

    fc = pl.read_parquet(forecasts)
    ratings = fc.filter(pl.col("kind") == "rating")
    consensus = {r["race_id"]: (consensus_rating(r["rating"]), r["n"]) for r in ratings.group_by(
        "race_id").agg(pl.col("rating"), pl.len().alias("n")).to_dicts()}

    rows = []
    pre = [r for r in csv.DictReader(manifest.open())
           if r["which"] == "pre_election" and r["page_kind"] in ("senate", "governor")]
    for r in sorted(pre, key=lambda x: x["race_id"]):
        html = Path(r["path_html"]).read_text()
        office, state = r["race_id"].split("-")[:2]
        nominees = nominees_from_infobox(html)
        d, dp, rep = choose_principals(nominees, _ge_header_counts(html, nominees))
        rows.append({
            "race_id": r["race_id"], "office": office, "state": state, "district": "",
            "special": r["special"] == "True", "d_side_name": d, "d_side_party": dp, "r_side_name": rep,
            "nominee_placeholder": False,
            "nominees": json.dumps(nominees), **flags_for(office, state),
            "replacement_note": "; ".join(replacement_notes(html)),
            "consensus_rating": consensus.get(r["race_id"], (None, 0))[0],
            "n_raters": consensus.get(r["race_id"], (None, 0))[1],
            "nominee_source": f"Wikipedia infobox, revid {r['revid']}", "source_url": r["url"],
        })

    meta = json.loads(st_meta.read_text())
    chart = next(k for k, v in meta.items() if v["office"] == "HOU")
    for x in parse_splitticket((st_meta.parent / meta[chart]["file"]).read_text(), "HOU"):
        office, rest = x["race_id"].split("-")[:2]
        state, dist = rest[:2], rest[2:]
        dname, rname = x["dem_name"], x["rep_name"]
        dparty = "I" if re.search(r"\((Ind|I)\)", dname) else "D"
        dname = re.sub(r"\s*\(.*?\)", "", dname).strip()
        rname = re.sub(r"\s*\(.*?\)", "", rname).strip()
        rows.append({
            "race_id": x["race_id"], "office": "HOU", "state": state, "district": dist, "special": False,
            "d_side_name": dname, "d_side_party": dparty, "r_side_name": rname,
            # Split Ticket's final table still says "Eventual Nominee" where no nominee was set
            "nominee_placeholder": "eventual nominee" in f"{dname} {rname}".lower(),
            "nominees": json.dumps({dname: dparty, rname: "R"}), **flags_for("HOU", state),
            "replacement_note": "", "consensus_rating": x["rating"], "n_raters": 1,
            "nominee_source": f"Split Ticket district table {chart} v{meta[chart]['version']}",
            "source_url": meta[chart]["url"],
        })
    rows.append({
        "race_id": "GEN-US-2026", "office": "GEN", "state": "US", "district": "", "special": False,
        "d_side_name": "Democratic", "d_side_party": "D", "r_side_name": "Republican",
        "nominee_placeholder": False,
        "nominees": json.dumps({"Democratic": "D", "Republican": "R"}), "rcv": False,
        "top_two": False, "top_four": False, "replacement_note": "", "consensus_rating": None,
        "n_raters": 0,
        "nominee_source": "generic ballot", "source_url": "",
    })
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    return out


if __name__ == "__main__":
    p = build()
    print(p)
