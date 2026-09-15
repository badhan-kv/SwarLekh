import pytest

import command_router as cr


@pytest.mark.parametrize(
    "raw, expected_mode, expected_text",
    [
        ("transcribe, this is a test", cr.MODE_TRANSCRIBE, "this is a test"),
        ("Transcribe this is a test", cr.MODE_TRANSCRIBE, "this is a test"),
        ("voice dictation hello there", cr.MODE_TRANSCRIBE, "hello there"),
        ("take notes about the meeting today", cr.MODE_NOTES, "about the meeting today"),
        ("Take Notes: buy milk, call mom", cr.MODE_NOTES, "buy milk, call mom"),
        ("just some words with no trigger", cr.MODE_TRANSCRIBE, "just some words with no trigger"),
        ("  transcribe   leading whitespace test", cr.MODE_TRANSCRIBE, "leading whitespace test"),
        ("", cr.MODE_TRANSCRIBE, ""),
    ],
)
def test_route(raw, expected_mode, expected_text):
    mode, text = cr.route(raw)
    assert mode == expected_mode
    assert text == expected_text


def test_take_notes_not_shadowed_by_no_trigger_phrase():
    # "take notes" must win over falling through to the no-trigger default.
    mode, text = cr.route("take notes I need to remember three things")
    assert mode == cr.MODE_NOTES
    assert text == "I need to remember three things"
