"""Mistral-based cleanup/restructuring of dictation transcripts.

Uses ministral-8b-latest, not mistral-small/medium/large: this account's free
tier no longer has access to those — they return a 429 with a flat 0 req/min
cap (see MODEL_NOT_ON_TIER_HINT below).

Time/number/currency formatting is handled by normalize.py (deterministic
regex), NOT by the LLM: an earlier version asked the model to do this
conversion itself, and it corrupted unrelated content ("before Thursday"
became "before 16:00") once the prompt grew long enough. The LLM's job here
is now scoped to what it's actually reliable at: disfluency removal and (in
notes mode) topic grouping — nothing else.
"""

from mistralai.client import Mistral
from mistralai.client.errors import MistralError

from command_router import MODE_NOTES, MODE_TRANSCRIBE
from normalize import normalize
from retry import get_status, with_retries
from verify import missing_words

DEFAULT_MODEL = "ministral-8b-latest"
DEFAULT_MAX_TOKENS = 2048
DEFAULT_TIMEOUT_MS = 60_000

UNCLEAR_MARKER = "[UNCLEAR]"


def has_unclear_segment(text: str) -> bool:
    """True if `clean()`'s output flagged a segment it couldn't confidently
    transcribe rather than guessing at it — callers should surface this."""
    return UNCLEAR_MARKER in text


MODEL_NOT_ON_TIER_HINT = (
    "Mistral returned a rate limit of 0 requests/minute for model '{model}' — "
    "your account tier has no allowance for it. Your API key is fine; "
    "retrying will not help. Switch to a free-tier model such as "
    "ministral-8b-latest, ministral-3b-latest, open-mistral-nemo, or codestral-latest."
)

_SHARED_RULES = (
    "Do NOT paraphrase, do NOT substitute synonyms, do NOT restructure "
    "sentences, do NOT make the tone more formal, do NOT insert any word "
    "that wasn't said (including small words like 'a'/'the'/'and' — not "
    "even to make it read more smoothly). If a word looks misheard, "
    "garbled, or like a strange transcription error, do NOT change it or "
    "guess what was meant — keep it exactly as transcribed. If a whole "
    "segment is too garbled or broken to confidently make out at all (a "
    "transcription glitch, not just casual or ungrammatical speech), do NOT "
    "guess or invent text for it — replace ONLY that segment with the "
    "literal marker [UNCLEAR] and leave the rest normal. This text will be "
    "pasted as PLAIN TEXT into arbitrary apps — literally zero Markdown "
    "characters anywhere in the output: no '#', no '*' or '**', no "
    "backticks."
)

TRANSCRIBE_PROMPT = (
    "You lightly clean up a dictated speech transcript. Make ONLY these "
    "edits, nothing else: (1) remove filler words and false starts (um, uh, "
    "like, so, I mean, stutters, abandoned/restarted sentences), (2) remove "
    "exact word/phrase repetition caused by stumbling, (3) add correct "
    "punctuation and capitalization. Do NOT fix grammar — leave a "
    "grammatically imperfect sentence exactly as spoken if that's how it "
    "was said, even if it's missing a word like 'a' or 'the' that would "
    "normally be there. Example: input 'email him about Xylophone deployment' "
    "must stay 'email him about Xylophone deployment' — do NOT insert 'the' "
    "before 'Xylophone' even though 'about the Xylophone deployment' reads "
    "more naturally. Do NOT reorder words. Keep the user's exact word "
    "choices, word order, and phrasing. Preserve every hedge word ('maybe', "
    "'probably', 'I think') exactly as said. Do not add information, "
    "answer questions, or add commentary. Return only the cleaned text, "
    "nothing else.\n\n" + _SHARED_RULES
)

NOTES_PROMPT = (
    "You turn a rambling, dictated stream of thoughts into well-structured "
    "notes. Your job is REORGANIZATION ONLY: group related sentences under "
    "the same topic as clear paragraphs and/or bullet points, in an order "
    "that makes sense by topic instead of the order it was said — even if "
    "the same topic was mentioned at multiple separate points in the "
    "recording, merge all of it under one topic group. Within each point, "
    "make ONLY these edits: (1) remove filler words and false starts (um, "
    "uh, like, so, I mean, stutters), (2) remove exact word/phrase "
    "repetition caused by stumbling, (3) add correct punctuation and "
    "capitalization. Do NOT fix grammar beyond that. Do NOT blend, merge "
    "wording, or smooth phrasing between points even when they're grouped "
    "together. Do NOT drop a sentence's opening words (its subject, 'I "
    "need to', etc.) to make it read more like a terse note — e.g. 'I need "
    "to buy milk' must stay 'I need to buy milk', NOT become 'Buy milk'. "
    "Do NOT summarize or condense. Do NOT remove or collapse "
    "framing phrases like 'the thing about X is' or 'what I mean is' even "
    "though they may feel removable — those are intentional phrasing, not "
    "disfluencies, and only true disfluencies (um, uh, false starts, "
    "stutters) may be removed. Each point must keep the speaker's exact "
    "word choices, word order, and phrasing — ONLY its position (which "
    "topic group it's filed under) and disfluency-removal may change, "
    "never its wording. Preserve every piece of information and detail "
    "from the original — this is a restructuring task, not a rewriting or "
    "summarization task. A topic header is just plain text followed by a "
    "colon, e.g. 'Marketing Team Meeting:' on its own line, never "
    "'**Marketing Team Meeting:**'. For bullets, start a line with a plain "
    "'- ' and nothing else before it. Return only the structured notes, "
    "nothing else.\n\n" + _SHARED_RULES + "\n\n"
    "Example — notice each bullet keeps the speaker's exact wording, only "
    "grouped and stripped of filler:\n"
    "INPUT: so first I need to call John about the invoice by Friday um also "
    "I think we should redesign the homepage banner and uh one more thing "
    "don't forget to call John back about the invoice deadline actually\n"
    "OUTPUT:\n"
    "Calling John:\n"
    "- I need to call John about the invoice by Friday.\n"
    "- Don't forget to call John back about the invoice deadline actually.\n\n"
    "Website:\n"
    "- I think we should redesign the homepage banner."
)

PROMPTS = {
    MODE_TRANSCRIBE: TRANSCRIBE_PROMPT,
    MODE_NOTES: NOTES_PROMPT,
}


def make_client(api_key: str, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> Mistral:
    return Mistral(api_key=api_key, timeout_ms=timeout_ms)


def _get_retry_after(exc):
    try:
        return float(exc.headers.get("retry-after"))
    except (AttributeError, TypeError, ValueError):
        return None


def _is_zero_allowance(exc) -> bool:
    try:
        return exc.headers.get("x-ratelimit-limit-req-minute") == "0"
    except AttributeError:
        return False


MAX_VERIFY_RETRIES = 2


def clean(
    client: Mistral,
    mode: str,
    transcript: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    on_retry=None,
    max_verify_retries: int = MAX_VERIFY_RETRIES,
) -> str:
    """Rewrite `transcript` per `mode` (MODE_TRANSCRIBE or MODE_NOTES).

    Time/number/currency formatting is applied deterministically via
    normalize() BEFORE the LLM ever sees the text, so it never has the
    opportunity to "fix" an unrelated word while doing so.

    After the LLM responds, verify.missing_words() checks the output still
    contains every non-filler word from the input. If something was dropped
    or silently substituted, retry with a corrective follow-up instead of
    just trusting the prompt worked — this is a real verification loop, not
    another layer of prompt wording.
    """
    transcript = normalize(transcript)
    system_prompt = PROMPTS.get(mode, TRANSCRIBE_PROMPT)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": transcript},
    ]

    def call():
        try:
            response = client.chat.complete(
                model=model, messages=messages, max_tokens=max_tokens, temperature=0
            )
        except MistralError as exc:
            if exc.status_code == 429 and _is_zero_allowance(exc):
                raise RuntimeError(MODEL_NOT_ON_TIER_HINT.format(model=model)) from exc
            raise
        return response.choices[0].message.content

    output = with_retries(call, get_status=get_status, get_retry_after=_get_retry_after, on_retry=on_retry)

    dropped: set[str] = set()
    for _ in range(max_verify_retries):
        dropped = missing_words(transcript, output)
        if not dropped:
            return output
        correction = (
            "Your previous answer dropped or changed these exact words from "
            "the original, which must be preserved verbatim somewhere in the "
            "output: " + ", ".join(sorted(dropped)) + ". Revise your answer "
            "to include them in their correct place, changing nothing else."
        )
        messages.append({"role": "assistant", "content": output})
        messages.append({"role": "user", "content": correction})
        output = with_retries(call, get_status=get_status, get_retry_after=_get_retry_after, on_retry=on_retry)

    dropped = missing_words(transcript, output)
    if dropped:
        print(
            "mistral_cleanup: could not fully verify word preservation after "
            f"{max_verify_retries} retries — possibly missing: {', '.join(sorted(dropped))}"
        )
    return output
