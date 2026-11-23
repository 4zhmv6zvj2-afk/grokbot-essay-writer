"""Which gathered works stage 4a downloads.

The gather may stay long. After that list exists, works that are not
relevant to the confirmed question are dropped. From what remains, the
works that support the stage 3 plan are the download set. That set stays
within the essay cite cap, and it stays at least at the essay floor when
enough supporting works were gathered.

A missing confirmed question or a missing stage 3 plan does not turn the
full gather into the download set. The student goes back to the earlier
missing step, and the download set is empty. The gather itself may stay.
Nothing here fetches a file or invents a work, a question, or a plan.
"""

from __future__ import annotations

from typing import Any

from essay_writer.source_ids import stable_source_id

# The earlier step the student completes before any download is chosen.
QUESTION_STEP = "question-confirm"
PLAN_STEP = "plan"


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
    url_value = work.get("url")
    url = url_value if isinstance(url_value, str) else ""
    doi_value = work.get("doi")
    doi = doi_value if isinstance(doi_value, str) else ""
    return "row:" + title + "|" + doi.casefold().strip() + "|" + url.strip()


def _question_text(essay_id: str) -> str:
    from essay_writer.source_floor import confirmed_question

    return confirmed_question(essay_id)


def _plan_text(essay_id: str) -> str:
    """The saved stage 3 plan. A draft note is not a saved plan."""
    from essay_writer.stage_state import _note_path

    try:
        path = _note_path(essay_id, "3")
    except KeyError:
        return ""
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8")
    marker = "## Final look\n\n"
    if "Status: final" not in text or marker not in text:
        return ""
    return text.rsplit(marker, 1)[1].removesuffix("\n").strip()


def _argument_overlap(work: dict[str, Any], question: str, plan: str) -> int:
    title = _title(work)
    if not title or not plan.strip():
        return 0
    argument = _stems(plan) - _stems(question)
    if not argument:
        argument = _stems(plan)
    return len(_stems(title) & argument)


def _cap(
    rows: list[dict[str, Any]],
    maximum: int | None,
    question: str,
    plan: str,
) -> list[dict[str, Any]]:
    """Keep the works that fit the plan best, up to the cap.

    A tie keeps the earlier gathered work. The work id is not the order.
    """
    if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < 1:
        return list(rows)
    ranked = sorted(
        range(len(rows)),
        key=lambda index: (-_argument_overlap(rows[index], question, plan), index),
    )
    chosen = set(ranked[:maximum])
    return [row for index, row in enumerate(rows) if index in chosen]


def missing_step(question: str, plan: str) -> str | None:
    """The earlier missing step. The essay question comes before the plan."""
    if question.strip() and plan.strip():
        return None
    if not question.strip():
        return QUESTION_STEP
    return PLAN_STEP


def return_sentence(essay_id: str, step: str) -> str:
    """Plain sentence that sends the student back to the missing step.

    The plan sentence is the same stage-opening line used after a save.
    The question sentence uses the same gap line the opening already speaks.
    """
    if step == PLAN_STEP:
        from essay_writer.specialists.grok_bot import saved_next
        from essay_writer.stage_llm import brief_genre, stage_title

        opening = saved_next("3", stage_title("3", brief_genre(essay_id)))
        return f"{opening} No papers are downloaded until that plan is saved."
    from essay_writer.assignment_gate import question_gap_line, read_assignment

    record = read_assignment(essay_id)
    gap = question_gap_line(essay_id, record.get("question"))
    return f"{gap} Go back and confirm the essay question before any papers are downloaded."


def choose_downloads(essay_id: str, works: list[dict[str, Any]]) -> dict[str, Any]:
    """Full list, question filter, then the plan shortlist used for downloads.

    A missing question or a missing plan does not use the full gather as
    the download set. The student goes back to the earlier missing step,
    and the shortlist is empty. The full list stays on ``full``. The works
    are not trimmed to fill a floor, and a work is not invented to fill one.
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
    step = missing_step(question, plan)
    if step is not None:
        return {
            "ready": False,
            "full": rows,
            "question_kept": [],
            "question_dropped": [],
            "plan_kept": [],
            "shortlist": [],
            "minimum": minimum,
            "maximum": maximum,
            "return_to": step,
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
        "shortlist": _cap(plan_kept, maximum, question, plan),
        "minimum": minimum,
        "maximum": maximum,
        "return_to": None,
    }


def download_hold(essay_id: str, works: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Student return when the download set cannot be chosen yet.

    None when the confirmed question and the stage 3 plan are both present.
    The caller then keeps the existing shortlist. This does not invent a
    question or a plan, and it does not fetch a file.
    """
    from essay_writer.student_voice import say

    choice = choose_downloads(essay_id, works)
    step = choice.get("return_to")
    if choice.get("ready") is True or not isinstance(step, str):
        return None
    return {
        "ready": False,
        "return_to": step,
        "download_set": [],
        "full": choice["full"],
        "next": say(return_sentence(essay_id, step)),
    }


def _same(row: dict[str, Any], other: dict[str, Any]) -> bool:
    from essay_writer.source_match import same_source

    ident = stable_source_id(row)
    if ident and ident == stable_source_id(other):
        return True
    return same_source(row, other)


def rows_for_download(
    essay_id: str,
    rows: list[dict[str, Any]],
    works: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Rows from ``rows`` that belong to the download shortlist of ``works``.

    A missing question or a missing plan yields no rows. The full gather is
    not returned as the download set.
    """
    choice = choose_downloads(essay_id, works)
    picked = [item for item in rows if isinstance(item, dict)]
    if not choice["ready"]:
        return []
    shortlist = choice["shortlist"]
    return [row for row in picked if any(_same(row, item) for item in shortlist)]
