"""Deterministic (non-LLM) normalization of spoken time/number/currency
phrases. Runs BEFORE the transcript reaches Mistral, so the LLM never has to
touch numbers/times/money — it corrupted unrelated words when asked to (e.g.
"before Thursday" -> "before 16:00" in testing). Regex only ever replaces text
it's confident about; anything ambiguous or unmatched is left untouched rather
than guessed at, on the same "never invent, never guess" principle as the rest
of this app.

Known scope limits (deliberate, to avoid ambiguous guesses):
- Bare "<number> hours"/"<number> hundred hours" (e.g. "1500 hours") is NOT
  converted — it's genuinely ambiguous between a clock time and a duration
  ("the flight takes 15 hours"). Only the decimal form ("9.30 hours") and
  explicit am/pm forms are converted, since those are unambiguous.
- Currency defaults to no conversion when no unit is named (no reliable way
  to tell via regex that a bare number is meant as money).
- Dates are never touched (by requirement — kept exactly as spoken).
"""

import re

from word2number import w2n

_NUMBER_WORDS = (
    r"zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|"
    r"thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand"
)
_NUMBER_WORD_SEQUENCE = rf"(?:(?:{_NUMBER_WORDS})[\s-]+)*(?:{_NUMBER_WORDS})"
_NUMBER_WORD_SEQUENCE_RE = re.compile(rf"\b{_NUMBER_WORD_SEQUENCE}\b", re.IGNORECASE)

_HOUR_WORD_RE = re.compile(r"^(\d{1,2}|[a-zA-Z]+)$")


def _word_to_int(span: str) -> int | None:
    if span.isdigit():
        return int(span)
    try:
        return w2n.word_to_num(span)
    except ValueError:
        return None


def _fmt(hour: int, minute: int = 0) -> str:
    return f"{hour % 24:02d}:{minute % 60:02d}"


def _apply_meridiem(hour: int, meridiem: str) -> int:
    meridiem = meridiem.lower()
    if meridiem == "a":
        return 0 if hour == 12 else hour
    return 12 if hour == 12 else hour + 12


_MERIDIEM_COLON_RE = re.compile(
    r"\b(1[0-2]|0?[1-9])[:.]([0-5]\d)\s*([ap])\.?\s*m\.?\b", re.IGNORECASE
)
_MERIDIEM_HOUR_ONLY_RE = re.compile(
    r"\b(1[0-2]|0?[1-9])\s*([ap])\.?\s*m\.?\b", re.IGNORECASE
)
_DOTTED_HOUR_RE = re.compile(r"\b([01]?\d|2[0-3])\.([0-5]\d)\s+hours?\b", re.IGNORECASE)
_HALF_PAST_RE = re.compile(r"\bhalf past (\d{1,2}|[a-zA-Z]+)\b", re.IGNORECASE)
_QUARTER_PAST_RE = re.compile(r"\bquarter past (\d{1,2}|[a-zA-Z]+)\b", re.IGNORECASE)
_QUARTER_TO_RE = re.compile(r"\bquarter to (\d{1,2}|[a-zA-Z]+)\b", re.IGNORECASE)
_NOON_RE = re.compile(r"\bnoon\b", re.IGNORECASE)
_MIDNIGHT_RE = re.compile(r"\bmidnight\b", re.IGNORECASE)


def _hour_word_value(span: str) -> int | None:
    value = _word_to_int(span)
    if value is None or not (1 <= value <= 12):
        return None
    return value


def convert_times(text: str) -> str:
    """Convert unambiguous spoken/numeric time expressions to 24-hour HH:MM."""

    def sub_colon(m):
        hour, minute, mer = int(m.group(1)), int(m.group(2)), m.group(3)
        return _fmt(_apply_meridiem(hour, mer), minute)

    def sub_hour_only(m):
        hour, mer = int(m.group(1)), m.group(2)
        return _fmt(_apply_meridiem(hour, mer))

    def sub_dotted(m):
        return _fmt(int(m.group(1)), int(m.group(2)))

    def sub_half_past(m):
        hour = _hour_word_value(m.group(1))
        return _fmt(hour, 30) if hour is not None else m.group(0)

    def sub_quarter_past(m):
        hour = _hour_word_value(m.group(1))
        return _fmt(hour, 15) if hour is not None else m.group(0)

    def sub_quarter_to(m):
        hour = _hour_word_value(m.group(1))
        return _fmt(hour - 1, 45) if hour is not None else m.group(0)

    text = _MERIDIEM_COLON_RE.sub(sub_colon, text)
    text = _MERIDIEM_HOUR_ONLY_RE.sub(sub_hour_only, text)
    text = _DOTTED_HOUR_RE.sub(sub_dotted, text)
    text = _HALF_PAST_RE.sub(sub_half_past, text)
    text = _QUARTER_PAST_RE.sub(sub_quarter_past, text)
    text = _QUARTER_TO_RE.sub(sub_quarter_to, text)
    text = _NOON_RE.sub("12:00", text)
    text = _MIDNIGHT_RE.sub("00:00", text)
    return text


_CURRENCY_SYMBOLS = {"dollar": "$", "euro": "€", "pound": "£"}
_CURRENCY_AMOUNT_RE = re.compile(
    rf"\b({_NUMBER_WORD_SEQUENCE}|\d+(?:\.\d+)?)\s+(dollars?|euros?|pounds?)\b",
    re.IGNORECASE,
)


def convert_currency(text: str) -> str:
    """Convert '<amount> dollars/euros/pounds' into symbol+digit, e.g. $20."""

    def sub(m):
        amount_span, unit = m.group(1), m.group(2).lower().rstrip("s")
        amount = _word_to_int(amount_span)
        if amount is None:
            return m.group(0)
        symbol = _CURRENCY_SYMBOLS[unit]
        return f"{symbol}{amount}"

    return _CURRENCY_AMOUNT_RE.sub(sub, text)


def convert_numbers(text: str, min_value: int = 5) -> str:
    """Convert spelled-out numbers >= min_value to digits. Smaller numbers
    (one, two, three, four) are left as words — casual counts read better
    spelled out, per user preference."""

    def sub(m):
        value = _word_to_int(m.group(0))
        if value is None or value < min_value:
            return m.group(0)
        return str(value)

    return _NUMBER_WORD_SEQUENCE_RE.sub(sub, text)


def normalize(text: str) -> str:
    """Apply time, then currency, then number conversion, in that order."""
    text = convert_times(text)
    text = convert_currency(text)
    text = convert_numbers(text)
    return text
