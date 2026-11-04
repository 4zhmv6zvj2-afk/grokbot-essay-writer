"""Words a student may hear or read in Word.

Chat may keep a tool id. Word drops house labels, including the word dig
inside a tool id. Invent guidance may stay in chat. Word drops it.
"""

from __future__ import annotations

import re

from essay_writer.paths import student_chat_path

# Tool names and dig-card paths stay. confirmPhase is an argument name.
_KEEP = re.compile(
    r"essay\.[A-Za-z0-9_.]+|confirmPhase|[\w./\\-]*dig-card\.(?:json|md)",
    re.IGNORECASE,
)

_SWAPS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bdig card\b", re.IGNORECASE), "source card"),
    (re.compile(r"SuperGrok", re.IGNORECASE), ""),
    (re.compile(r"Grok Build", re.IGNORECASE), ""),
    (re.compile(r"Grok Bot", re.IGNORECASE), ""),
    (re.compile(r"\bfront office\b", re.IGNORECASE), ""),
    (re.compile(r"\bmid office\b", re.IGNORECASE), ""),
    (re.compile(r"\bfront-office\b", re.IGNORECASE), ""),
    (re.compile(r"\bmid-office\b", re.IGNORECASE), ""),
    (re.compile(r"\bEQR\b"), ""),
    (re.compile(r"\bdig\b", re.IGNORECASE), "look-up"),
    (re.compile(r"\bdoors?\b", re.IGNORECASE), ""),
    (re.compile(r"\bhouse\b", re.IGNORECASE), ""),
    (re.compile(r"\bConfirm\b"), ""),
    (re.compile(r"\bconfirm\b"), ""),
    (re.compile(r"\bpacks?\b", re.IGNORECASE), "draft"),
    (re.compile(r"\bshelf\b", re.IGNORECASE), "saved copy"),
    (re.compile(r"\bseats?\b", re.IGNORECASE), ""),
    (re.compile(r"\bsmoke\b", re.IGNORECASE), ""),
    (re.compile(r"\btip\b", re.IGNORECASE), ""),
    (re.compile(r"\bGO\b"), ""),
    (re.compile(r"\bPASS\b"), ""),
    (re.compile(r"\bCursor\b", re.IGNORECASE), ""),
)

_INVENT = re.compile(
    r"[^.!?\n]*(?:invent-forbid|\bdo not invent\b|\bdon't invent\b)[^.!?\n]*[.!?]?",
    re.IGNORECASE,
)
_DIG_WORD = re.compile(r"\bdig\b", re.IGNORECASE)
_INVENT_TOKEN = re.compile(r"invent-forbid", re.IGNORECASE)
_EQR_WORD = re.compile(r"\bEQR\b")
_GROK_BUILD = re.compile(r"Grok Build", re.IGNORECASE)
_GROK_BOT = re.compile(r"Grok Bot", re.IGNORECASE)
_SUPER = re.compile(r"SuperGrok", re.IGNORECASE)
_CONFIRM_SLANG = re.compile(r"\bConfirm\b")
_OFFICE_LABEL = re.compile(r"\b(?:mid|front)[-\s]office\b", re.IGNORECASE)

# A writer that speaks as a model. Student prose and chat speak as the student.
_ASSISTANT_VOICE = re.compile(
    r"\bas an? (?:large language model|ai language model|language model|ai)\b"
    r"|\bi(?:'m| am) (?:just |only )?an? (?:large language model|ai language model|language model|ai)\b",
    re.IGNORECASE,
)
# Drop the model line itself. A sentence start, and the following word, stay intact.
_AI_LEAD = re.compile(
    r"(?:^|(?<=[.!?]\s))as an? (?:large language model|ai language model|language model|ai)\s*,\s*",
    re.IGNORECASE,
)
_AI_SELF = re.compile(
    r"(?:^|(?<=[.!?]\s))i(?:'m| am) (?:just |only )?an? "
    r"(?:large language model|ai language model|language model|ai)\b[.,]?\s*",
    re.IGNORECASE,
)


def _drop_assistant_voice(text: str) -> str:
    """Remove a model self-reference, then keep a capital at the sentence start."""
    cleaned = _AI_SELF.sub("", _AI_LEAD.sub("", text))
    if cleaned != text and cleaned[:1].islower():
        cleaned = cleaned[:1].upper() + cleaned[1:]
    return cleaned


# House labels in a stage prompt, a pasted writing note, or a Word file.
# The academic verb "confirm" is not this list. "Confirm" as a save label is.
STUDENT_SURFACE_BANS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bdig\b", re.IGNORECASE), "dig"),
    (re.compile(r"\bdoors?\b", re.IGNORECASE), "door"),
    (re.compile(r"\bhouse\b", re.IGNORECASE), "house"),
    (_CONFIRM_SLANG, "Confirm"),
    (_EQR_WORD, "EQR"),
    (_INVENT_TOKEN, "invent-forbid"),
    (re.compile(r"\bpacks?\b", re.IGNORECASE), "pack"),
    (re.compile(r"\bshel(?:f|ves)\b", re.IGNORECASE), "shelf"),
    (_OFFICE_LABEL, "office"),
    (re.compile(r"\bseats?\b", re.IGNORECASE), "seat"),
    (re.compile(r"\bsmoke\b", re.IGNORECASE), "smoke"),
    (re.compile(r"\btip\b", re.IGNORECASE), "tip"),
    (re.compile(r"\bGO\b"), "GO"),
    (re.compile(r"\bPASS\b"), "PASS"),
    (_GROK_BUILD, "Grok Build"),
    (_ASSISTANT_VOICE, "assistant voice"),
)


def student_surface_hits(text: str) -> list[str]:
    """Banned labels found in student-facing prompt or Word text."""
    if not isinstance(text, str) or not text:
        return []
    return [name for pattern, name in STUDENT_SURFACE_BANS if pattern.search(text)]


# Ordinary English in a gathered quotation. The same words stay in Word,
# the annotation, and the 4b markdown. dig, invent-forbid, EQR, Grok Build,
# Confirm as a save label, and mid or front office are still replaced.
QUOTATION_HOUSE_WORDS = ("pack", "door", "house", "seat", "tip", "smoke")
QUOTATION_HOUSE_POLICY = (
    "A gathered quotation keeps ordinary English such as pack, door, house, seat, tip, or smoke. "
    "That rule is the same in the essay Word file, the annotation, and the 4b markdown. "
    "dig, invent-forbid, EQR, Grok Build, Confirm as a save label, and mid or front office "
    "are still replaced before those files are saved."
)
_QUOTED_SPAN = re.compile(r'"[^"]*"|“[^”]*”')


def strip_word_labels(text: str) -> str:
    """Word and paper-note text. The academic verb confirm stays.

    The word dig does not, including inside a tool id. The invent-forbid
    token does not. Ordinary words such as pack in a quotation stay, so a
    gathered sentence is not rewritten.
    """
    if not isinstance(text, str) or not text:
        return text
    text = _drop_assistant_voice(text)
    text = _INVENT_TOKEN.sub("do not invent sources", text)
    text = _EQR_WORD.sub("independent review", text)
    text = _GROK_BUILD.sub("", text)
    text = _GROK_BOT.sub("", text)
    text = _SUPER.sub("", text)
    text = _CONFIRM_SLANG.sub("approve", text)
    text = _OFFICE_LABEL.sub("", text)
    text = _DIG_WORD.sub("look-up", text)
    return re.sub(r"[ \t]{2,}", " ", text)


def _tidy(text: str) -> str:
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r" +([.,;:])", r"\1", text)
    return text.strip()


_CHAT_PLACE = "Grok Bot chat delivery"
_CHAT_PLACE_TOKEN = "\x01chatplace\x01"
_CONFIRM_CARD = "Confirm card"
_CONFIRM_CARD_TOKEN = "\x01confirmcard\x01"
_PATH_KEYS = frozenset(
    {
        "app",
        "app_path",
        "kb1",
        "setup",
        "path",
        "mac_path",
        "tracking_path",
        "localPaths",
    }
)
_TILDE_PATH = re.compile(r"(?<![\w.])~(?:/[\w.-]+)+")


def _scrub_paths_in_text(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        cleaned = student_chat_path(match.group(0))
        return cleaned if cleaned else match.group(0)

    text = _TILDE_PATH.sub(replace, text)
    for match in re.finditer(
        r"(?:/Users/|/Volumes/|/private/|/workspace/)(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+",
        text,
    ):
        raw = match.group(0)
        cleaned = student_chat_path(raw)
        if cleaned != raw:
            text = text.replace(raw, cleaned, 1)
    return text


def say(text: str) -> str:
    """Student chat. Invent guidance is left in place."""
    if not isinstance(text, str) or not text:
        return text
    text = _drop_assistant_voice(text)
    text = _scrub_paths_in_text(text)
    text = text.replace(_CHAT_PLACE, _CHAT_PLACE_TOKEN)
    text = text.replace(_CONFIRM_CARD, _CONFIRM_CARD_TOKEN)
    kept: list[str] = []

    def protect(match: re.Match[str]) -> str:
        kept.append(match.group(0))
        return f"\x00{len(kept) - 1}\x00"

    masked = _KEEP.sub(protect, text)
    for pattern, replacement in _SWAPS:
        masked = pattern.sub(replacement, masked)

    def restore(match: re.Match[str]) -> str:
        return kept[int(match.group(1))]

    restored = _tidy(re.sub(r"\x00(\d+)\x00", restore, masked))
    restored = restored.replace(_CHAT_PLACE_TOKEN, _CHAT_PLACE)
    return restored.replace(_CONFIRM_CARD_TOKEN, _CONFIRM_CARD)


def annotation_prose(text: str) -> str:
    """Full annotation sentences for the Word file.

    House labels are still replaced. The claim and the brief's mark-scheme
    words stay. This does not score simple words and does not shorten the
    paragraph to a citation line.
    """
    return prose_for_surface(text, "annotation")


def prose_for_surface(text: str, surface: str) -> str:
    """Student prose for word, annotation, or review.

    Quoted spans keep QUOTATION_HOUSE_WORDS on every surface. Outside a
    quotation, Word still drops the wider house list. Annotation and 4b
    markdown use the narrower replacement, so ordinary English stays.
    """
    if not isinstance(text, str) or not text:
        return text

    def outside(part: str) -> str:
        if not part:
            return part
        if surface == "word":
            return for_word(part)
        return strip_word_labels(part)

    pieces: list[str] = []
    last = 0
    for match in _QUOTED_SPAN.finditer(text):
        pieces.append(outside(text[last : match.start()]))
        pieces.append(strip_word_labels(match.group(0)))
        last = match.end()
    pieces.append(outside(text[last:]))
    return "".join(pieces)


def for_word(text: str) -> str:
    """Word file text. House labels and invent guidance are omitted.

    Tool ids that contain the word dig are kept in chat and dropped here.
    """
    if not isinstance(text, str) or not text:
        return text
    spoken = say(text)
    cleaned = _tidy(_INVENT.sub(" ", spoken))
    return _tidy(_DIG_WORD.sub("look-up", cleaned))


def speak(body: dict) -> dict:
    """Clean the strings a person reads on a tool reply. Codes stay."""
    reason = body.get("reason")
    if isinstance(reason, str):
        body["reason"] = say(reason)
    nxt = body.get("next")
    if isinstance(nxt, str):
        body["next"] = say(nxt)
    for key, value in list(body.items()):
        if key in _PATH_KEYS:
            if isinstance(value, str):
                body[key] = student_chat_path(value)
            elif isinstance(value, list) and key == "localPaths":
                body[key] = [
                    student_chat_path(item) if isinstance(item, str) else item for item in value
                ]
    for key in ("issues", "blockers", "notes"):
        items = body.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and isinstance(item.get("reason"), str):
                item["reason"] = say(item["reason"])
    return body
