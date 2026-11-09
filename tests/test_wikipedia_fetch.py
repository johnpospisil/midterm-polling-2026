import pytest

from mp.geo import race_id
from mp.ingest.wikipedia_polls import classify


@pytest.mark.parametrize(
    "title,kind,rid,special",
    [
        ("2026 United States Senate election in Michigan", "senate", "SEN-MI-2026", False),
        ("2026 United States Senate special election in Ohio", "senate", "SEN-OH-2026", True),
        ("2026 United States Senate election in New Hampshire", "senate", "SEN-NH-2026", False),
        ("2026 New Hampshire gubernatorial election", "governor", "GOV-NH-2026", False),
        ("2026 United States House of Representatives elections in Texas", "house_state", None, False),
        ("2026 United States House of Representatives election in Alaska", "house_state", None, False),
        ("2026 United States House of Representatives elections in California (districts 1–26)",
         "house_state", None, False),
        ("2026 United States House of Representatives elections", "overview_house", "GEN-US-2026", False),
    ],
)
def test_classify_us_race_pages(title, kind, rid, special):
    p = classify(title)
    assert p is not None
    assert (p.page_kind, p.race_id, p.special) == (kind, rid, special)


@pytest.mark.parametrize(
    "title",
    [
        "2026 Osaka gubernatorial election",
        "2026 Guam gubernatorial election",
        "2026 Texas lieutenant gubernatorial election",
        "2026 United States Shadow Senator election in the District of Columbia",
        "2026 Maine Senate election",  # state legislature, not US Senate
    ],
)
def test_classify_rejects_non_us_race_pages(title):
    assert classify(title) is None


def test_race_id_formats():
    assert race_id("HOU", "AZ", "6") == "HOU-AZ06-2026"
    assert race_id("HOU", "AK", "AL") == "HOU-AKAL-2026"
    assert race_id("GEN", "US") == "GEN-US-2026"
    with pytest.raises(ValueError):
        race_id("PRES", "PA")
