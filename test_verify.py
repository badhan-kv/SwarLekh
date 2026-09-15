import verify


def test_missing_words_empty_when_content_preserved():
    source = "I need to buy milk and eggs."
    output = "Buy milk and eggs, I need to."
    assert verify.missing_words(source, output) == set()


def test_missing_words_detects_dropped_word():
    source = "Honestly, I think we should rewrite that module."
    output = "I think we should rewrite that module."
    assert verify.missing_words(source, output) == {"honestly"}


def test_missing_words_detects_substitution():
    source = "Sarah's out sick this week. Redirect her emails to me."
    output = "Sarah's out sick this week. Redirect Sarah's emails to me."
    assert verify.missing_words(source, output) == {"her"}


def test_missing_words_ignores_filler_removal():
    source = "Um, so I think, uh, this is like, fine."
    output = "I think this is fine."
    assert verify.missing_words(source, output) == set()


def test_missing_words_ignores_i_mean_phrase():
    source = "I mean, this is the plan."
    output = "This is the plan."
    assert verify.missing_words(source, output) == set()


def test_missing_words_ignores_case_and_punctuation():
    source = "It's Thursday, right?"
    output = "IT IS THURSDAY RIGHT"
    # "it's" vs "it is" differ at the word level (apostrophe-s contraction is
    # a different token from "is") — only checking case/punctuation-insensitivity here.
    assert "thursday" not in verify.missing_words(source, output)
    assert "right" not in verify.missing_words(source, output)


def test_missing_words_normalizes_curly_apostrophes():
    source = "don't forget"
    output = "don’t forget"  # curly apostrophe, as Mistral often outputs
    assert verify.missing_words(source, output) == set()


def test_missing_words_allows_exact_repetition_removal():
    source = "the meeting is at three the meeting is at three"
    output = "the meeting is at three"
    assert verify.missing_words(source, output) == set()


def test_missing_words_ignores_extra_words_in_output():
    # Topic headers in notes mode introduce new vocabulary — that's fine,
    # missing_words only checks the source->output direction.
    source = "buy milk"
    output = "Groceries:\n- buy milk"
    assert verify.missing_words(source, output) == set()
