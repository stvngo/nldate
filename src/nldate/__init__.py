"""nldate: turn natural language date strings into concrete dates.

The public entry point is :func:`parse`, which accepts expressions such as:

* ``"December 1st, 2025"``
* ``"Five days before December 1st, 2025"``
* ``"Next Tuesday"``
* ``"Two weeks from tomorrow"``
* ``"One year and two months after yesterday"``
* ``"in three days"`` / ``"three days ago"``

and returns the :class:`datetime.date` they refer to. Relative expressions are
resolved against a reference date (``today``), which defaults to the current
date.
"""

from __future__ import annotations

import calendar
import re
import sys
from datetime import date, timedelta

__all__ = ["parse"]


# --- Lookup tables ---------------------------------------------------------

_MONTHS: dict[str, int] = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sept": 9,
    "sep": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}

# Monday is 0, matching datetime.date.weekday().
_WEEKDAYS: dict[str, int] = {
    "monday": 0,
    "mon": 0,
    "tuesday": 1,
    "tue": 1,
    "tues": 1,
    "wednesday": 2,
    "wed": 2,
    "weds": 2,
    "thursday": 3,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "friday": 4,
    "fri": 4,
    "saturday": 5,
    "sat": 5,
    "sunday": 6,
    "sun": 6,
}

_ONES: dict[str, int] = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}

_TENS: dict[str, int] = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}

# Each unit maps to (months, days) contributed by a single count of it.
_UNITS: dict[str, tuple[int, int]] = {
    "day": (0, 1),
    "days": (0, 1),
    "week": (0, 7),
    "weeks": (0, 7),
    "fortnight": (0, 14),
    "fortnights": (0, 14),
    "month": (1, 0),
    "months": (1, 0),
    "year": (12, 0),
    "years": (12, 0),
}

# Relation keywords that separate a duration from an anchor, with the sign
# applied to the duration. Order matters: these are checked before the
# "in ..." / "... ago" shorthands.
_RELATIONS: tuple[tuple[str, int], ...] = (
    (" before ", -1),
    (" after ", 1),
    (" from ", 1),
)

_WEEKDAY_MODIFIERS = frozenset({"next", "this", "last", "coming", "upcoming"})

_ORDINAL_RE = re.compile(r"\b(\d+)(?:st|nd|rd|th)\b")
_ISO_RE = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")
_SLASH_RE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
_SLASH_YMD_RE = re.compile(r"(\d{4})/(\d{1,2})/(\d{1,2})")


# --- Normalization ---------------------------------------------------------


def _normalize(text: str) -> str:
    """Lower-case, drop commas/periods and ordinal suffixes, collapse whitespace.

    Periods are dropped so an abbreviated month name written with a trailing
    period (e.g. ``"Dec."``) matches the month table.
    """
    lowered = text.strip().lower().replace(",", " ").replace(".", " ")
    without_ordinals = _ORDINAL_RE.sub(r"\1", lowered)
    return " ".join(without_ordinals.split())


# --- Number words ----------------------------------------------------------


def _words_to_number(words: list[str]) -> int:
    """Convert a list of number tokens (e.g. ``["twenty", "one"]``) to an int."""
    total = 0
    current = 0
    seen = False
    for word in words:
        for part in word.split("-"):
            if not part:
                continue
            seen = True
            if part in ("a", "an"):
                current += 1
            elif part.isdigit():
                current += int(part)
            elif part in _ONES:
                current += _ONES[part]
            elif part in _TENS:
                current += _TENS[part]
            elif part == "hundred":
                current = (current or 1) * 100
            else:
                raise ValueError(f"Unrecognized number word: {part!r}")
    if not seen:
        raise ValueError("Expected a number")
    return total + current


# --- Durations -------------------------------------------------------------


def _parse_duration(text: str) -> tuple[int, int]:
    """Parse a duration like ``"one year and two months"`` into (months, days)."""
    months = 0
    days = 0
    number_words: list[str] = []
    matched = False
    for token in text.split():
        if token == "and":
            continue
        if token in _UNITS:
            quantity = _words_to_number(number_words) if number_words else 1
            per_month, per_day = _UNITS[token]
            months += quantity * per_month
            days += quantity * per_day
            number_words = []
            matched = True
        else:
            number_words.append(token)
    if number_words or not matched:
        raise ValueError(f"Unrecognized duration: {text!r}")
    return months, days


def _add_months(anchor: date, months: int) -> date:
    """Shift ``anchor`` by a number of months, clamping to end-of-month."""
    index = anchor.month - 1 + months
    year = anchor.year + index // 12
    month = index % 12 + 1
    day = min(anchor.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _apply_duration(anchor: date, months: int, days: int, sign: int) -> date:
    shifted = _add_months(anchor, sign * months)
    return shifted + timedelta(days=sign * days)


# --- Anchors (today / weekdays / absolute dates) ---------------------------


def _parse_weekday(text: str, today: date) -> date | None:
    tokens = text.split()
    if not tokens:
        return None
    modifier: str | None = None
    if tokens[0] in _WEEKDAY_MODIFIERS:
        modifier = tokens[0]
        tokens = tokens[1:]
    if len(tokens) != 1 or tokens[0] not in _WEEKDAYS:
        return None
    target = _WEEKDAYS[tokens[0]]
    current = today.weekday()
    if modifier == "last":
        behind = (current - target) % 7 or 7
        return today - timedelta(days=behind)
    if modifier == "next":
        ahead = (target - current) % 7 or 7
        return today + timedelta(days=ahead)
    # "this", "coming", or a bare weekday name: the next upcoming occurrence.
    return today + timedelta(days=(target - current) % 7)


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _parse_absolute(text: str) -> date | None:
    tokens = text.split()
    if len(tokens) == 1:
        iso = _ISO_RE.fullmatch(tokens[0])
        if iso is not None:
            return _safe_date(int(iso[1]), int(iso[2]), int(iso[3]))
        ymd = _SLASH_YMD_RE.fullmatch(tokens[0])
        if ymd is not None:  # year-first: YYYY/MM/DD
            return _safe_date(int(ymd[1]), int(ymd[2]), int(ymd[3]))
        slash = _SLASH_RE.fullmatch(tokens[0])
        if slash is not None:  # month-first: M/D/Y
            return _safe_date(int(slash[3]), int(slash[1]), int(slash[2]))
        return None
    if len(tokens) == 3:
        first, second, third = tokens
        if first in _MONTHS and second.isdigit() and third.isdigit():
            return _safe_date(int(third), _MONTHS[first], int(second))
        if second in _MONTHS and first.isdigit() and third.isdigit():
            return _safe_date(int(third), _MONTHS[second], int(first))
    return None


def _parse_anchor(text: str, today: date) -> date:
    if text in ("today", "now"):
        return today
    if text == "tomorrow":
        return today + timedelta(days=1)
    if text == "yesterday":
        return today - timedelta(days=1)
    weekday = _parse_weekday(text, today)
    if weekday is not None:
        return weekday
    absolute = _parse_absolute(text)
    if absolute is not None:
        return absolute
    raise ValueError(f"Unrecognized date expression: {text!r}")


# --- Public API ------------------------------------------------------------


def parse(text: str, today: date | None = None) -> date:
    """Resolve a natural language date expression to a concrete date.

    Args:
        text: The natural language expression, e.g. ``"next Tuesday"`` or
            ``"five days before December 1st, 2025"``.
        today: Reference date for relative expressions. Defaults to the
            current date when omitted.

    Returns:
        The :class:`datetime.date` the expression refers to.

    Raises:
        ValueError: If ``text`` is empty or not a recognized date expression.
    """
    if today is None:
        today = date.today()

    normalized = _normalize(text)
    if not normalized:
        raise ValueError("Cannot parse an empty date expression")

    for keyword, sign in _RELATIONS:
        if keyword in normalized:
            left, right = normalized.split(keyword, 1)
            months, days = _parse_duration(left)
            anchor = _parse_anchor(right.strip(), today)
            return _apply_duration(anchor, months, days, sign)

    if normalized.startswith("in "):
        months, days = _parse_duration(normalized[len("in ") :])
        return _apply_duration(today, months, days, 1)

    if normalized.endswith(" ago"):
        months, days = _parse_duration(normalized[: -len(" ago")])
        return _apply_duration(today, months, days, -1)

    return _parse_anchor(normalized, today)


def main() -> None:
    """Minimal CLI: parse the argument expression and print the ISO date."""
    expression = " ".join(sys.argv[1:]).strip()
    if not expression:
        print("usage: nldate <expression>")
        return
    try:
        result = parse(expression)
    except ValueError as exc:
        print(f"error: {exc}")
        raise SystemExit(1) from exc
    print(result.isoformat())
