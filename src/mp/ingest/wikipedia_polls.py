"""2026 poll tables from Wikipedia (CC BY-SA 4.0).

Fetch mode (P02) freezes, for every 2026 Senate, governor, House and overview page, the last
revision before election day 06:00 ET and the current revision. Raw parse HTML and wikitext are
saved under data/raw/wikipedia/<page_slug>/<revid>.{html,wikitext}, with a manifest.csv.

Parse mode (P03) turns general-election poll tables into one row per table row as published
(variants such as LV/RV or RCV rounds stay separate rows sharing a `poll_group`). A table is kept
only if both principal nominees (D side, R side) are among its candidate columns, which drops
primaries and hypothetical matchups. Every skipped table is logged with a reason.

    uv run python -m mp.ingest.wikipedia_polls fetch
    uv run python -m mp.build.races          # races.csv (needed by parse)
    uv run python -m mp.ingest.wikipedia_polls parse
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
    # The House overview page carries the generic-ballot aggregator averages (not the polls).
    "2026 United States House of Representatives elections": ("overview_house", "GEN-US-2026"),
    # Generic-ballot polls live in this template (split out of the elections article in Sept 2026;
    # the "2026 United States elections polling" page that transcludes it was created Nov 5).
    "Template:2026 United States elections/polling": ("generic_ballot", "GEN-US-2026"),
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


# ------------------------------------------------------------------------------------- parse (P03)

_MONTH = r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?"
_DAY_PART = re.compile(rf"^\s*(?:{_MONTH}\s+)?(\d{{1,2}})(?:,\s*(\d{{4}}))?\s*$")
_NON_CANDIDATE = re.compile(
    r"^(other|undecided|lead|margin|none|neither|would not vote|refused|don.?t know|not sure|"
    r"someone else|no opinion|wouldn.?t vote)", re.IGNORECASE)
_SKIP_SECTION = re.compile(r"primary|convention|caucus|lieutenant|nominating", re.IGNORECASE)


def parse_sample(text: str) -> tuple[int | None, str | None]:
    """'1,326 (LV)' -> (1326, 'LV'); '— (LV)' -> (None, 'LV')."""
    pop = re.search(r"\(([A-Za-z/ ]+)\)", text)
    n = re.match(r"\s*([\d,]+)", text)
    return (int(n.group(1).replace(",", "")) if n and n.group(1).replace(",", "") else None,
            pop.group(1).replace(" ", "") if pop else None)


def parse_moe(text: str) -> float | None:
    m = re.search(r"\d+(?:\.\d+)?", text)
    return float(m.group()) if m else None


def _month_num(tok: str) -> int:
    return ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"].index(
        tok[:3].lower()) + 1


_MONTH_ONLY = re.compile(rf"^\s*{_MONTH}\s+(\d{{4}})\s*$")


def parse_field_dates(text: str) -> tuple[str | None, str | None]:
    """Field dates as ISO (start, end). Handles 'Oct 26–29, 2026', 'Oct 31 – Nov 1, 2026',
    'Dec 28, 2025 – Jan 3, 2026', single dates, a missing comma before the year, any dash or
    minus sign, and month-only dates ('April 2026' -> whole month)."""
    import calendar

    if m := _MONTH_ONLY.match(text):
        mon, yr = _month_num(m.group(1)), int(m.group(2))
        last = calendar.monthrange(yr, mon)[1]
        return f"{yr:04d}-{mon:02d}-01", f"{yr:04d}-{mon:02d}-{last:02d}"
    t = re.sub(r"\s*[–—\-−]\s*", "–", text.strip())
    t = re.sub(r"(\d)\s+(\d{4})\s*$", r"\1, \2", t)  # 'July 8–10 2026' -> 'July 8–10, 2026'
    parts = t.split("–")
    if len(parts) > 2:
        return None, None
    parsed = []
    for p in parts:
        m = _DAY_PART.match(p)
        if not m:
            return None, None
        mon = _month_num(m.group(1)) if m.group(1) else None
        parsed.append([mon, int(m.group(2)), int(m.group(3)) if m.group(3) else None])
    end = parsed[-1]
    if end[0] is None or end[2] is None:
        if end[0] is None and parsed[0][0] is not None:
            end[0] = parsed[0][0]
        if end[2] is None:
            return None, None
    start = parsed[0]
    if start[0] is None:
        start[0] = end[0]
    if start[2] is None:
        start[2] = end[2] - 1 if start[0] > end[0] else end[2]

    def iso(x):
        return f"{x[2]:04d}-{x[0]:02d}-{x[1]:02d}"

    return iso(start), iso(end)


def section_path(table) -> list[str]:
    """Enclosing headings (h2 > h3 > ...) of a table: walk back, taking only shallower levels."""
    from mp.ingest.aggregators import clean

    out: dict[int, str] = {}
    min_level = 9
    for h in table.find_all_previous(["h2", "h3", "h4", "h5"]):
        lvl = int(h.name[1])
        if lvl < min_level:
            out[lvl] = clean(h.get_text(" "))
            min_level = lvl
        if lvl == 2:
            break
    return [out[k] for k in sorted(out)]


def _note_group(li) -> str | None:
    """Label of the footnote list an item belongs to, e.g. 'Partisan clients' (a bold paragraph
    just before the references wrapper), or None for unlabelled lists."""
    from mp.ingest.aggregators import clean

    ol = li.find_parent("ol")
    if ol is None:
        return None
    # climb to the top-level block of the article body (live pages wrap the list in extra divs)
    block = ol
    while block.parent is not None and "mw-parser-output" not in (block.parent.get("class") or []):
        block = block.parent
    prev = block.find_previous_sibling()
    while prev is not None and prev.name in ("link", "style", "meta"):
        prev = prev.find_previous_sibling()
    if prev is not None and prev.name in ("p", "div") and prev.find("b"):
        label = clean(prev.get_text(" "))
        return label if len(label) <= 40 else None
    return None


def _refs(cell, soup) -> tuple[list[str], list[str], list[str]]:
    """(citation URLs, note texts, notes in Wikipedia's 'Partisan clients' group) for a cell."""
    from bs4 import BeautifulSoup

    from mp.ingest.aggregators import clean

    urls, notes, partisan = [], [], []
    for a in cell.select("sup.reference a[href^='#']"):
        li = soup.find(id=a["href"][1:])
        if li is None:
            continue
        ext = [x["href"] for x in li.select("a.external[href]")]
        if ext:
            urls += ext
            continue
        group = _note_group(li)
        li = BeautifulSoup(str(li), "lxml")  # copy, so removing backlinks leaves the page intact
        for b in li.select(".mw-cite-backlink"):
            b.decompose()
        txt = clean(re.sub(r"^\s*\^\s*", "", li.get_text(" ")))
        if txt:
            notes.append(txt)
            if group and "partisan" in group.lower():
                partisan.append(txt)
    return urls, notes, partisan


def parse_poll_tables(html: str, *, race_id: str | None = None, principals: dict | None = None,
                      matcher=None, state: str | None = None,
                      house_districts: dict | None = None) -> tuple[list[dict], list[dict]]:
    """General-election poll rows from one page.

    Statewide/generic pages: pass race_id, principals {'D': name, 'R': name} and a NomineeMatcher
    (None for the generic ballot, whose columns are party names). House state pages: pass state
    and house_districts {race_id: {'D', 'R', 'D_party'}}; the district comes from the h2 section.
    """
    from bs4 import BeautifulSoup

    from mp.geo import race_id as make_race_id
    from mp.ingest.aggregators import clean, parse_pct, party_of, table_grid
    from mp.names import NomineeMatcher

    soup = BeautifulSoup(html, "lxml")
    rows: list[dict] = []
    log: list[dict] = []
    group_ids: dict[int, int] = {}
    for t_idx, table in enumerate(soup.select("table.wikitable")):
        grid = table_grid(table)
        if not grid or not clean(grid[0][0].get_text(" ")).lower().startswith("poll source"):
            continue
        hdr = [clean(c.get_text(" ")) for c in grid[0]]
        sec = section_path(table)
        sec_str = " > ".join(sec)
        base = {"table_index": t_idx, "section": sec_str, "header": hdr}
        if _SKIP_SECTION.search(sec_str):
            log.append(base | {"race_id": race_id, "reason": "primary_section"})
            continue
        rid, princ, m = race_id, principals, matcher
        if house_districts is not None and sec and sec[0].lower().startswith("statewide"):
            # statewide House-vote polls on a state's House page: not a district race
            log.append(base | {"race_id": None, "reason": "statewide_congressional_poll"})
            continue
        if house_districts is not None:
            dm = re.match(r"District (\d+)", sec[0]) if sec else None
            rid = make_race_id("HOU", state, dm.group(1) if dm else "AL")
            d = house_districts.get(rid)
            if d is None:
                log.append(base | {"race_id": rid, "reason": "no_district_nominees"})
                continue
            princ = {"D": d["D"], "R": d["R"]}
            m = NomineeMatcher({d["D"]: d.get("D_party", "D"), d["R"]: "R"})
        start = 4
        rcv_col = None
        if len(hdr) > 4 and re.match(r"(rcv )?round", hdr[4], re.IGNORECASE):
            rcv_col, start = 4, 5
        cands, tail = [], {}
        for i in range(start, len(hdr)):
            if _NON_CANDIDATE.match(hdr[i]):
                tail.setdefault(_tail_kind(hdr[i]), i)
            elif not tail:
                cands.append(i)
        # resolve candidate columns
        resolved = []  # (col, name, party, is_principal_side)
        for i in cands:
            raw_name, tag = party_of(hdr[i])
            if m:
                hit = m.match(raw_name)
                name, party = hit if hit else (raw_name, tag)
            else:
                name, party = raw_name, tag
            resolved.append((i, name, party, hit is not None if m else party in ("D", "R")))
        if m:
            d_col = next((c for c in resolved if c[1] == princ["D"]), None)
            r_col = next((c for c in resolved if c[1] == princ["R"]), None)
        else:
            d_col = next((c for c in resolved if c[2] == "D"), None)
            r_col = next((c for c in resolved if c[2] == "R"), None)
        if d_col is None or r_col is None:
            log.append(base | {"race_id": rid, "reason": "not_final_matchup",
                               "candidates": [c[1] for c in resolved]})
            continue
        extras = [c[1] for c in resolved if not c[3]]
        for r_idx, row in enumerate(grid[1:], 1):
            if len(row) < len(hdr) or len({id(c) for c in row}) == 1:
                continue  # rows holding only shared rowspan cells, or full-width separator rows
            vals = [clean(c.get_text(" ")) for c in row]
            if rcv_col is not None and not vals[rcv_col].isdigit():
                continue
            ptxt = vals[0]
            if not ptxt and all(parse_pct(vals[c[0]]) is None for c in resolved):
                log.append(base | {"race_id": rid, "reason": "annotation_row", "row_index": r_idx,
                                   "dates_raw": vals[1]})
                continue
            tag = re.search(r"\(([DRIL])\)\s*$", ptxt)
            pollster = re.sub(r"\s*\([DRIL]\)\s*$", "", ptxt).strip()
            urls, notes, partisan_notes = _refs(row[0], soup)
            n, pop = parse_sample(vals[2])
            fs, fe = parse_field_dates(vals[1])
            gid = group_ids.setdefault(id(row[0]), len(group_ids))
            tail_pct = {k: parse_pct(vals[i]) for k, i in tail.items() if k != "lead"}
            rows.append({
                "race_id": rid, "table_index": t_idx, "row_index": r_idx, "poll_group": gid,
                "section": sec_str, "pollster_raw": pollster,
                "pollster_partisan_tag": tag.group(1) if tag else None,
                "notes": notes, "partisan_client_notes": partisan_notes, "citation_urls": urls,
                "dates_raw": vals[1], "field_start": fs, "field_end": fe,
                "date_issue": ("unparsed" if fe is None else "start_after_end" if fs > fe
                               else "month_only" if _MONTH_ONLY.match(vals[1]) else None),
                "sample_raw": vals[2], "n": n, "population": pop, "moe": parse_moe(vals[3]),
                "rcv_round": int(vals[rcv_col]) if rcv_col is not None else None,
                "candidates": [{"name": c[1], "header": hdr[c[0]], "party": c[2],
                                "pct": parse_pct(vals[c[0]])} for c in resolved],
                "extra_candidates": extras,
                "dem_name": d_col[1], "dem_pct": parse_pct(vals[d_col[0]]),
                "rep_name": r_col[1], "rep_pct": parse_pct(vals[r_col[0]]),
                "other_pct": tail_pct.get("other"), "undecided_pct": tail_pct.get("undecided"),
                "other_undecided_pct": tail_pct.get("other_undecided"),
                "lead_raw": vals[tail["lead"]] if "lead" in tail else None,
            })
    return rows, log


def _tail_kind(h: str) -> str:
    h = h.lower()
    if h.startswith(("lead", "margin")):
        return "lead"
    if "other" in h and "undecided" in h:
        return "other_undecided"
    if h.startswith(("other", "someone")):
        return "other"
    return "undecided"


def parse_all(manifest: Path = RAW_DIR / "manifest.csv",
              races_csv: Path = Path("data/reference/races.csv"),
              out_dir: Path = Path("data/processed"), election_eve: str = "2026-11-02") -> dict:
    """Parse current revisions (polls with field end <= election eve), flag rows not present in
    the election-eve revision, and keep election-eve rows that were later removed (flagged)."""
    import json

    import polars as pl

    from mp.names import NomineeMatcher

    races = list(csv.DictReader(races_csv.open()))
    by_id = {r["race_id"]: r for r in races}
    house: dict[str, dict] = {}
    for r in races:
        if r["office"] == "HOU":
            house.setdefault(r["state"], {})[r["race_id"]] = {
                "D": r["d_side_name"], "R": r["r_side_name"], "D_party": r["d_side_party"]}
    man = list(csv.DictReader(manifest.open()))
    pages: dict[str, dict[str, dict]] = {}
    for r in man:
        pages.setdefault(r["title"], {})[r["which"]] = r
    all_rows, all_log = [], []
    for title, revs in sorted(pages.items()):
        kind = revs["current"]["page_kind"]
        if kind not in ("senate", "governor", "house_state", "generic_ballot"):
            continue
        rid = revs["current"]["race_id"] or None
        if kind == "house_state":
            st = STATES[_HOU.match(title).group(1)]
            kw = {"state": st, "house_districts": house.get(st, {})}
        elif kind == "generic_ballot":
            kw = {"race_id": rid, "principals": {"D": "Democratic", "R": "Republican"}, "matcher": None}
        else:
            race = by_id[rid]
            nominees = json.loads(race["nominees"])
            kw = {"race_id": rid, "principals": {"D": race["d_side_name"], "R": race["r_side_name"]},
                  "matcher": NomineeMatcher(nominees)}
        parsed = {}
        for which in ("pre_election", "current"):
            rev = revs[which]
            rows, log = parse_poll_tables(Path(rev["path_html"]).read_text(), **kw)
            src = {"source_page": title, "revid": int(rev["revid"]), "source_url": rev["url"]}
            parsed[which] = ([x | src for x in rows], [x | src | {"which": which} for x in log])

        def key(x):
            return (x["race_id"], x["pollster_raw"], x["dates_raw"], x["sample_raw"], x["rcv_round"],
                    x["dem_pct"], x["rep_pct"])

        def loose(x):
            return (x["race_id"], x["pollster_raw"], x["dates_raw"], x["sample_raw"], x["rcv_round"])

        pre_rows, cur_rows = parsed["pre_election"][0], parsed["current"][0]
        pre_loose = {loose(x) for x in pre_rows}
        cur_loose = {loose(x) for x in cur_rows}
        pre_exact = {key(x) for x in pre_rows}
        for x in cur_rows:
            x["added_post_election"] = loose(x) not in pre_loose
            x["edited_post_election"] = loose(x) in pre_loose and key(x) not in pre_exact
            x["removed_post_election"] = False
        removed = [x | {"added_post_election": False, "edited_post_election": False,
                        "removed_post_election": True} for x in pre_rows if loose(x) not in cur_loose]
        all_rows += cur_rows + removed
        all_log += parsed["current"][1]
    for x in all_rows:
        x["after_election_eve"] = bool(x["field_end"]) and x["field_end"] > election_eve
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pl.DataFrame(all_rows, infer_schema_length=None)
    p = out_dir / "polls_raw.parquet"
    df.write_parquet(p)
    logp = out_dir / "polls_parse_log.csv"
    pl.DataFrame([{k: (json.dumps(v) if isinstance(v, list) else v) for k, v in x.items()}
                  for x in all_log], infer_schema_length=None).write_csv(logp)
    return {"polls_raw": p, "log": logp, "rows": df.height}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode", choices=["fetch", "parse"])
    ap.add_argument("--root", type=Path, default=RAW_DIR)
    a = ap.parse_args(argv)
    if a.mode == "fetch":
        print("manifest:", fetch_all(a.root))
    else:
        print(parse_all(a.root / "manifest.csv"))


if __name__ == "__main__":
    main()
