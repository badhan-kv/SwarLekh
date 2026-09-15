"""Deterministic post-hoc check that a cleanup pass didn't drop or silently
substitute content it was supposed to preserve verbatim. This is what lets
mistral_cleanup.clean() actually VERIFY and retry instead of just hoping the
prompt worked — a substituted word (e.g. "her" -> "Sarah's") shows up here as
the original word going missing, same as an outright dropped word.

Deliberately not perfect: it can't distinguish a wrongly-dropped word from a
correctly-dropped one inside an abandoned/restarted sentence (a real
disfluency-removal case the prompt allows). In practice that's rare relative
to the bugs this actually catches (dropped hedge words, silent substitutions),
so the trade-off favors catching more real issues over zero false positives.
"""

import re

_FILLER_RE = re.compile(r"\b(um+|uh+|erm+|like|so)\b", re.IGNORECASE)
_I_MEAN_RE = re.compile(r"\bi mean\b", re.IGNORECASE)
_WORD_RE = re.compile(r"[a-z0-9']+")


def _normalize_quotes(text: str) -> str:
    return text.replace("’", "'").replace("‘", "'")


def _content_words(text: str) -> set[str]:
    text = _normalize_quotes(text)
    text = _I_MEAN_RE.sub(" ", text)
    text = _FILLER_RE.sub(" ", text)
    return set(_WORD_RE.findall(text.lower()))


def missing_words(source: str, output: str) -> set[str]:
    """Content words present in `source` but absent anywhere in `output`."""
    return _content_words(source) - _content_words(output)
