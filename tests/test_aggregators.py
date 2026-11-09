import pytest
from bs4 import BeautifulSoup

from mp.ingest.aggregators import (
    NomineeMatcher,
    nominees_from_infobox,
    parse_aggregation_tables,
    parse_ratings_table,
    parse_splitticket,
    party_of,
    table_grid,
)

STATE_PAGE = """
<table class="wikitable"><tr><th>Source of poll aggregation</th><th>Dates administered</th>
<th>Dates updated</th><th>Abdul El-Sayed</th><th>Haley Stevens</th><th>Undecided</th><th>Margin</th></tr>
<tr><td>270toWin<sup>[1]</sup></td><td>through July 30, 2026</td><td>August 3, 2026</td><td>50%</td>
<td>40%</td><td>10%</td><td>El-Sayed +10%</td></tr></table>
<table class="wikitable"><tr><th>Source of poll aggregation</th><th>Dates administered</th>
<th>Dates updated</th><th>Abdul El-Sayed (D)</th><th>Mike Rogers (R)</th><th>Other/ Undecided</th>
<th>Margin</th></tr>
<tr><td>Silver Bulletin<sup>[9]</sup></td><td>September 1 – November 1, 2026</td><td>November 2, 2026</td>
<td>50.9%</td><td>46.0%</td><td>3.1%</td><td>El-Sayed +4.9%</td></tr>
<tr><td>RealClearPolitics</td><td>October 20–31, 2026</td><td>November 1, 2026</td>
<td>50.0%</td><td>46.5%</td><td>3.5%</td><td>El-Sayed +3.5%</td></tr>
<tr><td>Average</td><td colspan="2">November 2, 2026</td><td>50.5%</td><td>46.2%</td><td>3.3%</td>
<td>El-Sayed +4.2%</td></tr></table>
"""

GENERIC_PAGE = """
<table class="wikitable"><tr><th>Source of poll aggregation</th><th>Dates administered</th>
<th>Dates updated</th><th>Republicans</th><th>Democrats</th><th>Other/ Undecided</th><th>Margin</th></tr>
<tr><td>Decision Desk HQ</td><td>January 9, 2025 – October 31, 2026</td><td>November 1, 2026</td>
<td>42.3%</td><td>51.2%</td><td>6.5%</td><td>Democrats +8.9%</td></tr></table>
"""


def test_party_of_header():
    assert party_of("Abdul El-Sayed (D)") == ("Abdul El-Sayed", "D")
    assert party_of("Peggy Flanagan (DFL)") == ("Peggy Flanagan", "D")
    assert party_of("Dan Osborn (I)") == ("Dan Osborn", "I")
    assert party_of("Republicans") == ("Republicans", "R")
    assert party_of("Democrats") == ("Democrats", "D")
    assert party_of("Haley Stevens") == ("Haley Stevens", None)


def test_aggregation_skips_primary_tables_and_maps_by_party():
    rows = parse_aggregation_tables(STATE_PAGE, "SEN-MI-2026")
    assert [r["aggregator"] for r in rows] == ["Silver Bulletin", "RealClearPolitics", "Average"]
    sb = rows[0]
    assert sb["dem_pct"] == pytest.approx(50.9)
    assert sb["rep_pct"] == pytest.approx(46.0)
    assert sb["margin"] == pytest.approx(4.9)  # D - R, positive = Democratic lead
    assert sb["date_updated"] == "2026-11-02"
    assert rows[2]["is_wiki_average"] and not sb["is_wiki_average"]
    # colspan on the Average row must not shift the candidate columns
    assert rows[2]["dem_pct"] == pytest.approx(50.5)


UNTAGGED_AND_PRIMARY = """
<table class="infobox"><tr><th>Nominee</th><td>Chris Pappas</td><td>John E. Sununu</td></tr>
<tr><th>Party</th><td>Democratic</td><td>Republican</td></tr></table>
<table class="wikitable"><tr><th>Source of poll aggregation</th><th>Dates administered</th>
<th>Dates updated</th><th>Chris Pappas (D)</th><th>Scott Brown (R)</th><th>Other/Undecided</th>
<th>Margin</th></tr>
<tr><td>270toWin</td><td>June 30, 2026</td><td>July 13, 2026</td><td>50.0%</td><td>37.0%</td>
<td>13.0%</td><td>Pappas +13.0%</td></tr></table>
<table class="wikitable"><tr><th>Source of poll aggregation</th><th>Dates administered</th>
<th>Dates updated</th><th>John E. Sununu</th><th>Chris Pappas</th><th>Other/Undecided</th>
<th>Margin</th></tr>
<tr><td>270toWin</td><td>September 15 – October 20, 2026</td><td>October 22, 2026</td><td>42.8%</td>
<td>49.7%</td><td>7.5%</td><td>Pappas +6.9%</td></tr></table>
"""


def test_nominees_from_infobox():
    assert nominees_from_infobox(UNTAGGED_AND_PRIMARY) == {"Chris Pappas": "D", "John E. Sununu": "R"}


def test_nominees_strip_replacement_note_and_union_rows():
    html = """<table class="infobox">
    <tr><th>Nominee</th><td><table><tr><td>x</td></tr></table></td></tr>
    <tr><th>Nominee</th><td>Susan Collins</td><td>Troy Jackson (replacing Graham Platner )</td></tr>
    <tr><th>Party</th><td>Republican</td><td>Democratic</td></tr>
    <tr><th>Candidate</th><td>Jonathan Kreiss-Tomkins</td><td>Bernadette Wilson</td></tr>
    <tr><th>Party</th><td>Democratic</td><td>Republican</td></tr>
    <tr><th>Nominee</th><td>Brett Lindstrom</td><td>Rick Beard</td></tr>
    <tr><th>Party</th><td>America First</td><td>Legal Marijuana NOW</td></tr></table>"""
    assert nominees_from_infobox(html) == {
        "Susan Collins": "R", "Troy Jackson": "D",
        "Jonathan Kreiss-Tomkins": "D", "Bernadette Wilson": "R",
    }


def test_matcher_handles_shared_surname():
    m = NomineeMatcher({"Dan S. Sullivan": "R", "Mary Peltola": "D", "Daniel J. Sullivan Jr.": "I"})
    assert m.match("Dan Sullivan (R)") == ("Dan S. Sullivan", "R")
    assert m.match("Daniel Sullivan Jr.") == ("Daniel J. Sullivan Jr.", "I")
    assert m.match("Peltola") == ("Mary Peltola", "D")
    assert m.match("Sullivan") is None  # ambiguous surname alone never matches


def test_aggregation_uses_nominees_not_header_tags():
    nominees = nominees_from_infobox(UNTAGGED_AND_PRIMARY)
    rows = parse_aggregation_tables(UNTAGGED_AND_PRIMARY, "SEN-NH-2026", nominees)
    # hypothetical Pappas-vs-Brown table dropped; untagged final-matchup table kept
    assert len(rows) == 1
    r = rows[0]
    assert (r["dem_name"], r["rep_name"]) == ("Chris Pappas", "John E. Sununu")
    assert r["margin"] == pytest.approx(6.9)


def test_top_two_primary_table_dropped_when_nominees_known():
    html = """
    <table class="wikitable"><tr><th>Source of poll aggregation</th><th>Dates administered</th>
    <th>Dates updated</th><th>Xavier Becerra (D)</th><th>Chad Bianco (R)</th><th>Steve Hilton (R)</th>
    <th>Katie Porter (D)</th><th>Other/ Undecided</th><th>Margin</th></tr>
    <tr><td>270toWin</td><td>May 14–31, 2026</td><td>June 2, 2026</td><td>24%</td><td>11%</td><td>22%</td>
    <td>7%</td><td>36%</td><td>Becerra +2%</td></tr></table>"""
    nominees = {"Xavier Becerra": "D", "Steve Hilton": "R"}
    assert parse_aggregation_tables(html, "GOV-CA-2026", nominees) == []


def test_generic_ballot_republicans_listed_first():
    (r,) = parse_aggregation_tables(GENERIC_PAGE, "GEN-US-2026")
    assert (r["dem_pct"], r["rep_pct"]) == (pytest.approx(51.2), pytest.approx(42.3))
    assert r["margin"] == pytest.approx(8.9)


RATINGS = """
<table class="wikitable sortable sticky-header-multi">
<tr><th colspan="2">Constituency</th><th colspan="2">Incumbent</th><th colspan="2">Ratings</th>
<th rowspan="2">Result</th></tr>
<tr><th>State</th><th>PVI</th><th>Senator</th><th>Last election</th>
<th>Cook <small>Nov 2, 2026</small><sup>[29]</sup></th><th>Silver <small>Nov 3, 2026</small></th></tr>
<tr><td>Alaska</td><td>R+6</td><td>Dan Sullivan</td><td>53.90% R</td><td>Tossup</td>
<td>Lean D <small>(flip)</small></td><td>TBD</td></tr>
<tr><td>Ohio <small>(special)</small></td><td>R+5</td><td>Jon Husted</td><td>New seat</td><td>Lean R</td>
<td>Tossup</td><td>TBD</td></tr>
</table>
"""


def test_ratings_long_format():
    rows = parse_ratings_table(RATINGS, "SEN")
    assert len(rows) == 4
    ak_silver = next(r for r in rows if r["race_id"] == "SEN-AK-2026" and r["rater"] == "Silver")
    assert ak_silver["rating"] == "Lean D"
    assert ak_silver["flip"] is True
    assert ak_silver["rating_date"] == "2026-11-03"
    assert {r["race_id"] for r in rows} == {"SEN-AK-2026", "SEN-OH-2026"}


def test_table_grid_expands_rowspan_and_colspan():
    t = BeautifulSoup(
        "<table><tr><td rowspan=2>a</td><td colspan=2>b</td></tr><tr><td>c</td><td>d</td></tr></table>",
        "lxml",
    ).table
    assert [[c.get_text() for c in row] for row in table_grid(t)] == [["a", "b", "b"], ["a", "c", "d"]]


def test_table_grid_tolerates_malformed_span():
    t = BeautifulSoup('<table><tr><td rowspan=\'2"\'>a</td><td>b</td></tr><tr><td>c</td></tr></table>',
                      "lxml").table
    assert [[c.get_text() for c in row] for row in table_grid(t)] == [["a", "b"], ["a", "c"]]


def test_parse_splitticket_senate_and_house():
    sen = (
        "Matchup,State,dem_name,rep_name,prediction,raw_prediction,bucket,win_prob_d,flip,win_prob_r\n"
        "A (D) vs B (R),Alabama,A,B,R+17.6,17.6,Safe R,0,N,100\n"
        "C (D) vs D (R),Ohio (Special),C,D,D+2.1,2.1,Lean D,61,Y,39\n"
    )
    rows = parse_splitticket(sen, office="SEN")
    assert rows[0]["race_id"] == "SEN-AL-2026" and rows[0]["proj_margin"] == pytest.approx(-17.6)
    assert rows[1]["race_id"] == "SEN-OH-2026" and rows[1]["dem_win_prob"] == pytest.approx(0.61)
    hou = (
        "Matchup,cd,dem_name,rep_name,prediction,raw_prediction,bucket,win_prob_d,flip,win_prob_r\n"
        "X (D) vs Y (R),AK-AL,X,Y,R+8.2,8.2,Likely R,11,N,89\n"
        "X (D) vs Y (R),AZ-6,X,Y,D+0.4,0.4,Tossup,52,Y,48\n"
    )
    rows = parse_splitticket(hou, office="HOU")
    assert [r["race_id"] for r in rows] == ["HOU-AKAL-2026", "HOU-AZ06-2026"]
