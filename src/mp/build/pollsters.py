"""Pollster attributes table.

Two jobs:

1. Normalise the pollster names Wikipedia prints ("CNN /SSRS", "KTSP / SurveyUSA",
   "Grayhouse") to one canonical name per polling operation. The canonical pollster is
   the firm that did the fieldwork; media and other sponsors go to ``partner``. Joint
   bipartisan teams (e.g. Fabrizio Ward / Impact Research) stay a team because they
   design the poll together. The full raw -> canonical map is written to
   ``data/reference/pollster_aliases.csv`` so every decision is visible.

2. Turn the hand-curated, cited ``data/reference/pollster_methods.csv`` (long format:
   one row per pollster x field, with source URL, access date and the quoted evidence)
   into one row per pollster, with "unknown" wherever nothing was found.
"""

from __future__ import annotations

import re
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[3]
ALIASES = ROOT / "data/reference/pollster_aliases.csv"
METHODS = ROOT / "data/reference/pollster_methods.csv"
POLLS = ROOT / "data/processed/polls.parquet"
STATEWIDE = ("SEN", "GOV")

# Parts of a "A / B" name that are sponsors or media partners, not the fieldwork firm.
SPONSORS = {
    "cnn", "cbs", "cbs news", "kstp", "ktsp", "the economist", "reuters", "washington post",
    "the washington post", "abc news", "npr", "pbs", "yahoo news", "univision", "forbes",
    "2way", "financial times", "the center square", "third way", "tusk strategies",
    "cato institute", "independent center", "wpri-tv", "realclear opinion research",
    "vermont public", "wfsb", "ct insider", "portland press herald",
    "the philadelphia inquirer", "i&i", "politico", "nhjournal", "virginia project",
    "newsnation", "harvard",
}
# Firms that field polls for many sponsors (universities, newsletters, media): when one
# of these appears with other names, it is the pollster and the others are partners.
FIELDWORK = {"YouGov", "Verasight", "SSRS", "SurveyUSA", "Ipsos"}

# Spelling variants and renamed organisations -> canonical name. Keys are lower-case.
VARIANTS = {
    "siena college": "Siena University",
    "new york times / siena university": "New York Times / Siena",
    "the new york times / siena university": "New York Times / Siena",
    "new york times / siena college": "New York Times / Siena",
    "ktsp": "KSTP",
    "grayhouse": "GrayHouse",
    "public opinon strategies": "Public Opinion Strategies",
    "mclaughlin and associates": "McLaughlin & Associates",
    "hart research associates": "Hart Research",
    "hart research associates / public opinion strategies":
        "Hart Research / Public Opinion Strategies",
    "fabrizio / impact research": "Fabrizio Ward / Impact Research",
    "fabrizio, lee, & associates": "Fabrizio, Lee & Associates",
    "guidant polling and strategy": "Guidant Polling & Strategy",
    "mason-dixon": "Mason-Dixon Polling & Strategy",
    "mitchell research": "Mitchell Research & Communications",
    "marquette university": "Marquette University Law School",
    "onmessage": "OnMessage Inc.",
    "onmessage public strategies": "OnMessage Inc.",
    "pulse science decision": "Pulse Decision Science",
    "targoz media research": "Targoz Market Research",
    "research & polling": "Research & Polling Inc.",
    "rutgers-eagleton": "Rutgers University Eagleton Institute of Politics",
    "sea polling": "SEA Polling",
    "the trafalgar group": "Trafalgar Group",
    "the tarrance group": "Tarrance Group",
    "bullfinch group": "The Bullfinch Group",
    "upswing research & strategy": "Upswing Research",
    "votenexus": "VoteNexus Research",
    "resonance media": "Resonance Media Services",
    "american pulse": "American Pulse Research & Polling",
    "american pulse research": "American Pulse Research & Polling",
    "dccc analytics department": "DCCC",
    "dccc targeting team": "DCCC",
    "democratic congressional campaign committee": "DCCC",
    "harris poll / harrisx": "HarrisX",
    "sspg": "Schar School",
    "praecones analytica": "Praecones Analytica",
    "nhjournal / praecones analytica": "Praecones Analytica",
    "the public sentiment institute": "Public Sentiment Institute",
    "massinc polling group": "MassINC Polling Group",
    "ddhq": "Decision Desk HQ",
    "university of massachusetts lowell": "UMass Lowell",
    "university of massachusetts": "UMass Amherst",
}

_TAG = re.compile(r"\s*\((?:D|R|I)\)\s*")
# Single firms whose names contain a slash; protected from the "A / B" split.
_SLASH_NAMES = {"co/efficient": "co\u2215efficient"}


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _variant(name: str) -> str:
    return VARIANTS.get(name.lower(), name)


def canonical_pollster(raw: str) -> tuple[str, str]:
    """Return (canonical pollster, partner) for a Wikipedia pollster string."""
    text = _TAG.sub(" / ", raw)
    for name, safe in _SLASH_NAMES.items():
        text = re.sub(re.escape(name), safe, text, flags=re.IGNORECASE)
    parts = [_variant(_clean(p).replace("\u2215", "/")) for p in text.split("/") if _clean(p)]
    partners = [p for p in parts if p.lower() in SPONSORS]
    firms = [p for p in parts if p.lower() not in SPONSORS]
    if not firms:  # only sponsor names, e.g. "PennLive": keep as printed
        firms, partners = partners, []
    field = [p for p in firms if p in FIELDWORK]
    if field and len(firms) > 1:
        partners = [p for p in firms if p not in field] + partners
        firms = field
    pollster = _variant(" / ".join(firms))
    partners = [_variant(p) for p in partners]
    return pollster, " / ".join(partners)


def alias_table(raw_names: list[str]) -> pl.DataFrame:
    rows = []
    for raw in sorted(set(raw_names)):
        pollster, partner = canonical_pollster(raw)
        rows.append({"pollster_raw": raw, "pollster": pollster, "partner": partner})
    return pl.DataFrame(rows)


# ---------------------------------------------------------------- methods table

MODES = {"live_phone", "ivr", "text_to_web", "online_opt_in", "probability_panel", "mail",
         "mixed", "unknown"}
# "no" only when the release says so; "not_listed" when it lists its weighting variables
# and this one is not among them; "unknown" when nothing was found.
YES_NO = {"yes", "no", "sometimes", "not_listed", "unknown"}
FIELDS: dict[str, set[str] | None] = {
    "mode_main": MODES,            # the mode most interviews come from (for grouping)
    "modes": None,                 # every mode used, ';'-separated values from MODES
    "population": {"LV", "RV", "A", "LV/RV", "unknown"},
    "weight_education": YES_NO,
    "weight_recalled_vote": YES_NO,
    "weight_party": YES_NO,         # party ID or party registration
    "panel_source": None,          # free text: own panel, vendor, voter file, RDD ...
    "aapor_ti": {"yes", "no", "unknown"},
}


def validate_methods(long: pl.DataFrame) -> list[str]:
    """Problems in the long methods table: unknown fields, bad values, missing citations."""
    problems = []
    for r in long.iter_rows(named=True):
        f, v = r["field"], (r["value"] or "").strip()
        where = f"{r['pollster']} / {f}"
        if f not in FIELDS:
            problems.append(f"{where}: unknown field")
            continue
        if (r.get("scope") or "all") not in SCOPES:
            problems.append(f"{where}: scope must be one of {sorted(SCOPES)}")
        allowed = FIELDS[f]
        if f == "modes":
            if any(m not in MODES for m in v.split(";")):
                problems.append(f"{where}: bad mode list {v!r}")
        elif allowed is not None and v not in allowed:
            problems.append(f"{where}: value {v!r} not in {sorted(allowed)}")
        if v != "unknown" and not ((r["source_url"] or "").startswith("http") and r["accessed"]):
            problems.append(f"{where}: needs source_url and accessed date")
    return problems


SCOPES = {"all", "own"}  # all = every poll by the firm; own = only polls with no partner


def methods_wide(long: pl.DataFrame) -> pl.DataFrame:
    """One row per pollster x scope, one column per field; 'unknown' where nothing is coded."""
    if "scope" not in long.columns:
        long = long.with_columns(pl.lit("all").alias("scope"))
    wide = long.pivot(on="field", index=["pollster", "scope"], values="value",
                      aggregate_function="first")
    for f in FIELDS:
        if f not in wide.columns:
            wide = wide.with_columns(pl.lit(None, dtype=pl.String).alias(f))
    return wide.select("pollster", "scope", *FIELDS).with_columns(
        [pl.col(f).fill_null("unknown") for f in FIELDS])


def attach_methods(polls: pl.DataFrame, wide: pl.DataFrame) -> pl.DataFrame:
    """Add the method fields to each poll. A scope-'own' row applies only to polls with no
    partner (e.g. YouGov's own text-to-web state polls, not its university partnerships)."""
    polls = polls.drop([c for c in (*FIELDS, "methods_coded") if c in polls.columns])
    key = pl.when(pl.col("partner").fill_null("") == "").then(pl.lit("own")).otherwise(pl.lit("partner"))
    p = polls.with_columns(key.alias("_scope"))
    own = wide.filter(pl.col("scope") == "own").drop("scope")
    every = wide.filter(pl.col("scope") == "all").drop("scope")
    a = p.join(own.with_columns(pl.lit("own").alias("_scope")), on=["pollster", "_scope"], how="left")
    b = p.join(every, on="pollster", how="left")
    out = a.with_columns(
        [pl.coalesce(pl.col(f), b[f]).alias(f) for f in FIELDS]
    ).with_columns(pl.col("mode_main").is_not_null().alias("methods_coded"))
    return out.with_columns([pl.col(f).fill_null("unknown") for f in FIELDS]).drop("_scope")


# ---------------------------------------------------------------- build

def normalise_polls(polls: pl.DataFrame, aliases: pl.DataFrame) -> pl.DataFrame:
    out = polls.drop([c for c in ("pollster", "partner") if c in polls.columns])
    out = out.join(aliases, on="pollster_raw", how="left")
    cols = out.columns
    i = cols.index("pollster_raw")
    order = [*cols[: i + 1], "pollster", "partner"]
    return out.select(order + [c for c in cols if c not in order])


def main() -> None:
    polls = pl.read_parquet(POLLS)
    aliases = alias_table(polls["pollster_raw"].to_list())
    aliases.write_csv(ALIASES)
    polls = normalise_polls(polls, aliases)
    print(f"aliases: {aliases.height} raw names -> {aliases['pollster'].n_unique()} pollsters")

    long = pl.read_csv(METHODS, infer_schema_length=0).with_columns(pl.col("*").fill_null(""))
    problems = validate_methods(long)
    for p in problems:
        print("METHODS:", p)
    if problems:
        raise SystemExit(f"{len(problems)} problems in {METHODS.name}")
    wide = methods_wide(long)
    wide.write_parquet(ROOT / "data/processed/pollsters.parquet")
    polls = attach_methods(polls, wide)
    polls.write_parquet(POLLS)

    sw = polls.filter(pl.col("race_id").str.slice(0, 3).is_in(STATEWIDE))
    for label, d in (("statewide", sw), ("all", polls)):
        k = int(d["methods_coded"].sum())
        print(f"{label} polls with coded methods: {k}/{d.height} ({k / d.height:.0%})")


if __name__ == "__main__":
    main()
