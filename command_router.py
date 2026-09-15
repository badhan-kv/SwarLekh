"""Detect a spoken trigger phrase at the start of a transcript and route it."""

import re

MODE_TRANSCRIBE = "transcribe"
MODE_NOTES = "notes"

# Longest/most-specific phrases first so "take notes" isn't shadowed by a shorter match.
TRIGGER_PHRASES = [
    ("take notes", MODE_NOTES),
    ("voice dictation", MODE_TRANSCRIBE),
    ("transcribe", MODE_TRANSCRIBE),
]


def route(raw_transcript: str) -> tuple[str, str]:
    """Return (mode, transcript_with_trigger_phrase_stripped).

    Defaults to MODE_TRANSCRIBE if no trigger phrase was said, so dictation still
    works if the command word is forgotten.
    """
    stripped = raw_transcript.strip()
    lowered = stripped.lower()
    for phrase, mode in TRIGGER_PHRASES:
        if lowered.startswith(phrase):
            remainder = stripped[len(phrase):]
            remainder = re.sub(r"^[\s,.:;-]+", "", remainder)
            return mode, remainder
    return MODE_TRANSCRIBE, stripped
