import pytest

import normalize


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("The meeting is at 3 pm sharp.", "The meeting is at 15:00 sharp."),
        ("See you at 3:00 p.m.", "See you at 15:00."),
        ("Call me at 9:30 am.", "Call me at 09:30."),
        ("Call me at 9.30 am.", "Call me at 09:30."),
        ("It's 9 am already.", "It's 09:00 already."),
        ("Switch it to 9.30 hour.", "Switch it to 09:30."),
        ("Switch it to 9.30 hours.", "Switch it to 09:30."),
        ("Meet at half past nine.", "Meet at 09:30."),
        ("Meet at quarter past three.", "Meet at 03:15."),
        ("Meet at quarter to three.", "Meet at 02:45."),
        ("Lunch is at noon.", "Lunch is at 12:00."),
        ("Curfew is midnight.", "Curfew is 00:00."),
    ],
)
def test_convert_times(raw, expected):
    assert normalize.convert_times(raw) == expected


def test_bare_hours_not_converted_ambiguous_with_duration():
    # "1500 hours" could be a clock time or a 1500-hour duration — deliberately
    # left untouched rather than guessed at.
    text = "Book it for 1500 hours instead."
    assert normalize.convert_times(text) == text


def test_thursday_not_mistaken_for_a_time():
    # Regression: an LLM asked to do this conversion once corrupted "before
    # Thursday" into "before 16:00". The regex approach must never touch it.
    text = "Email me before Thursday."
    assert normalize.convert_times(text) == text


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("It costs twenty dollars.", "It costs $20."),
        ("It costs 20 dollars.", "It costs $20."),
        ("Pay one hundred pounds.", "Pay £100."),
        ("It's five euros.", "It's €5."),
    ],
)
def test_convert_currency(raw, expected):
    assert normalize.convert_currency(raw) == expected


def test_convert_currency_leaves_unspecified_amounts_alone():
    text = "It costs twenty."
    assert normalize.convert_currency(text) == text


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("There's three reasons why.", "There's three reasons why."),
        ("I have one idea.", "I have one idea."),
        ("There are twenty files.", "There are 20 files."),
        ("Version twelve is out.", "Version 12 is out."),
        ("We need five more.", "We need 5 more."),
    ],
)
def test_convert_numbers_respects_threshold(raw, expected):
    assert normalize.convert_numbers(raw) == expected


def test_normalize_applies_all_three_in_order():
    text = "The call is at 3 pm, costs twenty dollars, and needs twelve people."
    result = normalize.normalize(text)
    assert result == "The call is at 15:00, costs $20, and needs 12 people."


def test_normalize_does_not_touch_unrelated_words():
    text = "Email Sara about the budget report by Wednesday."
    assert normalize.normalize(text) == text
