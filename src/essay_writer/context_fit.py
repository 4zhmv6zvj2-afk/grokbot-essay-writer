"""Stage 5 window when 4b markdowns are too long.

The stage 5 context window is a character budget (the same integer
stage_settings stores). Recovery is trim, then split, then reopen.
A markdown is never cut off in the middle. A quotation is checked
against the full markdown. The revise loop stays open while a clear
path remains. The person is told only when every path is exhausted.
"""

from __future__ import annotations

from typing import Any

from essay_writer.stage_llm import HOUSE_MODEL

MODEL_LINE = f"Critical note: {HOUSE_MODEL}"


def _text(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _papers(reviews: object) -> list[dict[str, str]] | None:
    """One markdown per paper. None when the list is not that shape."""
    if not isinstance(reviews, list):
        return None
    papers: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in reviews:
        if not isinstance(item, dict):
            return None
        paper_id = _text(item.get("paper_id"))
        markdown = item.get("markdown")
        if paper_id is None or paper_id in seen:
            return None
        if not isinstance(markdown, str) or not markdown.strip():
            return None
        seen.add(paper_id)
        papers.append({"paper_id": paper_id, "markdown": markdown})
    return papers


def trim_model_line(markdown: str) -> tuple[str, int]:
    """Drop only the repeated model line. Every other line stays."""
    kept: list[str] = []
    dropped = 0
    for line in markdown.splitlines():
        if line.strip() == MODEL_LINE:
            dropped += 1
            continue
        kept.append(line)
    text = "\n".join(kept)
    if markdown.endswith("\n") and text and not text.endswith("\n"):
        text += "\n"
    return text, dropped


def _pending() -> dict[str, object]:
    return {
        "ok": True,
        "pending": True,
        "clear": True,
        "exhausted": False,
        "silent_truncation": False,
        "action": "pending",
        "continue_revise": False,
        "batches": [],
        "held": [],
        "refused_reopen": [],
        "trimmed_lines": 0,
        "tip": None,
        "invent_forbid": "hold",
        "evidence": "full-markdown",
    }


def _base(*, budget: int) -> dict[str, object]:
    body = _pending()
    body["pending"] = False
    body["budget"] = budget
    return body


def _reopen_passage(
    paper_id: str,
    markdown: str,
    reopens: object,
    budget: int,
    refused: list[dict[str, str]],
) -> str | None:
    """An exact passage that fits. A passage that is not in the markdown is refused."""
    if reopens is None:
        return None
    if not isinstance(reopens, list):
        refused.append({"paper_id": paper_id, "reason": "reopen must list a paper and a passage."})
        return None
    chosen: str | None = None
    for item in reopens:
        if not isinstance(item, dict) or item.get("paper_id") != paper_id:
            continue
        passage = item.get("passage")
        if not isinstance(passage, str) or not passage.strip():
            refused.append({"paper_id": paper_id, "reason": "reopen needs the passage."})
            continue
        passage = passage.strip()
        if passage not in markdown:
            refused.append(
                {
                    "paper_id": paper_id,
                    "reason": "That passage is not in the critical-review markdown.",
                }
            )
            continue
        if len(passage) <= budget and chosen is None:
            chosen = passage
    return chosen


def fit_critical_reviews(
    reviews: object = None,
    *,
    reopens: object = None,
    budget: int,
) -> dict[str, object]:
    """Fit 4b markdowns into the stage 5 window without a silent cut.

    Trim drops only the repeated model line. Split keeps each paper whole.
    Reopen uses an exact passage from that markdown. A cut at the budget
    is not a result this function returns.
    """
    if reviews is None:
        return _pending()
    if not isinstance(budget, int) or budget < 1:
        body = _base(budget=0)
        body["ok"] = False
        body["clear"] = False
        body["exhausted"] = True
        body["action"] = "exhausted"
        body["tip"] = (
            "The critical-review notes do not fit this step. "
            "Nothing was cut off in silence."
        )
        return body
    papers = _papers(reviews)
    body = _base(budget=budget)
    if papers is None:
        body["ok"] = False
        body["clear"] = False
        body["exhausted"] = True
        body["action"] = "exhausted"
        body["invent_forbid"] = "hold"
        body["tip"] = (
            "The critical-review notes do not fit this step. "
            "Nothing was cut off in silence."
        )
        return body
    if not papers:
        body["action"] = "fit"
        body["clear"] = True
        return body

    trimmed_rows: list[dict[str, Any]] = []
    trimmed_lines = 0
    for paper in papers:
        trimmed, dropped = trim_model_line(paper["markdown"])
        trimmed_lines += dropped
        trimmed_rows.append(
            {
                "paper_id": paper["paper_id"],
                "markdown": paper["markdown"],
                "trimmed": trimmed,
                "dropped": dropped,
            }
        )
    body["trimmed_lines"] = trimmed_lines
    original_total = sum(len(row["markdown"]) for row in trimmed_rows)
    trimmed_total = sum(len(row["trimmed"]) for row in trimmed_rows)

    def _batch(rows: list[dict[str, Any]], *, source: str) -> dict[str, object]:
        return {
            "paper_ids": [row["paper_id"] for row in rows],
            "chars": sum(len(row["working"]) for row in rows),
            "source": source,
            "working": {row["paper_id"]: row["working"] for row in rows},
        }

    if original_total <= budget:
        fitted = [{"paper_id": row["paper_id"], "working": row["markdown"]} for row in trimmed_rows]
        body["action"] = "fit"
        body["clear"] = True
        body["continue_revise"] = False
        body["batches"] = [_batch(fitted, source="full-markdown")]
        return body

    if trimmed_total <= budget:
        fitted = [{"paper_id": row["paper_id"], "working": row["trimmed"]} for row in trimmed_rows]
        body["action"] = "trim"
        body["clear"] = True
        body["continue_revise"] = True
        body["batches"] = [_batch(fitted, source="trim")]
        return body

    fitting: list[dict[str, Any]] = []
    oversized: list[dict[str, Any]] = []
    for row in trimmed_rows:
        if len(row["trimmed"]) <= budget:
            fitting.append(row)
        else:
            oversized.append(row)

    batches: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    current_chars = 0
    for row in fitting:
        size = len(row["trimmed"])
        if current and current_chars + size > budget:
            batches.append(
                _batch(
                    [{"paper_id": item["paper_id"], "working": item["trimmed"]} for item in current],
                    source="split",
                )
            )
            current = []
            current_chars = 0
        current.append(row)
        current_chars += size
    if current:
        batches.append(
            _batch(
                [{"paper_id": item["paper_id"], "working": item["trimmed"]} for item in current],
                source="split",
            )
        )

    refused: list[dict[str, str]] = []
    held: list[dict[str, str]] = []
    reopened = False
    for row in oversized:
        passage = _reopen_passage(row["paper_id"], row["markdown"], reopens, budget, refused)
        if passage is None:
            held.append(
                {
                    "paper_id": row["paper_id"],
                    "reason": "The note does not fit, and no re-opened passage fits.",
                }
            )
            continue
        reopened = True
        batches.append(
            _batch(
                [{"paper_id": row["paper_id"], "working": passage}],
                source="reopen",
            )
        )

    body["batches"] = batches
    body["held"] = held
    body["refused_reopen"] = refused
    if refused:
        body["invent_forbid"] = "refuse"
    if held:
        body["clear"] = False
        body["exhausted"] = True
        body["continue_revise"] = False
        body["action"] = "exhausted"
        body["tip"] = (
            "The critical-review notes do not fit this step. "
            "A shorter group and a re-opened passage were not enough. "
            "Nothing was cut off in silence."
        )
        return body

    body["clear"] = True
    body["exhausted"] = False
    body["continue_revise"] = True
    if reopened:
        body["action"] = "reopen"
    elif trimmed_lines and any(item.get("source") == "split" for item in batches) or len(batches) > 1 or (batches and batches[0].get("source") == "split"):
        body["action"] = "split"
    else:
        body["action"] = "trim"
    body["tip"] = None
    return body
