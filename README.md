# nldate

Turn natural language date strings into concrete dates.

`nldate` parses everyday date expressions — `"Next Tuesday"`, `"Five days before December 1st, 2025"`, `"One year and two months after yesterday"` — and resolves them to a `datetime.date`. Relative expressions are evaluated against a reference date (`today`) that defaults to the current date.

```python
from nldate import parse

parse("Two weeks from tomorrow")
# datetime.date(...)  # relative to today
```

## Features

- **Keyword anchors** — `today`, `tomorrow`, `yesterday`
- **Absolute dates** — month-name, ISO, and numeric spellings, with ordinals and commas
- **Weekdays** — `next Tuesday`, `this Monday`, `last Friday`, or a bare `Sunday`
- **Relative offsets** — `in three days`, `three days ago`, `two weeks from tomorrow`, `a week before tomorrow`
- **Compound durations** — `one year and two months after yesterday`
- Case-insensitive; tolerant of surrounding whitespace and commas
- No runtime dependencies — pure standard library
- Fully type-annotated and `mypy`-clean

## Installation

`nldate` is a [uv](https://docs.astral.sh/uv/)-managed package. It isn't published to PyPI, so install it from source:

```bash
# Add to a uv project, straight from GitHub
uv add git+https://github.com/stvngo/nldate

# …or with pip
pip install git+https://github.com/stvngo/nldate
```

To work on it locally:

```bash
git clone https://github.com/stvngo/nldate
cd nldate
uv sync
```

## Usage

The entire public API is a single function:

```python
def parse(text: str, today: datetime.date | None = None) -> datetime.date: ...
```

- **`text`** — the natural language expression.
- **`today`** — reference date for relative expressions. Defaults to `datetime.date.today()` when omitted.
- **Returns** a `datetime.date`.
- **Raises** `ValueError` if `text` is empty or not a recognized date expression.

### Examples

All relative examples below use a fixed reference date of **Wednesday, 2025-11-12** so the results are reproducible:

```python
import datetime
from nldate import parse

ref = datetime.date(2025, 11, 12)  # a Wednesday

parse("tomorrow", today=ref)  # 2025-11-13
parse("Next Tuesday", today=ref)  # 2025-11-18
parse("last Friday", today=ref)  # 2025-11-07
parse("in three days", today=ref)  # 2025-11-15
parse("three days ago", today=ref)  # 2025-11-09
parse("Two weeks from tomorrow", today=ref)  # 2025-11-27
parse("One year and two months after yesterday", today=ref)  # 2027-01-11

# Absolute dates ignore the reference date
parse("December 1st, 2025", today=ref)  # 2025-12-01
parse("2025-12-01", today=ref)  # 2025-12-01
parse("Five days before December 1st, 2025", today=ref)  # 2025-11-26
```

When `today` is omitted, relative expressions resolve against the current date:

```python
parse("in three days")  # three days from today
```

## Supported expressions

| Category | Examples | Notes |
|---|---|---|
| Keyword anchors | `today`, `tomorrow`, `yesterday` | |
| Absolute dates | `December 1st, 2025`, `Dec 1 2025`, `Dec. 1, 2025`, `1 December 2025`, `2025-12-01`, `2025/12/04`, `12/1/2025` | Ordinals (`1st`, `3rd`), commas, and a trailing period on an abbreviated month (`Dec.`) are tolerated; slash dates may be year-first `YYYY/MM/DD` or month-first `M/D/Y` |
| Weekdays | `next Tuesday`, `this Monday`, `last Friday`, `Sunday` | Full names and common abbreviations (`Tue`, `Weds`, …) |
| Relative offsets | `in three days`, `3 days ago`, `in a week`, `in one month` | |
| Offsets from an anchor | `two weeks from tomorrow`, `a week before tomorrow`, `five days before December 1st, 2025` | Anchor may be a keyword, weekday, or absolute date |
| Compound durations | `one year and two months after yesterday`, `two months and ten days before December 1st, 2025` | |

Supported duration units: **days**, **weeks**, **fortnights**, **months**, **years**. Quantities may be digits (`3`), number words (`three`), or the articles `a`/`an` (meaning 1).

## Semantics

A few conventions are worth calling out:

- **`next <weekday>`** is the first occurrence *strictly after* `today`. **`last <weekday>`** is the most recent occurrence *strictly before* `today`. A bare weekday (or **`this <weekday>`**) is the next upcoming occurrence (today itself if it matches).
- **Month arithmetic clamps to the end of the month.** For example, one month after January 31st is February 28th (or 29th in a leap year).
- **`before`** subtracts a duration from the anchor; **`after`** and **`from`** add it. **`in <duration>`** adds to `today`; **`<duration> ago`** subtracts from `today`.
- Parsing is **case-insensitive** and ignores surrounding whitespace and commas.

## Error handling

Any input that isn't a recognized date — including the empty string — raises `ValueError`:

```python
parse("")  # ValueError
parse("not a date")  # ValueError
parse("banana")  # ValueError
```

## Command line

Installing the package also provides a small CLI that prints the resolved date in ISO format (relative to the current date):

```bash
$ nldate "two weeks from tomorrow"
2025-11-27

$ nldate "December 1st, 2025"
2025-12-01
```

Unrecognized input prints an error and exits with a non-zero status.

## Development

The project uses `uv`, with `pytest`, `mypy`, and `ruff` as dev dependencies:

```bash
uv sync                      # install dependencies
uv run pytest                # run the test suite
uv run mypy src/             # type-check
uv run ruff check            # lint
uv run ruff format --check   # verify formatting
```
