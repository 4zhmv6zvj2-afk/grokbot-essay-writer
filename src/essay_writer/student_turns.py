"""Exact student lines for the opening, four redirects, and stages 6 and 7.

The wording lives once in front_office/chat.md. A short ask that is one of
the four cases returns that reply and does not save. A stage note does not.
"""

from __future__ import annotations

import re

from essay_writer.prompt_loader import text

_CHAT = "front_office/chat.md"

FIRST_TURN_CARD = text(_CHAT, "first_turn_card")
REDIRECT_WHOLE = text(_CHAT, "redirect_whole")
REDIRECT_ORDER = text(_CHAT, "redirect_order")
REDIRECT_VOICE = text(_CHAT, "redirect_voice")
REDIRECT_CLOSE = text(_CHAT, "redirect_close")
STAGE6_LEAD_IN = text(_CHAT, "stage6_lead_in")
STAGE7_LINE = text(_CHAT, "stage7_line")

# Optional polite words a student may put in front of a short ask.
_POLITE = (
    r"(?:(?:"
    r"please |can you |could you |would you |i want to |i need to |i want you to |"
    r"just |can we |could we |let us |help me "
    r")*)"
)

_CASES: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            rf"^{_POLITE}(?:beat|fool|bypass|evade|trick) (?:the |an? )?(?:ai )?detector$"
            rf"|^{_POLITE}make (?:it|this) undetectable$",
        ),
        REDIRECT_CLOSE,
    ),
    (
        re.compile(
            rf"^{_POLITE}(?:make (?:it|this|the writing) )?sound less like "
            rf"(?:an? )?(?:ai|robot|machine|chatbot)$",
        ),
        REDIRECT_VOICE,
    ),
    (
        re.compile(rf"^{_POLITE}(?:skip|skipping)(?: the)? stages?(?: now)?$"),
        REDIRECT_ORDER,
    ),
    (
        re.compile(
            rf"^{_POLITE}(?:write|draft|do|finish) (?:the |my )?"
            rf"(?:whole|entire|full|complete) (?:essay|report)(?: now)?$"
            rf"|^{_POLITE}write (?:the |my )?(?:essay|report) now$",
        ),
        REDIRECT_WHOLE,
    ),
)

# A real stage note is longer than a short ask. Past this, leave the note alone.
_LIMIT = 180


def redirect_for(message: object) -> str | None:
    """The approved reply when the whole message is one of the four short asks."""
    if not isinstance(message, str):
        return None
    folded = re.sub(r"\s+", " ", message).strip().strip(" .!?").casefold()
    if not folded or len(folded) > _LIMIT:
        return None
    for pattern, reply in _CASES:
        if pattern.fullmatch(folded):
            return reply
    return None


def stage6_student_rule() -> str:
    """Stage 6 rule both shells apply. The lead-in sentence stays exact."""
    return (
        "Say this to the student once at the start of the first read, "
        f"then show the short read list: {STAGE6_LEAD_IN}"
    )


def stage7_student_rule() -> str:
    """Stage 7 rule both shells apply. The student line stays exact."""
    return f"Say this to the student before the questions: {STAGE7_LINE}"
