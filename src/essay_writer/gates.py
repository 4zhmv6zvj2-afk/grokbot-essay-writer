"""Mechanical gates 1–11 and the unquoted-exact plagiarism blocker.

These checks are code. They are not a review, and they do not record EQR.
The writer seat does not pass itself.
"""

from __future__ import annotations

import re
from typing import Any, cast

from essay_writer.diary import blocked_identity_keys
from essay_writer.known_paths import research_file
from essay_writer.paths import (
    BRIEF_NAMES,
    essay_dir,
    locator_target,
    module_code,
    sequence_write_error,
    target_error,
)

_CITE = re.compile(r"\(([A-Za-z][^,()]{0,40}),\s*((?:19|20)\d{2})\)")


def _gate(number: int, name: str, passed: bool, reason: str) -> dict[str, Any]:
    return {"gate": number, "name": name, "passed": passed, "reason": reason}


def _brief_path(module: str):
    folder = essay_dir(module)
    for name in ("brief.md", "brief.txt", "brief.docx"):
        path = folder / name
        if path.is_file() and path.stat().st_size > 0:
            return path
    return None


def _genre(pack: dict[str, Any]) -> str | None:
    raw = pack.get("genre")
    if isinstance(raw, str) and raw.strip().casefold() in {"essay", "report"}:
        return raw.strip().casefold()
    assessment = pack.get("assessment")
    if isinstance(assessment, str):
        folded = assessment.casefold()
        if "report" in folded:
            return "report"
        if "essay" in folded:
            return "essay"
    return None


def _sections_text(pack: dict[str, Any]) -> str:
    sections = pack.get("sections")
    if not isinstance(sections, list):
        return ""
    parts: list[str] = []
    for section in sections:
        if isinstance(section, dict):
            body = section.get("body")
            if isinstance(body, str):
                parts.append(body)
    return "\n".join(parts)


def _surname(author: str) -> str:
    return author.split(",")[0].strip().casefold()


def _gathered_texts(essay_id: str, pack: dict[str, Any] | None) -> list[str]:

    texts: list[str] = []
    module = module_code(essay_id)
    brief = _brief_path(module)
    if (
        brief is not None
        and brief.suffix.lower() in {".md", ".txt"}
        and research_file(essay_id, str(brief)) is not None
    ):
        texts.append(brief.read_text(encoding="utf-8", errors="replace"))
    if not isinstance(pack, dict):
        return texts
    for source in pack.get("sources") or []:
        if not isinstance(source, dict):
            continue
        locator = source.get("locator")
        if not isinstance(locator, str):
            continue
        try:
            _kind, path = locator_target(essay_id, locator)
        except ValueError:
            continue
        if path is None or not path.is_file():
            continue
        if research_file(essay_id, str(path)) is None:
            continue
        suffix = path.suffix.lower()
        if suffix in {".md", ".txt", ".csv", ".html", ".htm"}:
            texts.append(path.read_text(encoding="utf-8", errors="replace"))
        elif suffix in {".docx", ".pdf"}:
            try:
                from essay_writer.invent import read_gathered_text

                texts.append(read_gathered_text(path, essay_id))
            except (OSError, ValueError):
                continue
    return texts


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    found: list[str] = []
    for part in parts:
        sentence = part.strip()
        if len(sentence.split()) >= 8:
            found.append(sentence)
    return found


def _quote_spans(body: str) -> list[tuple[int, int]]:
    return [
        (match.start(1), match.end(1))
        for match in re.finditer(r"[\"“](.+?)[\"”]", body, flags=re.DOTALL)
    ]


def _inside_quote(spans: list[tuple[int, int]], start: int, end: int) -> bool:
    return any(left <= start and end <= right for left, right in spans)


def _wrapped_in_quotes(body: str, start: int, end: int) -> bool:
    if start < 1 or end >= len(body):
        return False
    return body[start - 1] in "\"“" and body[end] in "\"”"


def unquoted_exact(body: str, gathered: list[str]) -> list[str]:
    """Sentences of eight or more words copied from a gathered file and not quoted.

    A sentence that is also copied again outside quotation marks still counts.
    A sentence that is itself the quotation, even when it contains a quote,
    does not.
    """
    spans = _quote_spans(body)
    hits: list[str] = []
    seen: set[str] = set()
    for text in gathered:
        for sentence in _sentences(text):
            if sentence in seen:
                continue
            cursor = 0
            while True:
                at = body.find(sentence, cursor)
                if at < 0:
                    break
                end = at + len(sentence)
                if not _inside_quote(spans, at, end) and not _wrapped_in_quotes(body, at, end):
                    seen.add(sentence)
                    hits.append(sentence)
                    break
                cursor = at + 1
    return hits


def _band_edges(rules: dict[str, Any]) -> tuple[int | None, int | None]:
    from essay_writer.rewrite_baseline import band_edges

    return band_edges(rules)


def evaluate_gates(essay_id: str, pack: dict[str, Any] | None = None, body: str | None = None) -> dict[str, Any]:
    module = module_code(essay_id) if isinstance(essay_id, str) else ""
    pack_sent = isinstance(pack, dict)
    pack_data = cast(dict[str, Any], pack) if pack_sent else {}
    text = body if isinstance(body, str) and body.strip() else _sections_text(pack_data)
    gates: list[dict[str, Any]] = []

    brief = _brief_path(module) if module else None
    gates.append(
        _gate(
            1,
            "brief",
            brief is not None,
            "A non-empty brief is on the module." if brief else "The module has no brief file.",
        )
    )

    pack_module = ""
    if isinstance(pack_data.get("essay_id"), str) and pack_data["essay_id"].strip():
        pack_module = module_code(pack_data["essay_id"])
    if not pack_sent or not pack_module:
        module_ok = False
        module_reason = "The pack is missing."
    elif bool(module) and pack_module == module:
        module_ok = True
        module_reason = "The pack module matches this sequence."
    else:
        module_ok = False
        module_reason = "The pack module does not match this sequence."
    gates.append(_gate(2, "module", module_ok, module_reason))

    title = pack_data.get("title")
    question_ok = (brief is not None) or (isinstance(title, str) and bool(title.strip()))
    gates.append(
        _gate(
            3,
            "question",
            question_ok,
            "A brief or a pack title names the question." if question_ok else "Name the question in the brief or the pack title.",
        )
    )

    genre = _genre(pack_data)
    if genre is None and module:
        from essay_writer.stage_llm import brief_genre

        genre = brief_genre(essay_id)
    if module == "MOD1004AA":
        genre_ok = genre == "report"
        genre_reason = "MOD1004AA is a report." if genre_ok else "MOD1004AA must be a report, not an essay."
    else:
        genre_ok = genre in {"essay", "report", "diary"}
        if genre == "diary":
            genre_reason = "Genre is a reflective diary."
        elif genre_ok:
            genre_reason = "Genre is essay or report."
        else:
            genre_reason = "Name the genre as essay or report. The brief decides."
    gates.append(_gate(4, "genre", genre_ok, genre_reason))

    sources = [item for item in (pack_data.get("sources") or []) if isinstance(item, dict)]

    located = 0
    for source in sources:
        locator = source.get("locator")
        if not isinstance(locator, str):
            continue
        try:
            _kind, path = locator_target(essay_id, locator)
        except ValueError:
            continue
        if path is not None and path.is_file() and research_file(essay_id, str(path)) is not None:
            located += 1
    gathered_ok = located >= 1 and located == len(sources) and len(sources) >= 1
    gates.append(
        _gate(
            5,
            "gathered-sources",
            gathered_ok,
            "Every source locator is a file on this module."
            if gathered_ok
            else "Each source needs a locator that is a real file on this module.",
        )
    )

    body_ok = len(text.split()) >= 1
    gates.append(
        _gate(6, "body", body_ok, "The body has words." if body_ok else "The body is empty.")
    )

    from essay_writer.brief_checks import before_word, decorative_citations

    citations = _CITE.findall(text)
    parked = decorative_citations(text)
    missing: list[str] = []
    for surname, year in citations:
        matched = False
        for source in sources:
            authors = source.get("authors") or source.get("author")
            names = authors if isinstance(authors, list) else [authors]
            years = str(source.get("year") or "")
            if years != year:
                continue
            for name in names:
                if isinstance(name, str) and _surname(name) == surname.casefold():
                    matched = True
        if not matched:
            missing.append(f"({surname}, {year})")
    cite_ok = not missing and not parked
    if missing:
        cite_reason = "These citations are not in the gathered sources: " + ", ".join(missing)
    elif parked:
        cite_reason = (
            "A citation is parked on a general sentence. "
            "Tie it to a specific result from a gathered source, or remove it. "
            + parked[0]
        )
    else:
        cite_reason = "In-text citations match a gathered author and year."
    gates.append(_gate(7, "citations", cite_ok, cite_reason))

    rules = pack_data.get("word_rules") if isinstance(pack_data.get("word_rules"), dict) else {}
    if not rules and module:
        from essay_writer.textutil import brief_file_word_rules

        rules = brief_file_word_rules(essay_id)
    low, high = _band_edges(rules) if rules else (None, None)
    count = len(text.split())
    if pack_data.get("word_count_acknowledged") is True and rules:
        band_ok, band_reason = True, "A person acknowledged the word count."
    elif low is None or high is None:
        band_ok, band_reason = True, "No word band is set on this pack."
    else:
        band_ok = low <= count <= high
        span = f"{low}–{high}"
        band_reason = (
            f"The body is inside the word band ({span})."
            if band_ok
            else f"The body is outside the word band ({count} counted, {span})."
        )
    section_rows: list[dict[str, Any]] = []
    clashes: list[str] = []
    simulation: dict[str, Any] = {"noticed": False}
    safe_default = None
    extra_blockers: list[dict[str, str]] = []
    if pack_sent:
        from essay_writer.textutil import word_rules_for

        rules_for_sections = word_rules_for(essay_id, pack_data)
        checked = before_word(
            essay_id,
            [
                {"heading": str(section.get("heading") or ""), "body": str(section.get("body") or "")}
                for section in (pack_data.get("sections") or [])
                if isinstance(section, dict)
            ],
            acknowledged_sections=pack_data.get("section_words_acknowledged") is True,
            acknowledged_contradiction=pack_data.get("contradiction_acknowledged") is True,
            acknowledged_simulation=pack_data.get("simulation_acknowledged") is True,
            exclude_citations=bool(rules_for_sections.get("exclude_in_text_citations")),
            gathered=_gathered_texts(essay_id, pack_data),
        )
        section_rows = checked["section_budgets"]
        clashes = checked["brief_contradictions"]
        simulation = checked["simulation_events"]
        safe_default = checked["safe_default"]
        extra_blockers = list(checked["blockers"])
        budget_block = [item for item in checked["blockers"] if item["code"] == "section-budget"]
        if budget_block:
            band_ok = False
            band_reason = budget_block[0]["reason"]
    else:
        budget_block = []
    if not band_ok and high is not None and count > high and not budget_block:
        from essay_writer.rewrite_baseline import rewrite_vs_opened_word, stricter_invented_max

        if stricter_invented_max(essay_id, rules, high=high) is not None:
            draft_sections = [
                {"heading": str(section.get("heading") or ""), "body": str(section.get("body") or "")}
                for section in (pack_data.get("sections") or [])
                if isinstance(section, dict)
            ]
            decision = rewrite_vs_opened_word(
                essay_id,
                text,
                rules,
                sections=draft_sections,
                high=high,
                counter="split",
            )
            if decision["waive_word"] and not decision["document_still_fails"]:
                band_ok = True
                band_reason = decision["reason"]
            elif decision["waive_word"] and decision["document_still_fails"]:
                band_ok = False
                band_reason = decision["document_reason"]
    gates.append(_gate(8, "word-band", band_ok, band_reason))

    if citations:
        refs_ok = all(isinstance(source.get("author") or source.get("authors"), (str, list)) and source.get("year") for source in sources)
        refs_reason = "Cited sources have an author and a year." if refs_ok else "A cited source is missing an author or a year."
    else:
        refs_ok, refs_reason = True, "No in-text citations, so the reference list is not required yet."
    gates.append(_gate(9, "references", refs_ok, refs_reason))


    identity_blocked = bool(blocked_identity_keys(essay_id, pack_data))
    gates.append(
        _gate(
            10,
            "identity",
            not identity_blocked,
            "No student identity." if not identity_blocked else "Remove the student identity.",
        )
    )

    conclusion = pack_data.get("conclusion")
    conclusion_ok = conclusion in {"noted", "open"}
    gates.append(
        _gate(
            11,
            "conclusion",
            conclusion_ok,
            "The conclusion is noted or open." if conclusion_ok else "The conclusion must be noted or open.",
        )
    )

    matches = unquoted_exact(text, _gathered_texts(essay_id, pack_data))
    plagiarism = {
        "code": "unquoted-exact",
        "passed": not matches,
        "matches": matches,
        "reason": "No unquoted exact sentence from a gathered file."
        if not matches
        else "A gathered sentence appears in the body without quotation marks.",
    }
    passed = all(item["passed"] for item in gates) and plagiarism["passed"] and not extra_blockers
    return {
        "ok": passed,
        "passed": passed,
        "gates": gates,
        "plagiarism": plagiarism,
        "invent_forbid": True,
        "decorative": parked,
        "section_budgets": section_rows,
        "brief_contradictions": clashes,
        "safe_default": safe_default,
        "simulation_events": simulation,
        "before_word": extra_blockers,
    }


def essay_gates(essay_id: str, pack: dict[str, Any] | None = None, body: str | None = None) -> dict[str, Any]:
    """Read-only mechanical gates. This is not the reviewer seat."""
    if not isinstance(essay_id, str):
        return {"ok": False, "refused": "essay-id", "reason": "Name the sequence.", "wrote": False, "stored": False}
    error = target_error(essay_id)
    if error:
        write_error = sequence_write_error(essay_id)
        return {
            "ok": False,
            "refused": "essay-id",
            "reason": write_error or error,
            "wrote": False,
            "stored": False,
        }
    if essay_id in BRIEF_NAMES:
        return {"ok": False, "refused": "essay-id", "reason": "Name the module.", "wrote": False, "stored": False}
    report = evaluate_gates(essay_id, pack, body)
    report["essay_id"] = essay_id
    report["read_only"] = True
    report["wrote"] = False
    report["stored"] = False
    report["seat"] = "mechanical"
    return report
