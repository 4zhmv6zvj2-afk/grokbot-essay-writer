"""Pack checks before Word. Draft shows the issues; confirm records them."""

from __future__ import annotations

import re
from typing import Any

from essay_writer.canon import digest
from essay_writer.cite_open import in_text_page_issues
from essay_writer.confirm import (
    CONFIRM,
    DRAFT,
    confirm_ready,
    now,
    phase_refusal,
    refuse,
    save_draft,
)
from essay_writer.diary import blocked_identity_keys
from essay_writer.draft_from_review import (
    ARGUMENT,
    CRITICAL_REVIEW,
    argument_blockers,
    first_draft_blockers,
)
from essay_writer.invent import gather_sources, load_text_for
from essay_writer.known_paths import guard_write_door
from essay_writer.paths import module_code, sequence_write_error
from essay_writer.paths import work_dir as _work_dir
from essay_writer.programme import STYLE_ID
from essay_writer.state import load_state, save_state
from essay_writer.student_voice import speak
from essay_writer.textutil import (
    align_in_text_cites,
    check_genre,
    citation_tokens,
    complete_citation_sources,
    count_words,
    figure_source_line,
    genre_for,
    in_text_forms,
    reference_line,
    token_allowed,
    without_surname_stub_lists,
    word_rules_for,
)

TOOL = "essay.pack.validate"

CLARIFY_KEYS = ("objective", "background", "issues", "guidance")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "for",
    "from",
    "has",
    "have",
    "i",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "we",
    "with",
    "am",
    "sure",
}
_CONFIDENCE_RE = re.compile(
    r"\b(?:i am|i'm|we are|we're)\s+sure\b|\b\d{1,3}\s*%\s*sure\b|\b\d{1,3}%\b",
    re.IGNORECASE,
)


def pack_identity(essay_id: str, pack: dict[str, Any]) -> str:
    return digest({"essay_id": essay_id, "pack": pack})


def research_index(state: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, str | None]]:
    allowed: dict[str, dict[str, Any]] = {}
    digests: dict[str, str | None] = {"summary": None, "full": None}
    for depth in ("summary", "full"):
        record = (state.get("research") or {}).get(depth)
        if not isinstance(record, dict):
            continue
        digests[depth] = record.get("digest")
        for source in record.get("sources") or []:
            if isinstance(source, dict) and source.get("locator"):
                allowed[source["locator"]] = source
    return allowed, digests


def _body_text(sections: list[dict[str, str]]) -> str:
    return "\n".join(section["body"] for section in sections)


def _strip_citations(sentence: str) -> str:
    cleaned = re.sub(r"\([^)]*\)", " ", sentence)
    for token in citation_tokens(sentence):
        cleaned = cleaned.replace(token, " ")
        cleaned = cleaned.replace(f"({token})", " ")
    return cleaned


def _important_tokens(text: str) -> list[str]:
    scrubbed = _CONFIDENCE_RE.sub(" ", _strip_citations(text))
    tokens = re.findall(r"[a-z0-9]+", scrubbed.casefold())
    return [token for token in tokens if token not in _STOPWORDS and len(token) > 1]


def _gathered_excerpt(source: dict[str, Any], texts: dict[str, str]) -> str:
    quote = source.get("quote")
    if isinstance(quote, str) and quote.strip():
        return quote
    return texts.get(source["locator"], "")


def _claim_supported(sentence: str, source: dict[str, Any], texts: dict[str, str]) -> bool:
    excerpt = _gathered_excerpt(source, texts).casefold()
    if not excerpt.strip():
        return False
    tokens = _important_tokens(sentence)
    if not tokens:
        return False
    return all(token in excerpt for token in tokens)


def _sentence_in_body(sentence: str, body: str) -> bool:
    stripped = sentence.strip()
    return bool(stripped) and stripped in body


def _conclusion_section_body(sections: list[dict[str, str]]) -> str | None:
    for section in sections:
        if section["heading"].casefold() == "conclusion" and section["body"].strip():
            return section["body"]
    return None


def _parse_conclusion_claim(pack: dict[str, Any]) -> str | None:
    raw = pack.get("conclusion_claim")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    if isinstance(raw, dict):
        text = raw.get("text") or raw.get("sentence")
        if isinstance(text, str) and text.strip():
            return text.strip()
    return None


def _clarify_left_open(state: dict[str, Any]) -> bool:
    for depth in ("full", "summary"):
        record = (state.get("research") or {}).get(depth)
        if not isinstance(record, dict):
            continue
        clarify = record.get("clarify_context")
        if not isinstance(clarify, dict):
            continue
        for key in CLARIFY_KEYS:
            item = clarify.get(key)
            if isinstance(item, dict) and item.get("leave_open") is True:
                return True
    return False


def _research_has_opened_files(state: dict[str, Any]) -> bool:
    for depth in ("full", "summary"):
        record = (state.get("research") or {}).get(depth)
        if not isinstance(record, dict):
            continue
        opened = record.get("opened")
        if isinstance(opened, list) and opened:
            return True
        sources = record.get("sources")
        if isinstance(sources, list) and sources:
            return True
    return False


def _cited_sentences(body: str, forms: set[str]) -> list[str]:
    sentences: list[str] = []
    for chunk in re.split(r"(?<=[.!?])\s+", body):
        if any(token_allowed(token, forms) for token in citation_tokens(chunk)):
            sentences.append(chunk.strip())
    return sentences


def _stand_back_noted(
    pack: dict[str, Any],
    sections: list[dict[str, str]],
    sources: list[dict[str, Any]],
    used: set[str],
    forms: set[str],
    texts: dict[str, str],
    state: dict[str, Any],
    blockers: list[dict[str, str]],
    notes: list[dict[str, str]],
) -> None:
    if not used:
        blockers.append(
            {
                "code": "invent-forbid",
                "reason": (
                    "A noted conclusion needs a gathered source cited in the body. "
                    "Clarify context is not evidence. Leave the conclusion open, or cite a gathered source."
                ),
            }
        )
        return
    if not _research_has_opened_files(state):
        blockers.append(
            {
                "code": "conclusion",
                "reason": (
                    "A noted conclusion needs a confirmed research pack with at least one opened file. "
                    "Gather and confirm research first."
                ),
            }
        )
    if _clarify_left_open(state):
        blockers.append(
            {
                "code": "conclusion",
                "reason": (
                    "A noted conclusion is refused while objective, background, issues, or guidance "
                    "was left open. Clarify answers are not evidence. Leave the conclusion open, or "
                    "close the open boxes with real answers."
                ),
            }
        )
    body = _body_text(sections)
    by_id = {source["id"]: source for source in sources}
    asked = _parse_conclusion_claim(pack) or _conclusion_section_body(sections)
    if asked:
        if not _sentence_in_body(asked, body):
            blockers.append(
                {
                    "code": "conclusion",
                    "reason": (
                        "The asked ending is not already in the body. The door does not write a new "
                        "sentence. Put the ending in the pack, or leave the conclusion open."
                    ),
                }
            )
            return
        linked = None
        claim = pack.get("conclusion_claim")
        if isinstance(claim, dict) and isinstance(claim.get("source_id"), str):
            linked = by_id.get(claim["source_id"])
        if linked is None:
            for source in sources:
                own = in_text_forms(str(source.get("author") or ""), str(source.get("year") or ""))
                if any(token_allowed(token, own) for token in citation_tokens(asked)):
                    linked = source
                    break
        if linked is None:
            blockers.append(
                {
                    "code": "conclusion",
                    "reason": (
                        "The asked ending needs a gathered source cited on that sentence. "
                        "A confidence percent or “I am sure” is not support."
                    ),
                }
            )
            return
        if not _claim_supported(asked, linked, texts):
            blockers.append(
                {
                    "code": "conclusion",
                    "reason": (
                        "The asked ending is not supported by the gathered excerpt for that source. "
                        "Important words from the claim must appear in the gathered quote or file. "
                        "A confidence percent or “I am sure” is not support. Leave the conclusion open."
                    ),
                }
            )
        return
    supported = False
    for sentence in _cited_sentences(body, forms):
        for source in sources:
            own = in_text_forms(str(source.get("author") or ""), str(source.get("year") or ""))
            if not any(token_allowed(token, own) for token in citation_tokens(sentence)):
                continue
            if _claim_supported(sentence, source, texts):
                supported = True
                break
        if supported:
            break
    if not supported:
        blockers.append(
            {
                "code": "conclusion",
                "reason": (
                    "A noted conclusion needs a cited sentence whose important words appear in the "
                    "gathered excerpt. A confidence percent or “I am sure” is not support. "
                    "Leave the conclusion open, or cite a supported claim."
                ),
            }
        )


def _validate_formed_views(
    pack: dict[str, Any],
    sections: list[dict[str, str]],
    sources: list[dict[str, Any]],
    texts: dict[str, str],
    blockers: list[dict[str, str]],
    notes: list[dict[str, str]],
) -> None:
    raw = pack.get("formed_views")
    if raw is None:
        return
    if not isinstance(raw, list):
        blockers.append({"code": "pack", "reason": "formed_views must be a list"})
        return
    body = _body_text(sections)
    by_id = {source["id"]: source for source in sources}
    for index, item in enumerate(raw):
        label = f"formed_views[{index}]"
        if not isinstance(item, dict):
            blockers.append({"code": "pack", "reason": f"{label} must be an object"})
            continue
        sentence = item.get("sentence")
        if not isinstance(sentence, str) or not sentence.strip():
            blockers.append({"code": "pack", "reason": f"{label}.sentence is required"})
            continue
        sentence = sentence.strip()
        if not _sentence_in_body(sentence, body):
            blockers.append(
                {
                    "code": "conclusion",
                    "reason": (
                        f"{label} labels a sentence that is not already in the body. "
                        "The door does not write a new sentence to create a formed view."
                    ),
                }
            )
            continue
        source = by_id.get(item.get("source_id"))
        if source is None:
            blockers.append(
                {
                    "code": "invent-forbid",
                    "reason": f"{label} needs a gathered source_id.",
                }
            )
            continue
        quote = item.get("quote")
        if isinstance(quote, str) and quote.strip() and quote not in texts.get(source["locator"], ""):
            blockers.append(
                {
                    "code": "invent-forbid",
                    "reason": f"{label} quote is not an exact span of the gathered file.",
                }
            )
        if not _claim_supported(sentence, source, texts):
            blockers.append(
                {
                    "code": "conclusion",
                    "reason": (
                        f"{label} is not supported by the gathered excerpt. "
                        "A look-up miss is not support; the quotation must be in the gathered file."
                    ),
                }
            )
            continue
        notes.append(
            {
                "code": "formed-view",
                "reason": f"Formed view recorded for a sentence already in the body: {sentence[:120]}",
            }
        )


def inspect_pack(essay_id: str, pack: object) -> dict[str, Any]:
    blockers: list[dict[str, str]] = []
    notes: list[dict[str, str]] = []
    if not isinstance(pack, dict):
        return _empty(blockers=[{"code": "pack", "reason": "pack must be an object"}])
    pack_id = pack.get("essay_id")
    module = module_code(essay_id) if isinstance(essay_id, str) else essay_id
    if pack_id not in (None, essay_id, module):
        blockers.append(
            {
                "code": "cross-essay",
                "reason": "pack essay_id does not match this essay. Packs are not mixed.",
            }
        )

    for key in blocked_identity_keys(essay_id, pack):
        blockers.append(
            {
                "code": "student",
                "reason": f"{key} is not written. Do not put a student name or number on the work.",
            }
        )
    output = pack.get("format", "docx")
    if output != "docx":
        blockers.append({"code": "word-only", "reason": "Word .docx is the only output. PDF is refused."})
    if pack.get("referencing") != STYLE_ID:
        blockers.append(
            {
                "code": "referencing",
                "reason": "referencing must be harvard. The door does not guess another style.",
            }
        )
    title = pack.get("title")
    if not isinstance(title, str) or not title.strip():
        blockers.append({"code": "pack", "reason": "title is required"})
    sections = pack.get("sections")
    if not isinstance(sections, list) or not sections:
        blockers.append({"code": "pack", "reason": "sections must be a non-empty list"})
        sections = []
    clean_sections: list[dict[str, str]] = []
    for index, section in enumerate(sections):
        if not isinstance(section, dict):
            blockers.append({"code": "pack", "reason": f"sections[{index}] must be an object"})
            continue
        heading = section.get("heading")
        body = section.get("body")
        if not isinstance(heading, str) or not heading.strip():
            blockers.append({"code": "pack", "reason": f"sections[{index}].heading is required"})
            heading = ""
        if not isinstance(body, str):
            blockers.append({"code": "pack", "reason": f"sections[{index}].body must be text"})
            body = ""
        clean_sections.append({"heading": heading.strip(), "body": body})
    from essay_writer.brief_contract import named_heading_issues

    for reason in named_heading_issues(
        essay_id,
        [section["heading"] for section in clean_sections],
    ):
        blockers.append({"code": "named-parts", "reason": reason})
    genre_blocker = check_genre(
        essay_id,
        pack,
        [section["heading"] for section in clean_sections],
    )
    if genre_blocker:
        blockers.append(genre_blocker)
    sources, source_issues = gather_sources(essay_id, pack.get("sources"))
    blockers.extend(source_issues)
    state = load_state(essay_id)
    allowed, research_digests = research_index(state)
    sources = complete_citation_sources(sources, allowed)
    clean_sections = without_surname_stub_lists(clean_sections, sources)
    clean_sections = [
        {
            "heading": section["heading"],
            "body": align_in_text_cites(section["body"], sources),
        }
        for section in clean_sections
    ]
    if research_digests["summary"] is None and research_digests["full"] is None:
        blockers.append(
            {
                "code": "research",
                "reason": "Confirm research for this essay before validating a pack.",
            }
        )
    for source in sources:
        prior = allowed.get(source["locator"])
        if prior is None:
            blockers.append(
                {
                    "code": "research",
                    "reason": (
                        f"{source['locator']} was not in the confirmed research. "
                        "Confirm a new research draft before this source can enter the pack."
                    ),
                }
            )
            continue
        if prior.get("sha256") != source.get("sha256"):
            blockers.append(
                {
                    "code": "sources-changed",
                    "reason": f"{source['locator']} changed after research was confirmed. Research again.",
                }
            )
    forms: set[str] = set()
    for source in sources:
        if source.get("author") and source.get("year"):
            forms |= in_text_forms(str(source["author"]), str(source["year"]))
    used: set[str] = set()
    for section in clean_sections:
        for token in citation_tokens(section["body"]):
            if not token_allowed(token, forms):
                blockers.append(
                    {
                        "code": "invent-forbid",
                        "reason": (
                            f"In-text citation {token!r} is not one of the gathered sources. "
                            "Omit it, or gather the source first."
                        ),
                    }
                )
            else:
                used.add(token)
    blockers.extend(in_text_page_issues(clean_sections, sources))
    for source in sources:
        if source.get("author") and source.get("year"):
            own = in_text_forms(str(source["author"]), str(source["year"]))
            if not any(token_allowed(token, own) for token in used):
                notes.append(
                    {
                        "code": "unused-source",
                        "reason": f"{source['id']} is gathered but not used in the body.",
                    }
                )
    source_texts = {source["locator"]: load_text_for(source) for source in sources}
    conclusion = pack.get("conclusion")
    if conclusion not in {"noted", "open"}:
        blockers.append(
            {
                "code": "conclusion",
                "reason": (
                    "conclusion must be noted or open. The door does not choose, and it does not "
                    "change open into noted. Clarify answers are not evidence enough to close it."
                ),
            }
        )
    elif conclusion == "noted":
        _stand_back_noted(
            pack,
            clean_sections,
            sources,
            used,
            forms,
            source_texts,
            state,
            blockers,
            notes,
        )
    elif conclusion == "open":
        notes.append(
            {
                "code": "conclusion",
                "reason": "Conclusion stays open. Word will label it as not a settled finding.",
            }
        )
    _validate_formed_views(pack, clean_sections, sources, source_texts, blockers, notes)
    _lock_claim_excerpts(pack, sources, clean_sections, source_texts, blockers)
    figures, figure_blockers = _visuals(pack.get("figures"), sources, "Figure")
    tables, table_blockers = _visuals(pack.get("tables"), sources, "Table")
    blockers.extend(figure_blockers)
    blockers.extend(table_blockers)
    rules = word_rules_for(essay_id, pack)
    counted = sum(
        count_words(
            section["body"],
            exclude_citations=bool(rules.get("exclude_in_text_citations")),
        )
        for section in clean_sections
    )
    word_count = _word_gate(pack, counted, blockers, notes, rules, essay_id)
    from essay_writer.brief_contract import missing_title_fields

    cover_report = {
        "title": pack.get("title") or pack.get("assessment"),
        "word_count": word_count,
    }
    for field in missing_title_fields(essay_id, pack, cover_report):
        blockers.append(
            {
                "code": "title-page",
                "reason": (
                    f"The title page is missing the {field}. Supply it. "
                    "It is not invented and it is not taken from a sample."
                ),
            }
        )
    from essay_writer.brief_checks import before_word, decorative_citations

    brief_view = before_word(
        essay_id,
        clean_sections,
        acknowledged_sections=pack.get("section_words_acknowledged") is True,
        acknowledged_contradiction=pack.get("contradiction_acknowledged") is True,
        acknowledged_simulation=pack.get("simulation_acknowledged") is True,
        exclude_citations=bool(rules.get("exclude_in_text_citations")),
        gathered=list(source_texts.values()),
    )
    blockers.extend(brief_view["blockers"])
    notes.extend(brief_view["notes"])
    if clean_sections:
        from essay_writer.mark_fit import mark_fit_notes

        notes.extend(mark_fit_notes(essay_id, clean_sections, sources))
    parked = decorative_citations("\n".join(section["body"] for section in clean_sections))
    for sentence in parked:
        blockers.append(
            {
                "code": "decorative-citation",
                "reason": (
                    "A citation is parked on a general sentence. "
                    "Tie it to a specific result from a gathered source, or remove it. "
                    + sentence
                ),
            }
        )
    if "critical_reviews" in pack or pack.get("author_from") == "critical-review":
        blockers.extend(
            first_draft_blockers(
                sources,
                pack.get("critical_reviews"),
                pack.get("reopen"),
            )
        )
        blockers.extend(argument_blockers(essay_id, clean_sections, pack.get("critical_reviews")))
    if pack.get("voice") == "third-person":
        notes.extend(_voice_notes(clean_sections))
    files = {source["locator"]: source["sha256"] for source in sources}
    references = [reference_line(source) for source in sources]
    return {
        "passed": not blockers,
        "blockers": blockers,
        "notes": notes,
        "files": files,
        "sources": sources,
        "sections": clean_sections,
        "word_count": word_count,
        "section_budgets": brief_view["section_budgets"],
        "brief_contradictions": brief_view["brief_contradictions"],
        "safe_default": brief_view["safe_default"],
        "simulation_events": brief_view["simulation_events"],
        "references": references,
        "figures": figures,
        "tables": tables,
        "research": research_digests,
        "title": title.strip() if isinstance(title, str) else "",
        "genre": genre_for(essay_id, pack).get("genre"),
    }


def _empty(**kwargs: Any) -> dict[str, Any]:
    body = {
        "passed": False,
        "blockers": [],
        "notes": [],
        "files": {},
        "sources": [],
        "sections": [],
        "word_count": {"counted": 0, "stated": None, "limit": None, "inside": None},
        "section_budgets": [],
        "brief_contradictions": [],
        "safe_default": None,
        "simulation_events": {"noticed": False},
        "references": [],
        "figures": [],
        "tables": [],
        "research": {"summary": None, "full": None},
        "title": "",
        "genre": None,
    }
    body.update(kwargs)
    return body


def _word_gate(
    pack: dict[str, Any],
    counted: int,
    blockers: list[dict[str, str]],
    notes: list[dict[str, str]],
    rules: dict[str, Any],
    essay_id: str = "",
) -> dict[str, Any]:
    stated = pack.get("stated_word_count")
    stated_value = stated if isinstance(stated, int) else None
    limit = rules.get("limit") if isinstance(rules.get("limit"), int) else None
    tolerance = rules.get("tolerance", 0.10)
    if not isinstance(tolerance, (int, float)) or isinstance(tolerance, bool):
        tolerance = 0.10
    low = high = None
    inside = None
    if limit is not None:
        low = int(limit * (1 - float(tolerance)))
        high = int(limit * (1 + float(tolerance)))
        inside = low <= counted <= high
        if not inside:
            waived = False
            if (
                essay_id
                and high is not None
                and counted > high
                and pack.get("word_count_acknowledged") is not True
            ):
                from essay_writer.rewrite_baseline import (
                    rewrite_vs_opened_word,
                    stricter_invented_max,
                )

                if stricter_invented_max(essay_id, rules, high=high) is not None:
                    decision = rewrite_vs_opened_word(
                        essay_id,
                        "",
                        rules,
                        counted=counted,
                        high=high,
                        counter="words",
                        exclude_citations=bool(rules.get("exclude_in_text_citations")),
                    )
                    waived = bool(decision["waive_word"] and not decision["document_still_fails"])
            if pack.get("word_count_acknowledged") is True:
                notes.append(
                    {
                        "code": "word-count",
                        "reason": "Counted words sit outside the declared band. A person acknowledged that.",
                    }
                )
            elif waived:
                notes.append(
                    {
                        "code": "word-count",
                        "reason": "The opened Word file already exceeds this invented band.",
                    }
                )
            elif counted < low and pack.get("word_band_shortfall"):
                blockers.append(
                    {
                        "code": "word-count",
                        "reason": (
                            f"The draft is short: {counted} words against {low}–{high}. "
                            "The gathered files do not hold another claim to add without repeating one. "
                            "Ask the student for another source."
                        ),
                    }
                )
            else:
                blockers.append(
                    {
                        "code": "word-count",
                        "reason": (
                            f"Counted words {counted} sit outside {low}–{high}. "
                            "Fix the draft, or set word_count_acknowledged true only after a person accepts it. "
                            "The door does not set that flag."
                        ),
                    }
                )
    return {
        "counted": counted,
        "stated": stated_value,
        "limit": limit,
        "low": low,
        "high": high,
        "inside": inside,
    }


def _excerpt_text(item: object) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        raw = item.get("excerpt")
        if not isinstance(raw, str) or not raw.strip():
            raw = item.get("quote")
        if isinstance(raw, str):
            return raw.strip()
    return ""


def _lock_claim_excerpts(
    pack: dict[str, Any],
    sources: list[dict[str, Any]],
    sections: list[dict[str, str]],
    texts: dict[str, str],
    blockers: list[dict[str, str]],
) -> None:
    """A draft body that already has sources waits until each claim excerpt is locked.

    A missing excerpt list is measurement. An excerpt that is not in the file is invent-forbid.
    """
    if not sources or not _body_text(sections).strip():
        return
    file_text = "\n".join(texts.values())
    if "excerpts" not in pack:
        quotes = [
            source["quote"]
            for source in sources
            if isinstance(source.get("quote"), str) and source["quote"].strip()
        ]
        if quotes and all(quote in file_text for quote in quotes):
            return
        blockers.append(
            {
                "code": "measurement",
                "reason": (
                    "This draft has gathered sources, and the excerpt list for each claim is missing. "
                    "Lock an excerpt from the file before this draft can continue."
                ),
            }
        )
        return
    excerpts = pack.get("excerpts")
    if not isinstance(excerpts, list) or not excerpts:
        blockers.append(
            {
                "code": "measurement",
                "reason": (
                    "This draft has gathered sources, and the excerpt list for each claim is missing. "
                    "Lock an excerpt from the file before this draft can continue."
                ),
            }
        )
        return
    for index, item in enumerate(excerpts):
        excerpt = _excerpt_text(item)
        if not excerpt:
            blockers.append(
                {
                    "code": "measurement",
                    "reason": f"excerpts[{index}] has no locked excerpt for that claim.",
                }
            )
            continue
        if excerpt not in file_text:
            blockers.append(
                {
                    "code": "invent-forbid",
                    "reason": (
                        f"excerpts[{index}] is not in the gathered file. "
                        "Do not invent an excerpt."
                    ),
                }
            )


def _voice_notes(sections: list[dict[str, str]]) -> list[dict[str, str]]:
    import re

    notes = []
    pattern = re.compile(r"\b(I|we|my|our|me)\b")
    for section in sections:
        body = re.sub(r"[\"“][^\"”]*[\"”]", " ", section["body"])
        if pattern.search(body):
            notes.append(
                {
                    "code": "voice",
                    "reason": f"{section['heading'] or 'section'} uses a first-person word. The pack asked for third person.",
                }
            )
    return notes


def _visuals(
    items: object, sources: list[dict[str, Any]], kind: str
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    if items is None:
        return [], []
    if not isinstance(items, list):
        return [], [{"code": "pack", "reason": f"{kind.lower()}s must be a list"}]
    by_id = {source["id"]: source for source in sources}
    visuals: list[dict[str, str]] = []
    blockers: list[dict[str, str]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            blockers.append({"code": "pack", "reason": f"{kind.lower()}s[{index}] must be an object"})
            continue
        title = item.get("title")
        if not isinstance(title, str) or not title.strip():
            blockers.append({"code": "pack", "reason": f"{kind.lower()}s[{index}].title is required"})
            title = ""
        source = by_id.get(item.get("source_id"))
        if source is None:
            blockers.append(
                {
                    "code": "invent-forbid",
                    "reason": f"{kind} {index + 1} has no gathered source_id.",
                }
            )
            continue
        line = figure_source_line(source)
        if line is None:
            blockers.append(
                {
                    "code": "invent-forbid",
                    "reason": f"{kind} {index + 1} needs a gathered author. A URL is not a figure or table source.",
                }
            )
            continue
        number = item.get("number", index + 1)
        visuals.append(
            {
                "label": f"{kind} {number}. {title.strip()}",
                "source_line": line,
            }
        )
    return visuals, blockers


def _pack_assignment_text(pack: dict[str, Any]) -> str:
    """Title, format words, and section text the constitution can see."""
    parts: list[str] = []
    for key in ("title", "assessment", "genre"):
        value = pack.get(key)
        if isinstance(value, str):
            parts.append(value)
    sections = pack.get("sections")
    if isinstance(sections, list):
        for section in sections:
            if not isinstance(section, dict):
                continue
            heading = section.get("heading")
            body = section.get("body")
            if isinstance(heading, str):
                parts.append(heading)
            if isinstance(body, str):
                parts.append(body)
    return "\n".join(parts)


def essay_pack_validate(
    essay_id: str,
    pack: dict[str, Any],
    confirmPhase: str | None = None,
) -> dict[str, Any]:
    id_error = sequence_write_error(essay_id)
    if id_error:
        return refuse("essay-id", id_error)
    phase = phase_refusal(confirmPhase)
    if phase:
        return phase

    blocked = guard_write_door(_work_dir(essay_id))
    if blocked:
        return blocked
    if not isinstance(pack, dict):
        return refuse("pack", "pack must be an object")
    from essay_writer.specialists.writer import accept_draft

    blocked_gate = accept_draft(essay_id, _pack_assignment_text(pack))
    if blocked_gate:
        return blocked_gate
    report = inspect_pack(essay_id, pack)
    hard = [
        item
        for item in report["blockers"]
        if item["code"] in {"invent-forbid", "cross-essay", "measurement", CRITICAL_REVIEW, ARGUMENT}
    ]
    payload = {"essay_id": essay_id, "pack": pack}
    fingerprint = {"files": report["files"], "research": report["research"]}
    identity = pack_identity(essay_id, pack)
    body: dict[str, Any] = {
        "ok": not hard,
        "passed": report["passed"],
        "essay_id": essay_id,
        "confirmPhase": confirmPhase,
        "wrote": False,
        "stored": False,
        "pack_digest": identity,
        "blockers": report["blockers"],
        "notes": report["notes"],
        "word_count": report["word_count"],
        "section_budgets": report.get("section_budgets") or [],
        "brief_contradictions": report.get("brief_contradictions") or [],
        "safe_default": report.get("safe_default"),
        "simulation_events": report.get("simulation_events") or {"noticed": False},
        "references": report["references"],
        "sources": report.get("sources") or [],
        "figures": report["figures"],
        "tables": report["tables"],
        "research": report["research"],
        "referencing": STYLE_ID,
        "same_arguments_required": True,
    }
    if hard:
        body["refused"] = hard[0]["code"]
        body["reason"] = hard[0]["reason"]
        body["invent_forbid"] = (
            "refuse" if any(item["code"] == "invent-forbid" for item in hard) else "pass"
        )
        return speak(body)
    if confirmPhase == DRAFT:
        body["digest"] = save_draft(essay_id, TOOL, payload, fingerprint)
        body["ok"] = True
        body["next"] = (
            "Show these checks to the human. Confirm with the same pack only after an explicit yes. "
            "A changed pack needs a fresh draft."
        )
        return speak(body)
    ready = confirm_ready(essay_id, TOOL, payload, fingerprint)
    if ready.get("ok") is False:
        ready["confirmPhase"] = CONFIRM
        ready["pack_digest"] = identity
        return speak(ready)
    state = load_state(essay_id)
    state["validations"][identity] = {
        "ok": report["passed"],
        "blockers": report["blockers"],
        "notes": report["notes"],
        "files": report["files"],
        "research": report["research"],
        "word_count": report["word_count"],
        "confirmed_at": now(),
        "pack_digest": identity,
    }
    save_state(essay_id, state)
    from essay_writer.pack_backup import snapshot_after_pack_validate

    snapshot_after_pack_validate(essay_id, pack)
    body["stored"] = True
    body["ok"] = True
    body["recorded_pass"] = report["passed"]
    body["digest"] = ready["digest"]
    body["next"] = (
        "Validation is recorded. Word can be drafted only for this same pack."
        if report["passed"]
        else "Validation is recorded as not passed. Word will not be written until the blockers are gone."
    )
    return speak(body)
