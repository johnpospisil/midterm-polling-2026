"""Candidate-name matching between table headers and nominee lists."""

from __future__ import annotations

import re

_SUFFIX = {"jr", "sr", "ii", "iii", "iv"}


def name_tokens(name: str) -> list[str]:
    name = re.sub(r"\(.*?\)", " ", name)  # party tags, "(replacing ...)" notes
    toks = [re.sub(r"[^a-z\-]", "", t) for t in name.lower().replace(",", " ").split()]
    return [t for t in toks if t and t not in _SUFFIX]


def surname(name: str) -> str:
    t = name_tokens(name)
    return t[-1] if t else ""


class NomineeMatcher:
    """Match a header name to a nominee, in tiers:

    1. first name + surname ("Dan Sullivan" -> Dan S. Sullivan)
    2. first initial + middle initial + surname ("Dan J. Sullivan" -> Daniel J. Sullivan Jr.)
    3. surname alone, only if no other nominee shares it.

    Alaska 2026 Senate has Dan S. Sullivan (R) and Daniel J. Sullivan Jr. (I), hence the tiers.
    """

    def __init__(self, nominees: dict[str, str]):
        self.nominees = nominees
        self._toks = {n: name_tokens(n) for n in nominees}

    def __bool__(self) -> bool:
        return bool(self.nominees)

    @staticmethod
    def _middle_ok(a: list[str], b: list[str]) -> bool:
        """Middle initials, when both names have one, must agree."""
        return not (len(a) >= 3 and len(b) >= 3 and a[1][0] != b[1][0])

    def _unique(self, pred) -> tuple[str, str] | None:
        hits = [n for n, t in self._toks.items() if t and pred(t)]
        return (hits[0], self.nominees[hits[0]]) if len(hits) == 1 else None

    def match(self, header_name: str) -> tuple[str, str] | None:
        h = name_tokens(header_name)
        if not h:
            return None
        tiers = [
            lambda t: t[0] == h[0] and t[-1] == h[-1] and self._middle_ok(t, h),
            lambda t: len(h) >= 3 and len(t) >= 3 and t[0][0] == h[0][0] and t[1][0] == h[1][0]
            and t[-1] == h[-1],
            lambda t: t[-1] == h[-1] and self._middle_ok(t, h),
        ]
        for pred in tiers:
            if hit := self._unique(pred):
                return hit
        return None
