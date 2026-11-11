"""Poll-table parser tests on small synthetic fixtures modelled on the 2026 Wikipedia pages."""

import pytest

from mp.ingest.wikipedia_polls import (
    parse_field_dates,
    parse_moe,
    parse_poll_tables,
    parse_sample,
)
from mp.names import NomineeMatcher


def H(level, text):
    return f'<div class="mw-heading mw-heading{level}"><h{level}>{text}</h{level}></div>'


def poll_table(cols, rows):
    head = "".join(f"<th>{c}</th>" for c in ["Poll source", "Date(s) administered", "Sample size",
                                              "Margin of error", *cols])
    return f'<table class="wikitable"><tr>{head}</tr>{"".join(rows)}</table>'


REFS = """
<div class="reflist"><ol class="references">
<li id="cite_note-1"><cite><a class="external text" href="https://emerson.example/poll-me">Emerson</a></cite></li>
<li id="cite_note-B-2">Poll sponsored by the Collins campaign</li>
</ol></div>"""

SENATE_ME = (
    H(2, "Republican primary") + H(3, "Polling")
    + poll_table(["Susan Collins", "Dan Smith"], [
        "<tr><td>UNH</td><td>May 1–5, 2026</td><td>400 (LV)</td><td>± 4.9%</td><td>70%</td><td>20%</td></tr>"])
    + H(2, "General election") + H(3, "Candidates") + H(4, "Declined") + H(3, "Polling")
    + poll_table(["Susan Collins (R)", "Troy Jackson (D)", "Other", "Undecided"], [
        ('<tr><td>Emerson College<sup class="reference"><a href="#cite_note-1">[1]</a></sup></td>'
        "<td>October 31 – November 1, 2026</td><td>600 (LV)</td><td>± 4.0%</td>"
        "<td>48%</td><td>49%</td><td>—</td><td>3%</td></tr>"),
        ('<tr><td rowspan="2">Rasmussen Reports (R)<sup class="reference"><a href="#cite_note-B-2">[B]</a>'
        "</sup></td><td rowspan=2>October 27 – November 2, 2026</td><td>896 (LV)</td>"
        "<td rowspan=2>± 3.0%</td><td>46%</td><td>49%</td><td>—</td><td>5%</td></tr>"),
        "<tr><td>1,020 (RV)</td><td>45%</td><td>48%</td><td>—</td><td>7%</td></tr>",
    ])
    # hypothetical matchup: Bellows was not the nominee -> dropped
    + poll_table(["Susan Collins (R)", "Shenna Bellows (D)", "Undecided"], [
        ("<tr><td>Z to A Research (D)</td><td>July 7–8, 2026</td><td>988 (LV)</td><td>± 3.1%</td>"
        "<td>47%</td><td>47%</td><td>6%</td></tr>")])
    + REFS
)
ME_PRINCIPALS = {"D": "Troy Jackson", "R": "Susan Collins"}
ME_NOMINEES = {"Susan Collins": "R", "Troy Jackson": "D"}


def test_parse_sample_and_moe():
    assert parse_sample("1,326 (LV)") == (1326, "LV")
    assert parse_sample("— (LV)") == (None, "LV")
    assert parse_sample("536 (LV/RV)") == (536, "LV/RV")
    assert parse_sample("400") == (400, None)
    assert parse_moe("± 3.0%") == 3.0
    assert parse_moe("—") is None


@pytest.mark.parametrize("text,expected", [
    ("October 26–29, 2026", ("2026-10-26", "2026-10-29")),
    ("October 31 – November 1, 2026", ("2026-10-31", "2026-11-01")),
    ("December 28, 2025 – January 3, 2026", ("2025-12-28", "2026-01-03")),
    ("March 9, 2026", ("2026-03-09", "2026-03-09")),
    ("Oct. 2–4, 2026", ("2026-10-02", "2026-10-04")),
    ("September 22−27, 2026", ("2026-09-22", "2026-09-27")),  # U+2212 minus sign
    ("July 27 − August 3, 2026", ("2026-07-27", "2026-08-03")),
    ("July 8–10 2026", ("2026-07-08", "2026-07-10")),  # missing comma
    ("April 2026", ("2026-04-01", "2026-04-30")),  # month only
    ("February 2026", ("2026-02-01", "2026-02-28")),
])
def test_parse_field_dates(text, expected):
    assert parse_field_dates(text) == expected


def test_annotation_rows_and_statewide_house_polls_skipped():
    html = (
        H(2, "General election") + H(3, "Polling")
        + poll_table(["Susan Collins (R)", "Troy Jackson (D)"], [
            "<tr><td></td><td>July 21, 2026</td><td>—</td><td>—</td><td>—</td><td>—</td></tr>",
            "<tr><td>Emerson</td><td>July 1–3, 2026</td><td>600 (LV)</td><td>±4%</td><td>48%</td><td>47%</td></tr>",
        ])
    )
    rows, log = parse_poll_tables(html, race_id="SEN-ME-2026", principals=ME_PRINCIPALS,
                                  matcher=NomineeMatcher(ME_NOMINEES))
    assert [r["pollster_raw"] for r in rows] == ["Emerson"]
    assert any(x["reason"] == "annotation_row" for x in log)
    house = (H(2, "Statewide polling") + H(3, "Statewide congressional polls")
             + poll_table(["Democratic", "Republican"], [
                 "<tr><td>X</td><td>July 1, 2026</td><td>500 (LV)</td><td>—</td><td>50%</td><td>45%</td></tr>"]))
    rows, log = parse_poll_tables(house, state="AZ", house_districts={})
    assert rows == [] and log[0]["reason"] == "statewide_congressional_poll"


def test_note_backlink_letters_stripped():
    html = (H(2, "General election") + H(3, "Polling")
            + poll_table(["Susan Collins (R)", "Troy Jackson (D)"], [
                ('<tr><td>AARP poll<sup class="reference"><a href="#cite_note-A-1">[A]</a></sup></td>'
                "<td>July 1–3, 2026</td><td>600 (LV)</td><td>±4%</td><td>48%</td><td>47%</td></tr>")])
            + '<ol><li id="cite_note-A-1"><span class="mw-cite-backlink">^ <a>a</a> <a>b</a></span>'
              " Poll sponsored by AARP</li></ol>")
    (r,), _ = parse_poll_tables(html, race_id="SEN-ME-2026", principals=ME_PRINCIPALS,
                                matcher=NomineeMatcher(ME_NOMINEES))
    assert r["notes"] == ["Poll sponsored by AARP"]


def test_partisan_client_group_recorded():
    html = (H(2, "General election") + H(3, "Polling")
            + poll_table(["Susan Collins (R)", "Troy Jackson (D)"], [
                ('<tr><td>PPP<sup class="reference"><a href="#cite_note-X-1">[A]</a></sup></td>'
                "<td>July 1–3, 2026</td><td>600 (LV)</td><td>±4%</td><td>48%</td><td>47%</td></tr>"),
                ('<tr><td>UNH<sup class="reference"><a href="#cite_note-Y-2">[a]</a></sup></td>'
                "<td>July 5–7, 2026</td><td>600 (LV)</td><td>±4%</td><td>48%</td><td>47%</td></tr>")])
            # live-page structure: <link> between label and list, and an extra wrapper div
            + '<p><b>Partisan clients</b></p><link rel="mw-deduplicated-inline-style"/>'
              '<div><div class="mw-references-wrap"><ol class="references">'
              '<li id="cite_note-X-1">^ Poll sponsored by Maine Forward</li></ol></div></div>'
            + '<div><div class="mw-references-wrap"><ol class="references">'
              '<li id="cite_note-Y-2">^ Includes leaners</li></ol></div></div>')
    html = f'<div class="mw-content-ltr mw-parser-output">{html}</div>'
    rows, _ = parse_poll_tables(html, race_id="SEN-ME-2026", principals=ME_PRINCIPALS,
                                matcher=NomineeMatcher(ME_NOMINEES))
    assert rows[0]["partisan_client_notes"] == ["Poll sponsored by Maine Forward"]
    assert rows[1]["partisan_client_notes"] == [] and rows[1]["notes"] == ["Includes leaners"]


def test_reversed_dates_flagged_not_fixed():
    html = (H(2, "General election") + H(3, "Polling")
            + poll_table(["Susan Collins (R)", "Troy Jackson (D)"], [
                ("<tr><td>Grassroots</td><td>July 8–6, 2026</td><td>500 (LV)</td><td>—</td><td>40%</td>"
                "<td>52%</td></tr>")]))
    (r,), _ = parse_poll_tables(html, race_id="SEN-ME-2026", principals=ME_PRINCIPALS,
                                matcher=NomineeMatcher(ME_NOMINEES))
    assert r["date_issue"] == "start_after_end"
    assert (r["field_start"], r["field_end"]) == ("2026-07-08", "2026-07-06")


def test_general_election_rows_only_and_variants_grouped():
    rows, log = parse_poll_tables(SENATE_ME, race_id="SEN-ME-2026", principals=ME_PRINCIPALS,
                                  matcher=NomineeMatcher(ME_NOMINEES))
    assert [r["pollster_raw"] for r in rows] == ["Emerson College", "Rasmussen Reports", "Rasmussen Reports"]
    em, ras_lv, ras_rv = rows
    assert (em["dem_pct"], em["rep_pct"], em["undecided_pct"]) == (49.0, 48.0, 3.0)
    assert em["field_start"] == "2026-10-31" and em["field_end"] == "2026-11-01"
    assert em["citation_urls"] == ["https://emerson.example/poll-me"]
    assert em["section"].startswith("General election")
    # the two Rasmussen rows are one poll published in two versions
    assert ras_lv["poll_group"] == ras_rv["poll_group"] != em["poll_group"]
    assert (ras_lv["population"], ras_rv["population"]) == ("LV", "RV")
    assert ras_rv["moe"] == 3.0 and ras_rv["field_end"] == "2026-11-02"
    assert ras_lv["pollster_partisan_tag"] == "R"
    assert ras_lv["notes"] == ["Poll sponsored by the Collins campaign"]
    reasons = {x["reason"] for x in log}
    assert "primary_section" in reasons and "not_final_matchup" in reasons


AK_RCV = (
    H(2, "General election") + H(3, "Polling") + H(4, "Ranked-choice polls")
    + poll_table(["RCV round", "Dan S. Sullivan (R)", "Mary Peltola (D)", "Dan J. Sullivan (I)",
                  "Gerald Heikes (R)", "Undecided / Not Ranked"], [
        ('<tr><td rowspan="3">Alaska Survey Research</td><td rowspan="3">October 26–29, 2026</td>'
        '<td rowspan="3">1,326 (LV)</td><td rowspan="3">± 3.0%</td></tr>'),
        "<tr><td>1</td><td>46%</td><td>48%</td><td>3%</td><td>3%</td><td>–</td></tr>",
        "<tr><td>2</td><td>47%</td><td>48%</td><td>5%</td><td>–</td><td>–</td></tr>",
    ])
)


def test_rcv_rounds_and_extra_candidates():
    nominees = {"Dan S. Sullivan": "R", "Mary Peltola": "D", "Daniel J. Sullivan Jr.": "I"}
    rows, _ = parse_poll_tables(AK_RCV, race_id="SEN-AK-2026",
                                principals={"D": "Mary Peltola", "R": "Dan S. Sullivan"},
                                matcher=NomineeMatcher(nominees))
    assert [r["rcv_round"] for r in rows] == [1, 2]
    r1 = rows[0]
    assert (r1["dem_pct"], r1["rep_pct"]) == (48.0, 46.0)
    assert r1["extra_candidates"] == ["Gerald Heikes"]
    shares = {c["name"]: c["pct"] for c in r1["candidates"]}
    assert shares["Daniel J. Sullivan Jr."] == 3.0  # Dan J. Sullivan (I) matched by initials
    assert rows[0]["poll_group"] == rows[1]["poll_group"]


GENERIC = (
    H(2, "2025–2026")
    + poll_table(["Democratic", "Republican", "Other/ Undecided", "Lead"], [
        ("<tr><td>John Zogby Strategies</td><td>November 1–2, 2026</td><td>1,001 (LV)</td>"
        "<td>± 3.2%</td><td>53%</td><td>47%</td><td>—</td><td>6%</td></tr>")])
)


def test_generic_ballot_party_columns():
    (r,), _ = parse_poll_tables(GENERIC, race_id="GEN-US-2026", principals={"D": "Democratic", "R": "Republican"},
                                matcher=None)
    assert (r["dem_pct"], r["rep_pct"], r["other_pct"]) == (53.0, 47.0, None)


HOUSE = (
    H(2, "District 1") + H(3, "General election") + H(4, "Polling")
    + poll_table(["Jay Feely (R)", "Amish Shah (D)", "Undecided"], [
        ("<tr><td>FirstStrategic</td><td>October 1, 2026</td><td>400 (LV)</td><td>± 5.4%</td>"
        "<td>42%</td><td>44%</td><td>14%</td></tr>")])
    + poll_table(["Jay Feely (R)", "Generic Democrat", "Undecided"], [
        ("<tr><td>Grayhouse (R)</td><td>November 15–17, 2025</td><td>500 (LV)</td><td>± 4.4%</td>"
        "<td>42%</td><td>42%</td><td>16%</td></tr>")])
    + H(2, "District 6") + H(3, "General election") + H(4, "Polling")
    + poll_table(["Juan Ciscomani (R)", "JoAnna Mendoza (D)"], [
        ("<tr><td>Noble Predictive</td><td>October 10–14, 2026</td><td>450 (LV)</td><td>± 4.6%</td>"
        "<td>47%</td><td>48%</td></tr>")])
)


def test_house_page_resolves_district_from_section():
    districts = {
        "HOU-AZ01-2026": {"D": "Amish Shah", "R": "Jay Feely", "D_party": "D"},
        "HOU-AZ06-2026": {"D": "JoAnna Mendoza", "R": "Juan Ciscomani", "D_party": "D"},
    }
    rows, log = parse_poll_tables(HOUSE, race_id=None, state="AZ", house_districts=districts)
    assert [(r["race_id"], r["pollster_raw"]) for r in rows] == [
        ("HOU-AZ01-2026", "FirstStrategic"), ("HOU-AZ06-2026", "Noble Predictive")]
    assert any(x["reason"] == "not_final_matchup" for x in log)  # "Generic Democrat" table
