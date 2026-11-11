"""Tracking-note text for one stage.

stage_note renders the stage markdown. It does not write the pointer or the
commit journal. It never imports the orchestrator.
"""

from __future__ import annotations

from essay_writer.stage_llm import stage_settings, stage_title


def render_tracking(
    stage: str,
    *,
    status: str,
    look: str,
    genre: str | None = None,
    essay_id: str | None = None,
) -> str:
    """Markdown from that stage's guidance, plus the working or final look."""
    item = stage_settings(stage, genre)
    title = stage_title(stage, genre)
    body = look if look else item["prompt_overlay"]
    heading = "Final look" if status == "final" else "Working look"
    sequence_line = f"Sequence id: {essay_id}\n\n" if essay_id else ""
    return (
        f"# Stage {stage} — {title}\n\n"
        f"{sequence_line}"
        f"Status: {status}\n\n"
        f"{item['rules']}\n\n"
        f"## {heading}\n\n"
        f"{body}\n"
    )
