"""Detect the language a job posting is written in, as a lowercase ISO 639-1 code ("en", "de").

Feeds the Jobs feed's Language filter. Detection never drops a job: a posting whose
language cannot be told (no description, or too little text) gets None, which the feed
shows as "Not detected" rather than guessing wrong.
"""
import re

from langdetect import DetectorFactory, LangDetectException, detect_langs

# langdetect is randomised by default: the same mixed-language text can come back "de" on
# one run and "en" on the next. A fixed seed makes a job's language stable across re-scrapes.
DetectorFactory.seed = 0

# Below this many letters the detector guesses (a bare "Data Engineer (m/w/d)" comes back as
# Afrikaans), so the language is left unknown instead.
MIN_LETTERS = 60
# The top guess must carry at least this much probability. German text full of English job
# jargon lands around 0.75; a coin-flip between two languages is not worth reporting.
MIN_CONFIDENCE = 0.7
# Language is evident well before the end of a long description; capping keeps detection ~ms.
MAX_CHARS = 4000

_TAGS = re.compile(r"<[^>]+>")
_URLS = re.compile(r"https?://\S+|www\.\S+|\S+@\S+")
_NON_LETTERS = re.compile(r"[\W\d_]+", re.UNICODE)


def detect_job_language(title: str | None, description: str | None) -> str | None:
    """
    Detect the language of a posting.

    The description carries the language. The title is added only to pad a short
    description; it is never used alone.

    Args:
        title: Job title, as scraped
        description: Job description, plain text or HTML

    Returns:
        Lowercase ISO 639-1 code, or None when the text is too short or too ambiguous
    """
    text = _URLS.sub(" ", _TAGS.sub(" ", description or ""))
    if len(_NON_LETTERS.sub("", text)) < MIN_LETTERS:
        if not text.strip():
            return None
        text = f"{title or ''} {text}"
    if len(_NON_LETTERS.sub("", text)) < MIN_LETTERS:
        return None

    try:
        best = detect_langs(text[:MAX_CHARS])[0]
    except LangDetectException:  # pragma: no cover - guarded by the letter count above
        return None
    if best.prob < MIN_CONFIDENCE:
        return None
    # langdetect separates Chinese: "zh-cn" / "zh-tw" -> "zh"
    return best.lang.split("-")[0]
