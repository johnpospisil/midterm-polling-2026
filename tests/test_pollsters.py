"""Pollster name normalisation and the cited methods table."""

import polars as pl
import pytest

from mp.build.pollsters import attach_methods, canonical_pollster, methods_wide, validate_methods


@pytest.mark.parametrize("raw,pollster,partner", [
    ("Emerson College", "Emerson College", ""),
    ("CNN /SSRS", "SSRS", "CNN"),  # media sponsor, SSRS does the fieldwork
    ("KTSP / SurveyUSA", "SurveyUSA", "KSTP"),  # typo in the sponsor fixed
    ("Bowling Green State University / YouGov", "YouGov", "Bowling Green State University"),
    ("The Economist / YouGov", "YouGov", "The Economist"),
    ("Strength In Numbers /Verasight", "Verasight", "Strength In Numbers"),
    ("YouGov Blue", "YouGov Blue", ""),  # a separate arm, not YouGov itself
    ("The New York Times / The Philadelphia Inquirer / Siena University",
     "New York Times / Siena", "The Philadelphia Inquirer"),
    ("New York Times / Siena College", "New York Times / Siena", ""),
    ("Siena College", "Siena University", ""),
    # bipartisan teams stay a team
    ("Fabrizio Ward (R)/ Impact Research", "Fabrizio Ward / Impact Research", ""),
    ("Hart Research Associates (D)/Public Opinion Strategies",
     "Hart Research / Public Opinion Strategies", ""),
    ("Beacon Research (D)/ Shaw & Co. Research", "Beacon Research / Shaw & Co. Research", ""),
    # spelling variants
    ("Grayhouse", "GrayHouse", ""),
    ("Public Opinon Strategies", "Public Opinion Strategies", ""),
    ("McLaughlin and Associates", "McLaughlin & Associates", ""),
    ("I&I/TIPP Insights", "TIPP Insights", "I&I"),
    ("Washington Post / ABC News / Ipsos", "Ipsos", "Washington Post / ABC News"),
    ("Some New Firm", "Some New Firm", ""),
    ("co/efficient", "co/efficient", ""),  # one firm whose name contains a slash
])
def test_canonical_pollster(raw, pollster, partner):
    assert canonical_pollster(raw) == (pollster, partner)


def _methods(rows, scope="all"):
    cols = ["pollster", "field", "value", "source_url", "accessed", "evidence"]
    return pl.DataFrame([dict(zip(cols, r)) | {"scope": scope} for r in rows])


def test_methods_wide_one_row_per_pollster_with_unknown_default():
    long = _methods([
        ("Emerson College", "mode_main", "mixed", "https://e", "2026-11-10", "text-to-web and IVR"),
        ("Emerson College", "weight_recalled_vote", "yes", "https://e", "2026-11-10", "2024 vote"),
        ("SSRS", "mode_main", "probability_panel", "https://s", "2026-11-10", "SSRS Opinion Panel"),
    ])
    wide = methods_wide(long).sort("pollster")
    assert wide["pollster"].to_list() == ["Emerson College", "SSRS"]
    assert wide["mode_main"].to_list() == ["mixed", "probability_panel"]
    assert wide["weight_recalled_vote"].to_list() == ["yes", "unknown"]
    assert wide["aapor_ti"].to_list() == ["unknown", "unknown"]


def test_validate_rejects_bad_values_and_missing_citations():
    bad = _methods([
        ("A", "mode_main", "telepathy", "https://a", "2026-11-10", "x"),
        ("B", "weight_education", "yes", "", "2026-11-10", "x"),
        ("C", "weight_party", "maybe", "https://c", "2026-11-10", "x"),
    ])
    problems = validate_methods(bad)
    assert len(problems) == 3


def test_validate_allows_unknown_without_a_source():
    ok = _methods([("A", "weight_education", "unknown", "", "", "not stated in release")])
    assert validate_methods(ok) == []


def test_not_listed_is_a_valid_answer_with_a_citation():
    # the release lists its weighting variables and this one isn't among them
    ok = _methods([("A", "weight_recalled_vote", "not_listed", "https://a", "2026-11-10", "age, sex")])
    assert validate_methods(ok) == []


def test_methods_scope_own_applies_only_to_polls_without_a_partner():
    long = pl.concat([
        _methods([("YouGov", "mode_main", "text_to_web", "https://y", "2026-11-10", "ttw")], scope="own"),
        _methods([("SSRS", "mode_main", "probability_panel", "https://s", "2026-11-10", "p")]),
    ])
    polls = pl.DataFrame({"poll_id": ["a", "b", "c"], "pollster": ["YouGov", "YouGov", "SSRS"],
                          "partner": ["", "UMass Amherst", "CNN"]})
    out = attach_methods(polls, methods_wide(long)).sort("poll_id")
    assert out["mode_main"].to_list() == ["text_to_web", "unknown", "probability_panel"]
    assert out["methods_coded"].to_list() == [True, False, True]
