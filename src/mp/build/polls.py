"""Poll table: one row per poll x race (data/processed/polls.parquet).

From polls_raw (one row per published table row), in order:
1. drop rows removed from Wikipedia after the election, rows fielded after election eve, and rows
   where a principal candidate wasn't offered;
2. drop exact duplicate rows;
3. collapse every version of the same poll (same race, pollster, field dates; possibly spread over
   several tables) to ONE row, preferring in this order:
   a. RCV first round, then a plain-vote question, then later rounds (decision 2026-11-10);
   b. population LV > V > RV > A;
   c. the full ballot (most candidates) over a head-to-head;
   d. the version that allocates the most respondents ("with leaners": smallest residual);
   e. first listed.
Partisan sponsorship is classified from Wikipedia's (D)/(R) pollster tag and footnote text.

    uv run python -m mp.build.polls
"""

from __future__ import annotations

import hashlib
import re
from datetime import date
from pathlib import Path

import polars as pl

from mp.build.margins import two_party_margin, two_party_share

ELECTION_DAY = date(2026, 11, 3)
POP_RANK = {"LV": 0, "V": 1, "LV/RV": 1, "RV": 2, "A": 3}

# Sponsors that Wikipedia lists under "Partisan clients" but that are news outlets, academic
# centres or nonpartisan nonprofits. A sponsor described as liberal/conservative etc. stays partisan.
_NONPARTISAN_HINT = re.compile(
    r"(?i)\b(tv|news|times|post|journal|tribune|herald|gazette|radio|public media|npr|pbs|cnn|"
    r"fox|abc|cbs|nbc|msnbc|cnbc|reuters|bloomberg|axios|politico|the hill|newsweek|semafor|"
    r"cook political|sabato|inside elections|decision desk|split ticket|substack|newspaper|"
    r"press|daily|magazine|wral|wsoc|kare|wsb|wfaa|ksdk|university|college|school of|"
    r"institute of politics|aarp|chamber of commerce|league of women voters)\b")
_LEAN_WORDS = re.compile(
    r"(?i)\b(conservative|liberal|progressive|republican|democratic|right-wing|left-wing|"
    r"supports?|endorsed|pro-|super ?pac|pac\b|action fund|for america)")


_COMMITTEE = re.compile(
    r"\b(nrcc|nrsc|dccc|dscc|dga|rga|national republican|national democratic|"
    r"(democratic|republican) (governors|senatorial|congressional|national|state|party)|"
    r"(democratic|republican) party)\b", re.IGNORECASE)
_CAMPAIGN = re.compile(r"campaign|internal poll", re.IGNORECASE)


def pollster_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def classify_sponsor(tag: str | None, partisan_notes: list[str] | None) -> str:
    """Sponsor class from Wikipedia's 'Partisan clients' footnotes and its (D)/(R) pollster tag.

    candidate_internal  - sponsored by a candidate's campaign
    party_committee     - sponsored by a party committee (NRCC, DSCC, state party, ...)
    sponsored_nonpartisan - listed under "Partisan clients" but the sponsor is a news outlet,
                          university or nonpartisan nonprofit (AARP, Cook Political Report, ...)
    partisan_client     - listed under Wikipedia's "Partisan clients" (interest groups, PACs);
                          the user confirms the list in review/sponsors_for_review.csv
    affiliated_pollster - no partisan client, but Wikipedia tags the FIRM (D)/(R)
    nonpartisan         - none of the above
    """
    text = " ".join(partisan_notes or [])
    if _COMMITTEE.search(text):
        return "party_committee"
    if _CAMPAIGN.search(text):
        return "candidate_internal"
    if partisan_notes:
        if _NONPARTISAN_HINT.search(text) and not _LEAN_WORDS.search(text):
            return "sponsored_nonpartisan"
        return "partisan_client"
    if tag in ("D", "R", "I", "L"):
        return "affiliated_pollster"
    return "nonpartisan"


def _poll_id(race_id: str, pk: str, fs: str, fe: str) -> str:
    return hashlib.sha1(f"{race_id}|{pk}|{fs}|{fe}".encode()).hexdigest()[:10]


def build_polls(raw: pl.DataFrame) -> tuple[pl.DataFrame, list[tuple[str, int]]]:
    waterfall: list[tuple[str, int]] = [("rows in polls_raw", raw.height)]
    df = raw

    def drop(mask: pl.Expr, label: str):
        nonlocal df
        before = df.height
        df = df.filter(~mask)
        waterfall.append((label, before - df.height))

    drop(pl.col("removed_post_election"), "removed from Wikipedia after the election")
    drop(pl.col("after_election_eve").fill_null(False), "fieldwork ended after election eve")
    drop(pl.col("dem_pct").is_null() | pl.col("rep_pct").is_null(), "a principal candidate not offered")

    pct_sum = pl.col("candidates").list.eval(pl.element().struct.field("pct")).list.sum()
    df = df.with_columns(
        pl.col("pollster_raw").map_elements(pollster_key, return_dtype=pl.String).alias("pollster_key"),
        pl.col("candidates").list.len().alias("n_candidates"),
        (100 - pct_sum).alias("residual_pct"),
    )
    before = df.height
    df = df.unique(subset=["race_id", "pollster_key", "dates_raw", "sample_raw", "rcv_round",
                           "dem_pct", "rep_pct", "residual_pct", "n_candidates"],
                   keep="first", maintain_order=True)
    waterfall.append(("exact duplicate rows", before - df.height))

    rcv_rank = (pl.when(pl.col("rcv_round") == 1).then(0)
                .when(pl.col("rcv_round").is_null()).then(1)
                .otherwise(1 + pl.col("rcv_round")))
    pop_rank = pl.col("population").replace_strict(POP_RANK, default=4, return_dtype=pl.Int64)
    key = ["race_id", "pollster_key", "field_start", "field_end"]
    df = (df.with_columns(rcv_rank.alias("_rcv"), pop_rank.alias("_pop"),
                          pl.len().over(key).alias("n_versions"))
            .sort([*key, "_rcv", "_pop", "n_candidates", "residual_pct", "table_index", "row_index"],
                  descending=[False] * 4 + [False, False, True, False, False, False],
                  nulls_last=True))
    before = df.height
    df = df.unique(subset=key, keep="first", maintain_order=True)
    waterfall.append(("merged into another version of the same poll", before - df.height))

    lo = pl.min_horizontal(pl.col("field_start").str.to_date(), pl.col("field_end").str.to_date())
    hi = pl.max_horizontal(pl.col("field_start").str.to_date(), pl.col("field_end").str.to_date())
    mid = lo + pl.duration(days=((hi - lo).dt.total_days() // 2))
    df = df.with_columns(lo.alias("field_lo"), hi.alias("field_hi")).with_columns(mid.alias("field_mid"))
    df = df.with_columns(
        (pl.lit(ELECTION_DAY) - pl.col("field_mid")).dt.total_days().alias("days_before"),
    ).with_columns((pl.col("days_before") // 7).alias("week_before"))

    rows = df.to_dicts()
    for r in rows:
        r["margin"] = two_party_margin(r["dem_pct"], r["rep_pct"])
        r["dem_2p"] = two_party_share(r["dem_pct"], r["rep_pct"])
        r["margin_raw"] = r["dem_pct"] - r["rep_pct"]
        r["sponsor_class"] = classify_sponsor(r["pollster_partisan_tag"], r["partisan_client_notes"])
        r["is_partisan"] = r["sponsor_class"] in ("candidate_internal", "party_committee", "partisan_client")
        r["dem_party"] = next((c["party"] for c in r["candidates"] if c["name"] == r["dem_name"]), None)
        r["poll_id"] = _poll_id(r["race_id"], r["pollster_key"], r["field_start"], r["field_end"])
        r["office"] = r["race_id"].split("-")[0]
    out = pl.DataFrame(rows, infer_schema_length=None).drop(["_rcv", "_pop"])
    first = ["poll_id", "race_id", "office", "pollster_raw", "pollster_key", "sponsor_class",
             "is_partisan", "pollster_partisan_tag", "field_start", "field_end", "field_mid",
             "days_before", "week_before", "n", "population", "moe", "dem_name", "dem_party",
             "dem_pct", "rep_name", "rep_pct", "margin", "dem_2p", "margin_raw", "rcv_round",
             "n_versions", "n_candidates"]
    out = out.select(first + [c for c in out.columns if c not in first]).sort(["race_id", "field_mid"])
    waterfall.append(("final polls", out.height))
    return out, waterfall


def double_entry_sample(polls: pl.DataFrame, frac: float = 0.10, seed: int = 2026) -> pl.DataFrame:
    """Random 10% for hand-checking against the pollster's own release; most important first."""
    s = polls.sample(fraction=frac, seed=seed, shuffle=True)
    s = s.with_columns(
        pl.when(pl.col("office").is_in(["SEN", "GOV"]) & (pl.col("days_before") <= 21)).then(1)
        .when(pl.col("office").is_in(["SEN", "GOV"])).then(2).otherwise(3).alias("priority"))
    return (s.select(
        "priority", "poll_id", "race_id", "pollster_raw", "dates_raw", "sample_raw",
        "dem_name", "dem_pct", "rep_name", "rep_pct",
        pl.col("citation_urls").list.join(" ").alias("pollster_source"),
        pl.col("source_url").alias("wikipedia_revision"),
    ).with_columns(
        *[pl.lit("").alias(c) for c in ["check_dates", "check_n_pop", "check_dem_pct",
                                        "check_rep_pct", "matches_Y_N", "check_notes"]],
    ).sort(["priority", "race_id", "pollster_raw"]))


CHECK_COLS = ["check_dates", "check_n_pop", "check_dem_pct", "check_rep_pct", "matches_Y_N",
              "check_notes"]
SPONSOR_REVIEW = Path("review/sponsors_for_review.csv")
DOUBLE_ENTRY = Path("review/double_entry_sample.csv")


def merge_keep_user_columns(new: pl.DataFrame, old: pl.DataFrame, key: str,
                            user_cols: list[str]) -> pl.DataFrame:
    """Regenerated review table with the user's filled-in columns carried over by key."""
    keep = old.select(key, *user_cols).with_columns(pl.col(user_cols).cast(pl.String))
    out = new.drop(user_cols).join(keep, on=key, how="left").with_columns(
        pl.col(user_cols).fill_null(""))
    lost = old.join(new.select(key), on=key, how="anti").filter(
        pl.any_horizontal(pl.col(user_cols).cast(pl.String).fill_null("") != ""))
    if lost.height:
        print(f"WARNING: {lost.height} reviewed rows no longer exist (key {key}); see {key} values:",
              lost[key].to_list()[:10])
    return out.select(new.columns)


def apply_sponsor_review(polls: pl.DataFrame, review: pl.DataFrame) -> pl.DataFrame:
    """Apply the user's partisan_Y_N answers: any Y -> partisan_client; all answered N ->
    sponsored_nonpartisan. Campaign and party-committee polls keep their class."""
    ans = {r["sponsor_note"]: str(r["partisan_Y_N"] or "").strip().upper()
           for r in review.to_dicts()}

    def decide(notes, cls):
        if cls in ("candidate_internal", "party_committee") or not notes:
            return cls
        a = [ans.get(n, "") for n in notes]
        if "Y" in a:
            return "partisan_client"
        if a and all(x == "N" for x in a):
            return "sponsored_nonpartisan"
        return cls

    cls = [decide(n, c) for n, c in zip(polls["partisan_client_notes"].to_list(),
                                         polls["sponsor_class"].to_list())]
    return polls.with_columns(pl.Series("sponsor_class", cls)).with_columns(
        pl.col("sponsor_class").is_in(["candidate_internal", "party_committee", "partisan_client"])
        .alias("is_partisan"))


def main() -> None:
    raw = pl.read_parquet("data/processed/polls_raw.parquet")
    polls, wf = build_polls(raw)
    for label, n in wf:
        print(f"{label:>48}: {n}")
    Path("review").mkdir(exist_ok=True)

    sp = sponsors_for_review(polls)  # automatic classes, before the user's answers
    if SPONSOR_REVIEW.exists():
        sp = merge_keep_user_columns(sp, pl.read_csv(SPONSOR_REVIEW, infer_schema_length=None),
                                     key="sponsor_note", user_cols=["partisan_Y_N"])
    sp.write_csv(SPONSOR_REVIEW)
    answered = (sp["partisan_Y_N"] != "").sum()
    print(f"partisan-client sponsors: {sp.height} ({answered} answered) -> {SPONSOR_REVIEW}")
    polls = apply_sponsor_review(polls, sp)

    Path("data/processed").mkdir(parents=True, exist_ok=True)
    polls.write_parquet("data/processed/polls.parquet")

    s = double_entry_sample(polls)
    if DOUBLE_ENTRY.exists():
        s = merge_keep_user_columns(s, pl.read_csv(DOUBLE_ENTRY, infer_schema_length=None),
                                    key="poll_id", user_cols=CHECK_COLS)
    s.write_csv(DOUBLE_ENTRY)
    print("double-entry sample:", s.height, "polls ->", DOUBLE_ENTRY)


def sponsors_for_review(polls: pl.DataFrame) -> pl.DataFrame:
    """Distinct 'Partisan clients' sponsor notes with the automatic class; the user confirms the
    `partisan_Y_N` column (uncertain ones first: partisan_client, then sponsored_nonpartisan)."""
    s = (polls.filter(pl.col("partisan_client_notes").list.len() > 0)
         .explode("partisan_client_notes")
         .group_by(pl.col("partisan_client_notes").alias("sponsor_note"))
         .agg(pl.len().alias("polls"), pl.col("sponsor_class").sort().first().alias("auto_class"),
              pl.col("race_id").unique().sort().str.join(", ").alias("races")))
    return (s.with_columns(
        pl.lit("").alias("partisan_Y_N"))
        .sort(["auto_class", "polls", "sponsor_note"], descending=[False, True, False]))


if __name__ == "__main__":
    main()
