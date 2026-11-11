"""Typed values for the stage runner.

``essay_stage`` keeps the public tool signature as the MCP schema and turns
its arguments into :class:`StageArgs`. The pipeline resolves those arguments
against the saved pointer and the waiting card, hands the resolved fields on
as a :class:`ConfirmState`, builds the reply body, then gives a
:class:`StageContext` to the draft and save writers. The old sentinel dict
that used to carry the resolved state between those steps is gone.

This module depends only on the standard library so the state side
(``essay_writer.stage_state``, ``essay_writer.stage_note``, and
``essay_writer.stage_hold``) never imports it and no cycle opens.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class StageArgs:
    """The public ``essay.stage`` arguments. This is the tool schema."""

    essay_id: str
    stage: str
    confirmPhase: str | None = None
    look: str | None = None
    master: str | None = None
    namedFolder: str | None = None
    answers: str | None = None
    edited: str | None = None
    webCheck: dict[str, Any] | None = None
    heldFile: str | None = None
    cardAction: str | None = None
    cardDigest: str | None = None
    card_only: bool = False
    encourageChoice: str | None = None
    paperChoice: dict[str, Any] | None = None
    lockChoice: str | None = None


@dataclass(slots=True)
class ConfirmState:
    """The fields the confirm path resolved, before the reply body is built.

    This is the handoff between ``_confirm_path`` and ``_build_stage_body``.
    The body builder turns it back into a call and the reply writers receive a
    full :class:`StageContext`. A refusal never becomes one of these.
    """

    confirmPhase: str | None
    text: str
    pointer: dict[str, Any]
    master: str | None
    namedFolder: str | None
    answers: str | None
    edited: str | None
    webCheck: dict[str, Any] | None
    heldFile: str | None


@dataclass(slots=True)
class StageContext:
    """One resolved stage call, ready to become a draft or save reply.

    ``args`` is the tool call that produced it (after the runner resolved the
    look and the inherited-lock choice). Every other field is what the body
    builder and the reply writers need; none of them is looked up by string
    key.
    """

    args: StageArgs
    essay_id: str
    stage: str
    genre: str | None
    pointer: dict[str, Any]
    confirmPhase: str | None
    text: str
    look: str | None
    master: str | None
    namedFolder: str | None
    answers: str | None
    edited: str | None
    webCheck: dict[str, Any] | None
    heldFile: str | None
    card_only: bool
    minting: bool
    auto_next: str | None
    revisit: bool
    real_bib: bool
    payload: dict[str, object]
    fingerprint: dict[str, object]
    body: dict[str, Any]
    note: Path
