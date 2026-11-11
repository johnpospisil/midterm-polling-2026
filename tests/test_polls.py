"""Poll-table rules: version preference, dedupe, partisan flags, dates."""

import polars as pl
import pytest

from mp.build.polls import build_polls, classify_sponsor, pollster_key


def raw(**kw):
    base = {
        "race_id": "SEN-ME-2026", "table_index": 1, "row_index": 1, "poll_group": 0,
        "section": "General election > Polling", "pollster_raw": "Emerson College",
        "pollster_partisan_tag": None, "notes": [], "partisan_client_notes": [],
        "citation_urls": ["https://x"],
        "dates_raw": "October 26–29, 2026", "field_start": "2026-10-26", "field_end": "2026-10-29",
        "date_issue": None, "sample_raw": "600 (LV)", "n": 600, "population": "LV", "moe": 3.9,
        "rcv_round": None, "candidates": [{"name": "Troy Jackson", "header": "Troy Jackson (D)",
                                           "party": "D", "pct": 49.0},
                                          {"name": "Susan Collins", "header": "Susan Collins (R)",
                                           "party": "R", "pct": 47.0}],
        "extra_candidates": [], "dem_name": "Troy Jackson", "dem_pct": 49.0,
        "rep_name": "Susan Collins", "rep_pct": 47.0, "other_pct": None, "undecided_pct": 4.0,
        "other_undecided_pct": None, "lead_raw": None, "source_page": "p", "revid": 1,
        "source_url": "https://en.wikipedia.org/w/index.php?oldid=1", "added_post_election": False,
        "edited_post_election": False, "removed_post_election": False, "after_election_eve": False,
    }
    row = base | kw
    if "candidates" not in kw:  # keep the candidate list consistent with dem_pct / rep_pct
        row["candidates"] = [
            {"name": row["dem_name"], "header": "", "party": "D", "pct": row["dem_pct"]},
            {"name": row["rep_name"], "header": "", "party": "R", "pct": row["rep_pct"]},
        ]
    return row


def run(rows):
    polls, waterfall = build_polls(pl.DataFrame(rows, infer_schema_length=None))
    return polls, waterfall


def test_lv_preferred_over_rv_and_a():
    polls, _ = run([
        raw(population="A", n=1500, dem_pct=50.0, rep_pct=40.0, row_index=1),
        raw(population="RV", n=1200, dem_pct=49.0, rep_pct=44.0, row_index=2),
        raw(population="LV", n=900, dem_pct=48.0, rep_pct=46.0, row_index=3),
    ])
    assert polls.height == 1
    p = polls.row(0, named=True)
    assert (p["population"], p["n"], p["n_versions"]) == ("LV", 900, 3)
    assert p["margin"] == pytest.approx(100 * 2 / 94)


def test_rcv_first_round_used():
    polls, _ = run([
        raw(rcv_round=1, dem_pct=48.0, rep_pct=46.0, row_index=1),
        raw(rcv_round=2, dem_pct=51.0, rep_pct=49.0, row_index=2),
    ])
    assert polls["rcv_round"].to_list() == [1]


def test_rcv_round_one_preferred_over_plain_vote_from_another_table():
    polls, _ = run([
        raw(table_index=2, rcv_round=None, dem_pct=47.0, rep_pct=47.0),
        raw(table_index=1, rcv_round=1, dem_pct=48.0, rep_pct=46.0),
    ])
    assert polls.height == 1 and polls["rcv_round"].to_list() == [1]


def test_full_ballot_then_leaners():
    three = [{"name": "Troy Jackson", "party": "D", "pct": 47.0, "header": ""},
             {"name": "Susan Collins", "party": "R", "pct": 45.0, "header": ""},
             {"name": "Rick Bennett", "party": "I", "pct": 5.0, "header": ""}]
    polls, _ = run([
        raw(row_index=1, dem_pct=50.0, rep_pct=48.0, undecided_pct=2.0),  # head-to-head
        raw(row_index=2, candidates=three, dem_pct=47.0, rep_pct=45.0, undecided_pct=3.0),
    ])
    assert polls["dem_pct"].to_list() == [47.0]
    # same ballot, with vs without leaners: fewer undecided wins
    polls, _ = run([
        raw(row_index=1, dem_pct=46.0, rep_pct=44.0, undecided_pct=10.0),
        raw(row_index=2, dem_pct=49.0, rep_pct=47.0, undecided_pct=4.0),
    ])
    assert polls["dem_pct"].to_list() == [49.0]


def test_same_poll_in_two_tables_counted_once_but_different_polls_kept():
    polls, wf = run([
        raw(table_index=1, poll_group=0),
        # same poll shown again in another table (e.g. a three-way question): one poll, not two
        raw(table_index=4, poll_group=7, pollster_raw="Emerson College ", dem_pct=46.0, rep_pct=45.0),
        raw(pollster_raw="UNH", poll_group=1, field_start="2026-10-20", field_end="2026-10-24"),
        raw(race_id="GOV-ME-2026"),  # same pollster and dates but a different race
    ])
    assert polls.height == 3
    assert dict(wf)["merged into another version of the same poll"] == 1


def test_exact_duplicate_and_unusable_rows_dropped():
    polls, wf = run([
        raw(), raw(),  # exact duplicate
        raw(pollster_raw="X", dem_pct=None),  # principal not offered
        raw(pollster_raw="Y", removed_post_election=True),
        raw(pollster_raw="Z", field_end="2026-11-03", field_start="2026-11-02", after_election_eve=True),
    ])
    w = dict(wf)
    assert polls.height == 1
    assert w["exact duplicate rows"] == 1
    assert w["a principal candidate not offered"] == 1
    assert w["removed from Wikipedia after the election"] == 1
    assert w["fieldwork ended after election eve"] == 1


def test_dates_midpoint_and_days_before():
    polls, _ = run([raw(field_start="2026-10-26", field_end="2026-10-29")])
    p = polls.row(0, named=True)
    assert str(p["field_mid"]) == "2026-10-27"  # midpoint rounds down
    assert p["days_before"] == 7 and p["week_before"] == 1


def test_reversed_dates_use_sorted_range():
    polls, _ = run([raw(field_start="2026-07-08", field_end="2026-07-06", date_issue="start_after_end")])
    p = polls.row(0, named=True)
    assert str(p["field_mid"]) == "2026-07-07" and p["date_issue"] == "start_after_end"


@pytest.mark.parametrize("tag,partisan_notes,expected", [
    (None, [], "nonpartisan"),
    ("R", [], "affiliated_pollster"),  # Wikipedia's firm tag only, no partisan client
    ("D", ["Poll sponsored by Platner's campaign."], "candidate_internal"),
    (None, ["Poll commissioned by the National Republican Congressional Committee"], "party_committee"),
    ("R", ["Poll sponsored by the NRSC"], "party_committee"),
    (None, ["Poll sponsored by Carolina Forward"], "partisan_client"),
    (None, ["Poll conducted behalf of John Stegner's campaign"], "candidate_internal"),
    # media / academic / nonpartisan nonprofits Wikipedia also lists under "Partisan clients"
    (None, ["Poll conducted for Fox News"], "sponsored_nonpartisan"),
    (None, ["Poll commissioned by AARP"], "sponsored_nonpartisan"),
    (None, ["Poll sponsored by The Cook Political Report ."], "sponsored_nonpartisan"),
    (None, ["Poll sponsored by WRAL-TV and WSOC-TV"], "sponsored_nonpartisan"),
    # a media outlet described as partisan stays partisan
    (None, ["Poll sponsored by Trending Politics, a conservative news website"], "partisan_client"),
])
def test_classify_sponsor(tag, partisan_notes, expected):
    assert classify_sponsor(tag, partisan_notes) == expected


def test_non_partisan_notes_do_not_make_a_poll_partisan():
    # only notes in Wikipedia's "Partisan clients" group count; e.g. "Includes leaners" doesn't
    polls, _ = run([raw(notes=["Poll sponsored by AARP"], partisan_client_notes=[])])
    assert polls["sponsor_class"].to_list() == ["nonpartisan"]


def test_pollster_key_normalises_punctuation_and_case():
    assert pollster_key("Emerson College ") == pollster_key("emerson  college")
    assert pollster_key("Verasight/VoteHub") == "verasightvotehub"


def test_ordinary_words_are_not_mistaken_for_media_sponsors():
    # e.g. "With" or "Work" must not look like TV call letters
    assert classify_sponsor(None, ["Poll sponsored by Work With Us Fund"]) == "partisan_client"


def test_user_sponsor_answers_override_auto_class(tmp_path):
    from mp.build.polls import apply_sponsor_review

    polls, _ = run([
        raw(partisan_client_notes=["Poll sponsored by Florida Politics"]),
        raw(pollster_raw="B", partisan_client_notes=["Poll sponsored by Carolina Journal"]),
        raw(pollster_raw="C", partisan_client_notes=["Poll sponsored by Some PAC"]),
    ])
    review = pl.DataFrame({"sponsor_note": ["Poll sponsored by Florida Politics",
                                            "Poll sponsored by Carolina Journal",
                                            "Poll sponsored by Some PAC"],
                           "partisan_Y_N": ["N", "Y", ""]})
    out = apply_sponsor_review(polls, review)
    got = dict(zip(out["pollster_raw"], out["sponsor_class"]))
    assert got == {"Emerson College": "sponsored_nonpartisan", "B": "partisan_client",
                   "C": "partisan_client"}  # blank answer keeps the automatic class
    assert dict(zip(out["pollster_raw"], out["is_partisan"])) == {"Emerson College": False, "B": True, "C": True}


def test_rewriting_review_files_keeps_user_entries(tmp_path):
    from mp.build.polls import merge_keep_user_columns

    old = pl.DataFrame({"k": ["a", "b"], "x": [1, 2], "partisan_Y_N": ["Y", ""]})
    new = pl.DataFrame({"k": ["a", "b", "c"], "x": [9, 9, 9], "partisan_Y_N": ["", "", ""]})
    merged = merge_keep_user_columns(new, old, key="k", user_cols=["partisan_Y_N"])
    assert merged.sort("k")["partisan_Y_N"].to_list() == ["Y", "", ""]
    assert merged.sort("k")["x"].to_list() == [9, 9, 9]
