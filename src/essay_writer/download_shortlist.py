"""Which gathered works stage 4a downloads.

The gather may stay long. After that list exists, works that are not
relevant to the confirmed question are dropped. From what remains, the
works that support the stage 3 plan are the download set. That set stays
within the essay cite cap, and it stays at least at the essay floor when
enough supporting works were gathered. Nothing here fetches a file or
invents a work.
"""

from __future__ import annotations

from typing import Any

from essay_writer.source_ids import stable_source_id


def _stems(text: str) -> set[str]:
    from essay_writer.essay_cites import _words

    return _words(text)


def _title(work: dict[str, Any]) -> str:
    title = work.get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    return ""


def matches_question(work: dict[str, Any], question: str) -> bool:
    """True when the title shares a word with the confirmed question."""
    title = _title(work)
    if not title or not question.strip():
        return False
    return bool(_stems(title) & _stems(question))


def supports_argument(work: dict[str, Any], question: str, plan: str) -> bool:
    """True when the title supports the plan, not only the question.

    Words the plan copies from the question are not the argument. When the
    plan adds no word of its own, the plan text is the argument.
    """
    title = _title(work)
    if not title or not plan.strip():
        return False
    title_stems = _stems(title)
    plan_stems = _stems(plan)
    argument = plan_stems - _stems(question)
    if not argument:
        argument = plan_stems
    return bool(title_stems & argument)


def _work_id(work: dict[str, Any]) -> str:
    ident = stable_source_id(work)
    if ident:
        return ident
    title = _title(work).casefold()
    url = work.get("url") if isinstance(work.get("url"), str) else ""
    doi = work.get("doi") if isinstance(work.get("doi"), str) else ""
    return "row:" + title + "|" + doi.casefold().strip() + "|" + url.strip()


def _question_text(essay_id: str) -> str:
    from essay_writer.source_floor import confirmed_question

    return confirmed_question(essay_id)


def _plan_text(essay_id: str) -> str:
    from essay_writer.stage_note import _note_look

    look = _note_look(essay_id, "3")
    return look.strip() if isinstance(look, str) else ""


def _cap(rows: list[dict[str, Any]], maximum: int | None) -> list[dict[str, Any]]:
    if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < 1:
        return list(rows)
    order = sorted({_work_id(row) for row in rows})
    keep = set(order[:maximum])
    return [row for row in rows if _work_id(row) in keep]


def choose_downloads(essay_id: str, works: list[dict[str, Any]]) -> dict[str, Any]:
    """Full list, question filter, then the plan shortlist used for downloads.

    A missing question or a missing plan leaves the works unchanged, because
    those two steps need both texts. The works are not trimmed to fill a
    floor, and a work is not invented to fill one.
    """
    from essay_writer.essay_cites import essay_cite_bounds

    rows = [item for item in works if isinstance(item, dict)]
    bounds = essay_cite_bounds(essay_id)
    minimum = int(bounds.get("minimum") or 0)
    maximum = bounds.get("maximum")
    if not isinstance(maximum, int) or isinstance(maximum, bool):
        maximum = None
    question = _question_text(essay_id)
    plan = _plan_text(essay_id)
    if not question or not plan:
        return {
            "ready": False,
            "full": rows,
            "question_kept": list(rows),
            "question_dropped": [],
            "plan_kept": list(rows),
            "shortlist": list(rows),
            "minimum": minimum,
            "maximum": maximum,
        }
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for row in rows:
        if matches_question(row, question):
            kept.append(row)
        else:
            dropped.append(row)
    plan_kept = [row for row in kept if supports_argument(row, question, plan)]
    return {
        "ready": True,
        "full": rows,
        "question_kept": kept,
        "question_dropped": dropped,
        "plan_kept": plan_kept,
        "shortlist": _cap(plan_kept, maximum),
        "minimum": minimum,
        "maximum": maximum,
    }


def _same(row: dict[str, Any], other: dict[str, Any]) -> bool:
    from essay_writer.research_packs import same_source

    ident = stable_source_id(row)
    if ident and ident == stable_source_id(other):
        return True
    return same_source(row, other)


def rows_for_download(
    essay_id: str,
    rows: list[dict[str, Any]],
    works: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Rows from ``rows`` that belong to the download shortlist of ``works``."""
    choice = choose_downloads(essay_id, works)
    picked = [item for item in rows if isinstance(item, dict)]
    if not choice["ready"]:
        return picked
    shortlist = choice["shortlist"]
    return [row for row in picked if any(_same(row, item) for item in shortlist)]
