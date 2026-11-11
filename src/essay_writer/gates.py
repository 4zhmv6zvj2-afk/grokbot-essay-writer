"""Mechanical gates 1–11 and the unquoted-exact plagiarism blocker.

These checks are code. They are not a review, and they do not record EQR.
The writer seat does not pass itself.
"""

from __future__ import annotations

import re
from pathlib import Path
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
from essay_writer.textutil import sentences


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


def _read_utf8(path: Path, blocked: list[str], unreadable: list[str]) -> str | None:
    """Read one gathered text file. A non-UTF-8 file is named and not replaced.

    UTF-8 and UTF-16 with a byte-order mark are accepted. Other encodings are
    refused so a copied sentence cannot hide behind replacement characters.
    A file that cannot be opened is named separately. That is not an encoding miss.
    """
    from essay_writer.textutil import decode_stored_text

    try:
        raw = path.read_bytes()
    except OSError:
        unreadable.append(path.name)
        return None
    try:
        return decode_stored_text(raw)
    except UnicodeDecodeError:
        blocked.append(path.name)
        return None


def _gathered_scan(
    essay_id: str, pack: dict[str, Any] | None
) -> tuple[list[str], list[str], list[str]]:
    """Gathered text, names that are not UTF-8, and names that could not be opened.

    Unreadable names are not scanned. Replacement characters would let a copied
    sentence through the plagiarism check.
    """
    texts: list[str] = []
    blocked: list[str] = []
    unreadable: list[str] = []
    module = module_code(essay_id)
    brief = _brief_path(module)
    if (
        brief is not None
        and brief.suffix.lower() in {".md", ".txt"}
        and research_file(essay_id, str(brief)) is not None
    ):
        brief_text = _read_utf8(brief, blocked, unreadable)
        if brief_text is not None:
            texts.append(brief_text)
    if not isinstance(pack, dict):
        return texts, blocked, unreadable
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
            source_text = _read_utf8(path, blocked, unreadable)
            if source_text is not None:
                texts.append(source_text)
        elif suffix in {".docx", ".pdf"}:
            try:
                from essay_writer.invent import read_gathered_text

                texts.append(read_gathered_text(path, essay_id))
            except (OSError, ValueError):
                continue
    return texts, blocked, unreadable


def _gathered_texts(essay_id: str, pack: dict[str, Any] | None) -> list[str]:
    texts, _blocked, _unreadable = _gathered_scan(essay_id, pack)
    return texts


def _exclude_in_text_citations(essay_id: str, rules: dict[str, Any]) -> bool:
    """Whether in-text citations count. A pack band keeps its own min and max.

    An explicit pack flag wins. Otherwise the mark scheme or brief flag is
    copied, and only then the studied module default in daily use.
    """
    if "exclude_in_text_citations" in rules:
        return bool(rules.get("exclude_in_text_citations"))
    from essay_writer.assignment_gate import study_defaults_allowed
    from essay_writer.specialists.writer import document_word_band
    from essay_writer.textutil import BRIEF_WORD_RULES

    stated = document_word_band(essay_id)
    if isinstance(stated, dict) and "exclude_in_text_citations" in stated:
        return bool(stated["exclude_in_text_citations"])
    if study_defaults_allowed(essay_id):
        studied = BRIEF_WORD_RULES.get(module_code(essay_id), {})
        if isinstance(studied, dict) and "exclude_in_text_citations" in studied:
            return bool(studied["exclude_in_text_citations"])
    return False


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
    return body[start - 1] in '"“' and body[end] in '"”'


def unquoted_exact(body: str, gathered: list[str]) -> list[str]:
    """Sentences copied from a gathered file and not quoted, short ones included.

    A sentence that is also copied again outside quotation marks still counts.
    A sentence that is itself the quotation, even when it contains a quote,
    does not. The old eight-word floor silently hid short copied lines; the
    shared splitter keeps them and this gate sees what the checks see.
    """
    spans = _quote_spans(body)
    hits: list[str] = []
    seen: set[str] = set()
    for text in gathered:
        for sentence in sentences(text):
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


def evaluate_gates(
    essay_id: str, pack: dict[str, Any] | None = None, body: str | None = None
) -> dict[str, Any]:
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
            "A brief or a pack title names the question."
            if question_ok
            else "Name the question in the brief or the pack title.",
        )
    )

    genre = _genre(pack_data)
    if genre is None and module:
        from essay_writer.stage_llm import brief_genre

        genre = brief_genre(essay_id)
    if module == "MOD1004AA":
        genre_ok = genre == "report"
        genre_reason = (
            "MOD1004AA is a report." if genre_ok else "MOD1004AA must be a report, not an essay."
        )
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
    from essay_writer.textutil import citation_records, count_words, in_text_forms, token_allowed

    forms: set[str] = set()
    for source in sources:
        year = source.get("year")
        if year is None or not str(year).strip():
            continue
        authors = source.get("authors") or source.get("author")
        names = authors if isinstance(authors, list) else [authors]
        for name in names:
            if isinstance(name, str) and name.strip():
                forms |= in_text_forms(name, str(year))
    records = citation_records(text)
    parked = decorative_citations(text)
    hard_missing = [
        record.token for record in records if record.hard and not token_allowed(record.token, forms)
    ]
    questionable = [
        record.token
        for record in records
        if not record.hard and not token_allowed(record.token, forms)
    ]
    cite_ok = not hard_missing and not parked
    if hard_missing:
        cite_reason = "These citations are not in the gathered sources: " + ", ".join(hard_missing)
    elif parked:
        cite_reason = (
            "A citation is parked on a general sentence. "
            "Tie it to a specific result from a gathered source, or remove it. " + parked[0]
        )
    else:
        cite_reason = "In-text citations match a gathered author and year."
        if questionable:
            label = (
                "A possible citation was" if len(questionable) == 1 else "Possible citations were"
            )
            cite_reason += f" {label} not confirmed: " + ", ".join(questionable) + "."
    cite_gate = _gate(7, "citations", cite_ok, cite_reason)
    cite_gate["questionable"] = questionable
    gates.append(cite_gate)

    rules = pack_data.get("word_rules") if isinstance(pack_data.get("word_rules"), dict) else {}
    if not rules and module:
        from essay_writer.textutil import brief_file_word_rules

        rules = brief_file_word_rules(essay_id)
    low, high = _band_edges(rules) if isinstance(rules, dict) and rules else (None, None)
    exclude_cites = (
        _exclude_in_text_citations(essay_id, rules) if isinstance(rules, dict) else False
    )
    count = count_words(text, exclude_citations=exclude_cites)
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
        checked = before_word(
            essay_id,
            [
                {
                    "heading": str(section.get("heading") or ""),
                    "body": str(section.get("body") or ""),
                }
                for section in (pack_data.get("sections") or [])
                if isinstance(section, dict)
            ],
            acknowledged_sections=pack_data.get("section_words_acknowledged") is True,
            acknowledged_contradiction=pack_data.get("contradiction_acknowledged") is True,
            acknowledged_simulation=pack_data.get("simulation_acknowledged") is True,
            exclude_citations=exclude_cites,
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
                {
                    "heading": str(section.get("heading") or ""),
                    "body": str(section.get("body") or ""),
                }
                for section in (pack_data.get("sections") or [])
                if isinstance(section, dict)
            ]
            decision = rewrite_vs_opened_word(
                essay_id,
                text,
                rules,
                sections=draft_sections,
                high=high,
                counter="words",
                exclude_citations=exclude_cites,
            )
            if decision["waive_word"] and not decision["document_still_fails"]:
                band_ok = True
                band_reason = decision["reason"]
            elif decision["waive_word"] and decision["document_still_fails"]:
                band_ok = False
                band_reason = decision["document_reason"]
    gates.append(_gate(8, "word-band", band_ok, band_reason))

    if records:
        refs_ok = all(
            isinstance(source.get("author") or source.get("authors"), (str, list))
            and source.get("year")
            for source in sources
        )
        refs_reason = (
            "Cited sources have an author and a year."
            if refs_ok
            else "A cited source is missing an author or a year."
        )
    else:
        refs_ok, refs_reason = (
            True,
            "No in-text citations, so the reference list is not required yet.",
        )
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
            "The conclusion is noted or open."
            if conclusion_ok
            else "The conclusion must be noted or open.",
        )
    )

    gathered, blocked, unreadable = _gathered_scan(essay_id, pack_data)
    matches = unquoted_exact(text, gathered)
    if blocked or unreadable:
        reason_parts: list[str] = []
        if blocked:
            reason_parts.append(
                "A gathered file is not valid UTF-8 and was not scanned: "
                + ", ".join(blocked)
                + ". Re-save it as UTF-8 and run this check again."
            )
        if unreadable:
            reason_parts.append(
                "A gathered file could not be read: "
                + ", ".join(unreadable)
                + ". Allow file access and run this check again."
            )
        reason = " ".join(reason_parts)
        if matches:
            reason += " A gathered sentence appears in the body without quotation marks."
        plagiarism_code = "gathered-encoding" if blocked else "gathered-unreadable"
        plagiarism_passed = False
    elif matches:
        reason = "A gathered sentence appears in the body without quotation marks."
        plagiarism_code = "unquoted-exact"
        plagiarism_passed = False
    else:
        reason = "No unquoted exact sentence from a gathered file."
        plagiarism_code = "unquoted-exact"
        plagiarism_passed = True
    plagiarism = {
        "code": plagiarism_code,
        "passed": plagiarism_passed,
        "matches": matches,
        "reason": reason,
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
        "questionable_citations": questionable,
    }


def essay_gates(
    essay_id: str, pack: dict[str, Any] | None = None, body: str | None = None
) -> dict[str, Any]:
    """Read-only mechanical gates. This is not the reviewer seat."""
    if not isinstance(essay_id, str):
        return {
            "ok": False,
            "refused": "essay-id",
            "reason": "Name the sequence.",
            "wrote": False,
            "stored": False,
        }
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
        return {
            "ok": False,
            "refused": "essay-id",
            "reason": "Name the module.",
            "wrote": False,
            "stored": False,
        }
    report = evaluate_gates(essay_id, pack, body)
    report["essay_id"] = essay_id
    report["read_only"] = True
    report["wrote"] = False
    report["stored"] = False
    report["seat"] = "mechanical"
    return report
