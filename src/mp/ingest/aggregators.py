"""Final pre-election polling averages and forecaster ratings, parsed from Wikipedia (CC BY-SA 4.0).

Wikipedia race pages carry a "Source of poll aggregation" table listing each aggregator's final
average (Silver Bulletin, 270toWin, DDHQ, FiftyPlusOne, RealClearPolitics, ...), with dates and a
citation. The overview pages carry a ratings table (Cook, DDHQ, Economist, FPO, Silver, ...).
We take both from the last pre-election revision, so no aggregator site is scraped (see DATA.md).

Margins are Dem share minus Rep share (positive = Democratic lead), NOT two-party; two-party
conversion happens in build/margins.py.

    uv run python -m mp.ingest.aggregators
"""

from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup, Tag

from mp.geo import STATES, race_id

_FOOTNOTE = re.compile(r"\s*\[\s*[^\]]*\]")
_PARTY_TAG = re.compile(r"^(.*?)\s*\(\s*([A-Za-z.\-]+)\s*\)$")
_PARTY_MAP = {"D": "D", "DFL": "D", "DEM": "D", "R": "R", "REP": "R", "GOP": "R",
              "I": "I", "IND": "I", "IND.": "I", "L": "L", "LIB": "L", "G": "G", "GRN": "G"}
_GENERIC = {"democrats": "D", "democratic": "D", "democratic party": "D",
            "republicans": "R", "republican": "R", "republican party": "R"}
_MONTHS = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?"
_DATE = re.compile(rf"({_MONTHS})\s+(\d{{1,2}}),\s+(\d{{4}})")


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", _FOOTNOTE.sub("", text)).strip()


def parse_date(text: str) -> str | None:
    """Last 'Month D, YYYY' in the text, as ISO date."""
    found = _DATE.findall(text)
    if not found:
        return None
    mon, day, yr = found[-1]
    mon = mon.rstrip(".")[:3]
    return datetime.strptime(f"{mon} {day} {yr}", "%b %d %Y").date().isoformat()


def parse_pct(text: str) -> float | None:
    """'50.9%' -> 50.9; dashes, blanks and 'TBD' -> None."""
    m = re.search(r"-?\d+(?:\.\d+)?", text.replace("−", "-"))
    return float(m.group()) if m else None


def party_of(header: str) -> tuple[str, str | None]:
    h = clean(header)
    if h.lower() in _GENERIC:
        return h, _GENERIC[h.lower()]
    m = _PARTY_TAG.match(h)
    if m and m.group(2).upper() in _PARTY_MAP:
        return m.group(1).strip(), _PARTY_MAP[m.group(2).upper()]
    return h, None


def _span(cell: Tag, attr: str) -> int:
    """Span attribute as int; tolerates editor typos like rowspan='2"' seen on live pages."""
    m = re.search(r"\d+", str(cell.get(attr, "1")))
    return max(1, int(m.group())) if m else 1


def table_grid(table: Tag) -> list[list[Tag]]:
    """Expand rowspan/colspan so every row has one cell object per column."""
    grid: list[list[Tag]] = []
    pending: dict[tuple[int, int], Tag] = {}
    for r, tr in enumerate(table.find_all("tr")):
        row: list[Tag] = []
        col = 0
        cells = tr.find_all(["th", "td"], recursive=False)
        it = iter(cells)
        cell = next(it, None)
        while cell is not None or (r, col) in pending:
            if (r, col) in pending:
                row.append(pending.pop((r, col)))
                col += 1
                continue
            cs, rs = _span(cell, "colspan"), _span(cell, "rowspan")
            for dc in range(cs):
                row.append(cell)
                for dr in range(1, rs):
                    pending[(r + dr, col + dc)] = cell
            col += cs
            cell = next(it, None)
        grid.append(row)
    return grid


_INFOBOX_PARTY = {"democratic": "D", "republican": "R", "independent": "I",
                  "libertarian": "L", "green": "G"}


def _party_word(text: str) -> str | None:
    t = text.lower()
    return next((v for k, v in _INFOBOX_PARTY.items() if t.startswith(k)), None)


def nominees_from_infobox(html: str) -> dict[str, str]:
    """{nominee name: party code} from the race infobox.

    Unions every innermost Nominee/Candidate row with the Party row that follows it (top-4 races
    and minor-party candidates span several rows). Annotations such as "(replacing Graham
    Platner)" are stripped from names. Candidates of parties outside D/R/I/L/G are left out.
    """
    soup = BeautifulSoup(html, "lxml")
    ib = soup.select_one("table.infobox")
    if ib is None:
        return {}
    trs = ib.find_all("tr")
    out: dict[str, str] = {}
    for i, tr in enumerate(trs):
        th = tr.find("th")
        if not (th and clean(th.get_text(" ")) in ("Nominee", "Candidate")) or tr.find("table"):
            continue  # outer rows wrap a nested table; only innermost rows hold one name per cell
        names = [re.sub(r"\s*\(.*?\)\s*", " ", clean(td.get_text(" "))).strip()
                 for td in tr.find_all("td", recursive=False)]
        names = [n for n in names if n]
        party_tr = next((t for t in trs[i + 1:] if t.find("th") and
                         clean(t.find("th").get_text(" ")) == "Party"), None)
        if not names or party_tr is None:
            continue
        parties = [clean(td.get_text(" ")) for td in party_tr.find_all("td", recursive=False)]
        parties = [p for p in parties if p]
        if len(parties) == len(names):
            out.update({n: p for n, w in zip(names, parties) if (p := _party_word(w))})
    return out


_SUFFIX = {"jr", "sr", "ii", "iii", "iv"}


def _name_tokens(name: str) -> list[str]:
    name = re.sub(r"\(.*?\)", " ", name)  # party tags, "(replacing ...)" notes
    toks = [re.sub(r"[^a-z\-]", "", t) for t in name.lower().replace(",", " ").split()]
    return [t for t in toks if t and t not in _SUFFIX]


def _surname(name: str) -> str:
    t = _name_tokens(name)
    return t[-1] if t else ""


class NomineeMatcher:
    """Match a table header name to a nominee: first name + surname, else a unique surname.

    Needed because e.g. Alaska 2026 Senate has Dan S. Sullivan (R) and Daniel J. Sullivan Jr. (I).
    """

    def __init__(self, nominees: dict[str, str]):
        self.nominees = nominees
        self.by_first_last: dict[tuple[str, str], tuple[str, str]] = {}
        by_last: dict[str, list[tuple[str, str]]] = {}
        for n, p in nominees.items():
            t = _name_tokens(n)
            if t:
                self.by_first_last[(t[0], t[-1])] = (n, p)
                by_last.setdefault(t[-1], []).append((n, p))
        self.by_unique_last = {k: v[0] for k, v in by_last.items() if len(v) == 1}

    def __bool__(self) -> bool:
        return bool(self.nominees)

    def match(self, header_name: str) -> tuple[str, str] | None:
        t = _name_tokens(header_name)
        if not t:
            return None
        return self.by_first_last.get((t[0], t[-1])) or self.by_unique_last.get(t[-1])


def parse_aggregation_tables(html: str, rid: str, nominees: dict[str, str] | None = None) -> list[dict]:
    """Final-matchup rows from 'Source of poll aggregation' tables.

    With `nominees` (from the infobox), a table is kept only if its candidate columns are the
    nominees (matched by surname), which drops primaries and hypothetical matchups even when
    headers lack party tags. Without nominees (e.g. the generic ballot), fall back to header tags.
    """
    soup = BeautifulSoup(html, "lxml")
    out: list[dict] = []
    ge_index = 0
    matcher = NomineeMatcher(nominees or {})
    for table in soup.select("table.wikitable"):
        grid = table_grid(table)
        if not grid or not clean(grid[0][0].get_text(" ")).startswith("Source of poll agg"):
            continue
        hdr = [clean(c.get_text(" ")) for c in grid[0]]
        try:
            start = next(i for i, h in enumerate(hdr) if h.lower().startswith("dates updated")) + 1
        except StopIteration:
            continue
        cand_cols = []
        for i in range(start, len(hdr)):
            if re.match(r"(other|undecided|margin)", hdr[i], re.IGNORECASE):
                break
            cand_cols.append((i, *party_of(hdr[i])))
        if matcher:
            # every candidate column must be a nominee, and at least two nominees present
            matched = [matcher.match(name) for _, name, _ in cand_cols]
            if len(cand_cols) < 2 or any(m is None for m in matched):
                continue
            cand_cols = [(i, n, p) for (i, _, _), (n, p) in zip(cand_cols, matched)]
        tagged = [c for c in cand_cols if c[2]]
        if len(tagged) < 2:
            continue  # primary table
        other_i = next((i for i, h in enumerate(hdr) if re.match(r"other|undecided", h, re.IGNORECASE)), None)
        margin_i = next((i for i, h in enumerate(hdr) if h.lower().startswith("margin")), None)
        d_side = next((c for c in tagged if c[2] == "D"), None) or next((c for c in tagged if c[2] == "I"), None)
        r_side = next((c for c in tagged if c[2] == "R"), None)
        for row in grid[1:]:
            if len(row) < len(hdr):
                continue
            vals = [clean(c.get_text(" ")) for c in row]
            agg = vals[0]
            cands = [{"name": n, "party": p, "pct": parse_pct(vals[i])} for i, n, p in cand_cols]
            dem = parse_pct(vals[d_side[0]]) if d_side else None
            rep = parse_pct(vals[r_side[0]]) if r_side else None
            out.append({
                "race_id": rid, "table_index": ge_index, "aggregator": agg,
                "is_wiki_average": agg.lower() == "average",
                "dates_administered": vals[1], "date_updated": parse_date(vals[2]),
                "dem_name": d_side[1] if d_side else None, "dem_party": d_side[2] if d_side else None,
                "dem_pct": dem, "rep_name": r_side[1] if r_side else None, "rep_pct": rep,
                "other_pct": parse_pct(vals[other_i]) if other_i is not None else None,
                "margin": round(dem - rep, 3) if dem is not None and rep is not None else None,
                "margin_raw": vals[margin_i] if margin_i is not None else None,
                "candidates": json.dumps(cands),
            })
        ge_index += 1
    return out


_RATER = re.compile(rf"^(.*?)\s+({_MONTHS}\s+\d{{1,2}},\s+\d{{4}})")


def _norm_rating(r: str) -> str:
    r = re.sub(r"\s*\(flip\)", "", r, flags=re.IGNORECASE).strip()
    return re.sub(r"^(Solid|Safe)\b", "Safe", r)


def parse_ratings_table(html: str, office: str) -> list[dict]:
    """Long-format ratings from an overview page's sticky-header ratings table."""
    soup = BeautifulSoup(html, "lxml")
    out: list[dict] = []
    for table in soup.select("table.wikitable"):
        grid = table_grid(table)
        if len(grid) < 3:
            continue
        sub = [clean(c.get_text(" ")) for c in grid[1]]
        raters = [(i, m.group(1).strip(), parse_date(m.group(2)))
                  for i, h in enumerate(sub) if (m := _RATER.match(h))]
        if not sub or sub[0] != "State" or len(raters) < 2:
            continue
        for row in grid[2:]:
            state_txt = clean(row[0].get_text(" "))
            special = "special" in state_txt.lower()
            st = STATES.get(re.sub(r"\s*\(.*?\)", "", state_txt).strip())
            if not st:
                continue
            for i, rater, rdate in raters:
                raw = clean(row[i].get_text(" ")) if i < len(row) else ""
                if not raw:
                    continue
                out.append({"race_id": race_id(office, st), "special": special, "rater": rater,
                                "rating_date": rdate, "rating": _norm_rating(raw),
                                "flip": "flip" in raw.lower(), "rating_raw": raw})
        break
    return out


def parse_splitticket(csv_text: str, office: str) -> list[dict]:
    """Split Ticket Datawrapper dataset → race-level win probability and projected margin (D-R)."""
    out = []
    for r in csv.DictReader(io.StringIO(csv_text)):
        if office == "HOU":
            st, d = r["cd"].split("-")
            rid = race_id("HOU", st, d)
        else:
            st = STATES[re.sub(r"\s*\(.*?\)", "", r["State"]).strip()]
            rid = race_id(office, st)
        pred = r["prediction"].strip()
        sign = 1 if pred.upper().startswith("D") else -1
        mag = float(re.search(r"\d+(?:\.\d+)?", pred).group()) if re.search(r"\d", pred) else 0.0
        out.append({"race_id": rid, "dem_name": r["dem_name"], "rep_name": r["rep_name"],
                        "proj_margin": sign * mag, "dem_win_prob": float(r["win_prob_d"]) / 100,
                        "rating": _norm_rating(r["bucket"]), "flip": r["flip"].strip().upper() == "Y"})
    return out


# ---------------------------------------------------------------- build outputs (P02)

def build_final_tables(manifest: Path = Path("data/raw/wikipedia/manifest.csv"),
                       st_dir: Path = Path("data/raw/forecasts/splitticket"),
                       out_dir: Path = Path("data/processed")) -> dict[str, Path]:
    import polars as pl

    rows = list(csv.DictReader(manifest.open()))
    pre = {r["title"]: r for r in rows if r["which"] == "pre_election"}
    averages, ratings = [], []
    for r in pre.values():
        html = Path(r["path_html"]).read_text()
        src = {"source_page": r["title"], "revid": int(r["revid"]), "rev_timestamp": r["rev_timestamp"],
                   "source_url": r["url"]}
        if r["race_id"]:
            nominees = nominees_from_infobox(html)
            src = src | {"nominees": json.dumps(nominees)}
            averages += [a | src for a in parse_aggregation_tables(html, r["race_id"], nominees)]
        if r["page_kind"] in ("overview_senate", "overview_governor"):
            office = "SEN" if r["page_kind"] == "overview_senate" else "GOV"
            ratings += [x | src | {"office": office} for x in parse_ratings_table(html, office)]

    forecasts = [{"race_id": x["race_id"], "forecaster": x["rater"], "kind": "rating", "rating": x["rating"],
                      "flip": x["flip"], "dem_win_prob": None, "proj_margin": None, "as_of": x["rating_date"],
                      "source": f"Wikipedia ratings table ({x['source_page']})", "source_url": x["source_url"],
                      "capture": f"revid {x['revid']}"} for x in ratings]
    meta = json.loads((st_dir / "meta.json").read_text()) if (st_dir / "meta.json").exists() else {}
    for chart, m in meta.items():
        if m["office"] not in ("SEN", "HOU"):
            continue
        text = (st_dir / m["file"]).read_text()
        for x in parse_splitticket(text, m["office"]):
            forecasts.append({"race_id": x["race_id"], "forecaster": "Split Ticket", "kind": "model",
                                  "rating": x["rating"], "flip": x["flip"], "dem_win_prob": x["dem_win_prob"],
                                  "proj_margin": x["proj_margin"], "as_of": m["last_modified"],
                                  "source": "Split Ticket 2026 model (The Argument), Datawrapper 'Get the data'",
                                  "source_url": m["url"], "capture": f"{chart} v{m['version']}"})
    out_dir.mkdir(parents=True, exist_ok=True)
    pa, pf = out_dir / "final_averages.parquet", out_dir / "final_forecasts.parquet"
    pl.DataFrame(averages, infer_schema_length=None).write_parquet(pa)
    fdf = pl.DataFrame(forecasts, infer_schema_length=None)
    # Duplicate Split Ticket charts (map + table) carry identical data: keep one row per race.
    fdf.unique(subset=["race_id", "forecaster", "kind"], keep="first", maintain_order=True).write_parquet(pf)
    return {"averages": pa, "forecasts": pf}


if __name__ == "__main__":
    for k, p in build_final_tables().items():
        print(k, p)
