"""Sign convention: margin = D - R (two-party), signed error = poll - result; + means polls overstated D."""

import pytest

from mp.build.margins import signed_error, two_party_margin, two_party_share


def test_two_party_margin_positive_means_democratic_lead():
    assert two_party_margin(52, 48) == pytest.approx(4.0)
    assert two_party_margin(45, 50) == pytest.approx(-100 * 5 / 95)


def test_two_party_ignores_undecided_and_others():
    # 45 D, 45 R, 10 undecided is a tie in two-party terms
    assert two_party_margin(45, 45) == 0
    assert two_party_share(45, 45) == pytest.approx(50)
    # 40-30 with 30 undecided: D gets 4/7 of the two-party vote
    assert two_party_share(40, 30) == pytest.approx(400 / 7)
    assert two_party_margin(40, 30) == pytest.approx(100 * 10 / 70)


def test_missing_or_zero_shares_give_none():
    assert two_party_margin(None, 40) is None
    assert two_party_margin(0, 0) is None


def test_signed_error_positive_when_polls_overstate_democrats():
    # poll D+5, result D+2 -> polls overstated Democrats by 3
    assert signed_error(5.0, 2.0) == pytest.approx(3.0)
    # poll R+1 (−1), result R+4 (−4) -> still overstated Democrats by 3
    assert signed_error(-1.0, -4.0) == pytest.approx(3.0)
    # poll D+1, result R+3 -> overstated Democrats by 4
    assert signed_error(1.0, -3.0) == pytest.approx(4.0)
    # poll R+6, result R+2 -> overstated Republicans: negative
    assert signed_error(-6.0, -2.0) == pytest.approx(-4.0)
