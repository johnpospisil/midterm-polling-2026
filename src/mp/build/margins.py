"""Two-party margins and signed error.

Convention (CLAUDE.md, used everywhere):
- margin = Democratic (D side) share minus Republican share of the TWO-PARTY vote, in points.
  Positive = Democratic lead. Undecided and other candidates are left out.
- signed error = poll margin - result margin. Positive = polls overstated Democrats.
"""

from __future__ import annotations


def two_party_share(dem: float | None, rep: float | None) -> float | None:
    """D side's share of the two-party vote, in percent."""
    if dem is None or rep is None or dem + rep <= 0:
        return None
    return 100.0 * dem / (dem + rep)


def two_party_margin(dem: float | None, rep: float | None) -> float | None:
    """(D - R) / (D + R) in points; 52-48 -> +4, 45-50 -> -5.26."""
    if dem is None or rep is None or dem + rep <= 0:
        return None
    return 100.0 * (dem - rep) / (dem + rep)


def signed_error(poll_margin: float, result_margin: float) -> float:
    """Poll margin minus result margin; positive = polls overstated Democrats."""
    return poll_margin - result_margin
