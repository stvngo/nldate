"""Test suite for ``nldate.parse``.

All relative expressions are evaluated against a fixed reference date so the
expected results are deterministic:

    TODAY = 2025-11-12 (a Wednesday)

Weekday / "tomorrow" / "yesterday" anchors from that date:

    yesterday = 2025-11-11 (Tuesday)
    tomorrow  = 2025-11-13 (Thursday)
"""

from datetime import date

import pytest

from nldate import parse

# Reference "today" used for every relative expression below.
TODAY = date(2025, 11, 12)  # Wednesday


# ---------------------------------------------------------------------------
# The four headline examples from the project description.
# ---------------------------------------------------------------------------


def test_five_days_before_absolute_date() -> None:
    # "Five days before December 1st, 2025" -> Dec 1 minus 5 days.
    assert parse("Five days before December 1st, 2025", today=TODAY) == date(2025, 11, 26)


def test_next_tuesday() -> None:
    # From Wednesday 2025-11-12, the next Tuesday is 2025-11-18.
    assert parse("Next Tuesday", today=TODAY) == date(2025, 11, 18)


def test_one_year_and_two_months_after_yesterday() -> None:
    # yesterday = 2025-11-11; +1 year +2 months -> 2027-01-11.
    assert parse("One year and two months after yesterday", today=TODAY) == date(2027, 1, 11)


def test_two_weeks_from_tomorrow() -> None:
    # tomorrow = 2025-11-13; +2 weeks -> 2025-11-27.
    assert parse("Two weeks from tomorrow", today=TODAY) == date(2025, 11, 27)


# ---------------------------------------------------------------------------
# Simple keyword anchors.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("today", date(2025, 11, 12)),
        ("Today", date(2025, 11, 12)),
        ("tomorrow", date(2025, 11, 13)),
        ("yesterday", date(2025, 11, 11)),
    ],
)
def test_keyword_anchors(text: str, expected: date) -> None:
    assert parse(text, today=TODAY) == expected


def test_today_defaults_to_current_date() -> None:
    # When no reference is given, "today" should be the real current date.
    assert parse("today") == date.today()


# ---------------------------------------------------------------------------
# Absolute dates in a few common spellings.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("December 1st, 2025", date(2025, 12, 1)),
        ("December 1, 2025", date(2025, 12, 1)),
        ("Dec 1 2025", date(2025, 12, 1)),
        ("1 December 2025", date(2025, 12, 1)),
        ("2025-12-01", date(2025, 12, 1)),
        ("January 3rd, 2026", date(2026, 1, 3)),
    ],
)
def test_absolute_dates(text: str, expected: date) -> None:
    # Absolute dates do not depend on the reference date.
    assert parse(text, today=TODAY) == expected


# ---------------------------------------------------------------------------
# Relative offsets ("in N units", "N units ago", "N units from/before X").
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("in three days", date(2025, 11, 15)),
        ("in 3 days", date(2025, 11, 15)),
        ("three days ago", date(2025, 11, 9)),
        ("3 days ago", date(2025, 11, 9)),
        ("in two weeks", date(2025, 11, 26)),
        ("in one month", date(2025, 12, 12)),
        ("in a week", date(2025, 11, 19)),
    ],
)
def test_relative_offsets(text: str, expected: date) -> None:
    assert parse(text, today=TODAY) == expected


def test_days_from_today() -> None:
    assert parse("five days from today", today=TODAY) == date(2025, 11, 17)


def test_before_relative_anchor() -> None:
    # "a week before tomorrow" -> tomorrow (2025-11-13) minus 7 days.
    assert parse("a week before tomorrow", today=TODAY) == date(2025, 11, 6)


# ---------------------------------------------------------------------------
# Weekday expressions.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("next Friday", date(2025, 11, 14)),
        ("this Monday", date(2025, 11, 17)),
        ("last Friday", date(2025, 11, 7)),
        ("Sunday", date(2025, 11, 16)),
    ],
)
def test_weekdays(text: str, expected: date) -> None:
    assert parse(text, today=TODAY) == expected


# ---------------------------------------------------------------------------
# Compound durations ("one year and two months", "a year and a day").
# ---------------------------------------------------------------------------


def test_compound_duration_after() -> None:
    assert parse("one year and two months after today", today=TODAY) == date(2027, 1, 12)


def test_compound_duration_before() -> None:
    # "two months and ten days before December 1st, 2025"
    # Dec 1 2025 - 2 months -> 2025-10-01; - 10 days -> 2025-09-21.
    assert parse("two months and ten days before December 1st, 2025", today=TODAY) == date(
        2025, 9, 21
    )


# ---------------------------------------------------------------------------
# Whitespace / case robustness.
# ---------------------------------------------------------------------------


def test_surrounding_whitespace_is_ignored() -> None:
    assert parse("   next Tuesday   ", today=TODAY) == date(2025, 11, 18)


def test_case_insensitive() -> None:
    assert parse("TWO WEEKS FROM TOMORROW", today=TODAY) == date(2025, 11, 27)


# ---------------------------------------------------------------------------
# Error handling: unrecognized input must raise ValueError.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "not a date",
        "hello world",
        "the fifth of neveruary",
        "banana",
    ],
)
def test_unrecognized_input_raises_value_error(text: str) -> None:
    with pytest.raises(ValueError):
        parse(text, today=TODAY)
