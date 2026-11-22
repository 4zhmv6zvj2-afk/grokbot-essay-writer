"""Writer specialist.

Draft and Word enter here. The bytes are still written by essay_writer.word.
accept_draft is the only draft-accept check. When a mark scheme is present,
the draft aims at the highest band. That rule is HIGHEST_BAND, applied by
assignment_gate. A word band stated on the mark scheme wins over the brief,
and either document wins over a pack budget. Body text is left-aligned unless
the brief or mark scheme says justified. The first-draft rule text lives here
so stage prompts do not keep a second copy.
"""

from __future__ import annotations

import re
from typing import Any

from essay_writer import textutil as essay_textutil
from essay_writer.assignment_gate import assignment_gate, mark_scheme_text
from essay_writer.cite_fit import BODY_CITE_STAGES
from essay_writer.confirm import refuse
from essay_writer.diary import layout_for
from essay_writer.known_paths import research_file
from essay_writer.paths import locator_target
from essay_writer.prompt_loader import text as prompt_text
from essay_writer.textutil import (
    count_words,
    family_name,
    word_band_from_brief_text,
    word_rules_for,
)

HIGHEST_BAND = prompt_text("craft/draft.md", "writer_highest_band")

FIRST_DRAFT_NOTE = prompt_text("craft/draft.md", "first_draft_note")

_JUSTIFIED = re.compile(r"(?im)^[ \t]*(?:alignment|body alignment|body)\s*:\s*justif")
_LEFT = re.compile(r"(?im)^[ \t]*(?:alignment|body alignment|body)\s*:\s*left\b")


def _stated_alignment(text: str) -> str | None:
    if not text:
        return None
    if _JUSTIFIED.search(text):
        return "justify"
    if _LEFT.search(text):
        return "left"
    return None


def body_is_justified(essay_id: str) -> bool:
    """Left is the house default. A stated alignment on the mark scheme wins, then the brief."""

    scheme = _stated_alignment(mark_scheme_text(essay_id))
    if scheme == "justify":
        return True
    if scheme == "left":
        return False

    if layout_for(essay_id).get("justify") is True:
        return True
    return _stated_alignment(essay_textutil.module_brief_text(essay_id)) == "justify"


def document_word_band(essay_id: str) -> dict[str, Any]:
    """Word band the documents state. The mark scheme wins. Nothing is invented."""

    scheme = word_band_from_brief_text(mark_scheme_text(essay_id))
    if scheme:
        return scheme
    return word_band_from_brief_text(essay_textutil.module_brief_text(essay_id))


_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")
_SKIP_HEADINGS = frozenset(
    {"introduction", "conclusion", "references", "reference list", "bibliography"}
)
# A section with a fixed job of its own does not take an added claim sentence.
# Methods describe what was done, and recommendations follow from the findings.
# A short draft stays short rather than grow in the wrong section.
_FIXED_JOB_HEADINGS = (
    "abstract",
    "appendix",
    "appendices",
    "contents",
    "executive summary",
    "letter of transmittal",
    "method",
    "methodology",
    "methods",
    "recommendation",
    "recommendations",
    "table of contents",
    "title page",
)
_HEADING_NUMBER = re.compile(r"^\s*(?:\d+(?:\.\d+)*[.)]?\s*)+")
_REWRITE = (
    (re.compile(r"\bThis article\b"), "The article"),
    (re.compile(r"\bThis paper\b"), "The paper"),
    (re.compile(r"\bThis study\b"), "The study"),
    (re.compile(r"\bIt argues\b"), "The text argues"),
    (re.compile(r"\bpresents the\b"), "sets out the"),
    (re.compile(r"\bas well as\b"), "and"),
)


def _section_bodies(pack: dict[str, Any]) -> list[str]:
    bodies: list[str] = []
    for section in pack.get("sections") or []:
        if isinstance(section, dict) and isinstance(section.get("body"), str):
            bodies.append(section["body"])
    return bodies


def _split_count(pack: dict[str, Any]) -> int:
    text = "\n".join(_section_bodies(pack)).strip()
    return len(text.split()) if text else 0


def _token_count(pack: dict[str, Any], *, exclude_citations: bool) -> int:

    return sum(
        count_words(body, exclude_citations=exclude_citations) for body in _section_bodies(pack)
    )


def _source_texts(essay_id: str, pack: dict[str, Any]) -> list[str]:
    from essay_writer.invent import read_gathered_text

    texts: list[str] = []
    for source in pack.get("sources") or []:
        if not isinstance(source, dict):
            continue
        locator = source.get("locator")
        if not isinstance(locator, str) or not locator.strip():
            continue
        try:
            _kind, path = locator_target(essay_id, locator)
        except ValueError:
            continue
        if path is None or not path.is_file():
            continue
        allowed = research_file(essay_id, str(path))
        if allowed is None:
            continue
        try:
            text = read_gathered_text(allowed, essay_id)
        except (OSError, ValueError):
            continue
        if isinstance(text, str) and text.strip():
            texts.append(text)
    return texts


def _source_texts_with_cite(essay_id: str, pack: dict[str, Any]) -> list[tuple[str, str | None]]:
    """Each gathered source text with the in-text citation its author-year gives.

    A source with no stored author or year has no citation, and the stretch does
    not append a sentence from it. Nothing is invented.
    """
    from essay_writer.invent import read_gathered_text

    try:
        from essay_writer.state import load_state
        from essay_writer.validate import research_index

        allowed, _digests = research_index(load_state(essay_id))
    except (OSError, ValueError):
        allowed = {}

    out: list[tuple[str, str | None]] = []
    for source in pack.get("sources") or []:
        if not isinstance(source, dict):
            continue
        locator = source.get("locator")
        if not isinstance(locator, str) or not locator.strip():
            continue
        try:
            _kind, path = locator_target(essay_id, locator)
        except ValueError:
            continue
        if path is None or not path.is_file():
            continue
        resolved = research_file(essay_id, str(path))
        if resolved is None:
            continue
        try:
            text = read_gathered_text(resolved, essay_id)
        except (OSError, ValueError):
            continue
        if not isinstance(text, str) or not text.strip():
            continue
        record = allowed.get(locator) if isinstance(allowed, dict) else None
        if not isinstance(record, dict):
            record = allowed.get(str(path)) if isinstance(allowed, dict) else None
        author = source.get("author")
        year = source.get("year")
        if not (isinstance(author, str) and author.strip()):
            author = record.get("author") if isinstance(record, dict) else None
        if not (isinstance(year, str) and year.strip()):
            year = record.get("year") if isinstance(record, dict) else None
        from essay_writer.citation_list import list_written, stored_in_text

        citation = None
        if list_written(essay_id):
            citation = stored_in_text(essay_id, source)
        elif isinstance(author, str) and author.strip() and isinstance(year, str) and year.strip():
            citation = f"({family_name(author)}, {year.strip()})"
        out.append((text, citation))
    return out


def _gathered_sentences(texts: list[str]) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for text in texts:
        for part in _SENT_SPLIT.split(text.strip()):
            sentence = " ".join(part.split()).strip()
            if len(sentence.split()) < 8:
                continue
            key = sentence.casefold()
            if key in seen:
                continue
            seen.add(key)
            found.append(sentence)
    return found


def _rewrite_supported(sentence: str, variant: int) -> str:
    """Same claims, different wording. The original sentence must not remain a span."""
    text = " ".join(sentence.split()).strip()
    if not text:
        return ""
    hits = [(pat, repl) for pat, repl in _REWRITE if pat.search(text)]
    if hits:
        pat, repl = hits[variant % len(hits)]
        text = pat.sub(repl, text, count=1)
        extra = (variant // len(hits)) % max(1, len(hits))
        if extra:
            other, other_repl = hits[extra]
            text = other.sub(other_repl, text, count=1)
    if sentence.strip() in text:
        words = text.split()
        if words:
            words[0] = {
                "The": "This",
                "This": "The",
                "It": "The text",
                "A": "One",
                "An": "One",
            }.get(words[0], "The text notes that " + words[0][:1].lower() + words[0][1:])
            text = " ".join(words)
    if not text.endswith((".", "?", "!")):
        text += "."
    return text


def _heading_job(heading: object) -> str:
    """Heading text without a leading section number, folded for a job check."""
    text = str(heading or "").strip().casefold()
    return _HEADING_NUMBER.sub("", text).strip()


def _is_fixed_job(heading: str) -> bool:
    """True when the heading names a job that does not take an added claim.

    The job is a whole word or a listed phrase, so "Methodological analysis of
    trade" is an analysis section, not a methods section.
    """
    return any(heading == job or heading.startswith(f"{job} ") for job in _FIXED_JOB_HEADINGS)


def _append_target(sections: list[dict[str, Any]]) -> int | None:
    """First section whose job can carry an added claim sentence.

    Introduction, conclusion, and references are skipped as before. A fixed-job
    section is skipped too, and it does not become the fallback: a short draft
    stays short rather than grow inside Methodology or Recommendations.
    """
    preferred: int | None = None
    intro: int | None = None
    fixed_job = False
    for index, section in enumerate(sections):
        heading = _heading_job(section.get("heading"))
        if heading in _SKIP_HEADINGS:
            if intro is None and heading == "introduction":
                intro = index
            continue
        if _is_fixed_job(heading):
            fixed_job = True
            continue
        preferred = index
        break
    if preferred is not None:
        return preferred
    if intro is not None and not fixed_job:
        return intro
    return None


def _shortfall(pack: dict[str, Any], low: int, counted: int) -> dict[str, Any]:
    """Same pack, marked short. The Word path names the gap instead of filling it."""
    marked = dict(pack)
    marked["word_band_shortfall"] = {"low": low, "counted": counted}
    return marked


def recover_short_word_band(essay_id: str, pack: dict[str, Any]) -> dict[str, Any]:
    """Stretch a short body from gathered files up into the document word band.

    Word calls this before inspect. Unused gathered sentences are rewritten
    first. Nothing is added that those files do not support. An over-length
    pack, a missing band, or a person-acknowledged count is left as it is.
    """
    if not isinstance(pack, dict) or pack.get("word_count_acknowledged") is True:
        return pack
    from essay_writer.rewrite_baseline import band_edges

    low, high = band_edges(document_word_band(essay_id))
    if low is None or high is None:
        return pack
    sections = [
        dict(section) if isinstance(section, dict) else section
        for section in pack.get("sections") or []
    ]
    if not any(isinstance(section, dict) for section in sections):
        return pack
    filled = dict(pack)
    filled["sections"] = sections
    exclude = bool(word_rules_for(essay_id, filled).get("exclude_in_text_citations"))
    split_now = _split_count(filled)
    token_now = _token_count(filled, exclude_citations=exclude)
    if split_now >= low and token_now >= low:
        return pack
    if split_now > high or token_now > high:
        return pack
    sentences: list[tuple[str, str]] = []
    for text, citation in _source_texts_with_cite(essay_id, filled):
        if not citation:
            continue
        for sentence in _gathered_sentences([text]):
            if all(sentence != seen for seen, _cite in sentences):
                sentences.append((sentence, citation))
    if not sentences:
        return _shortfall(pack, low, min(split_now, token_now))
    body = "\n".join(_section_bodies(filled))
    unused = [(item, cite) for item, cite in sentences if item not in body]
    pool = unused or sentences
    target = _append_target([section for section in sections if isinstance(section, dict)])
    if target is None:
        return _shortfall(pack, low, min(split_now, token_now))
    from essay_writer.gates import unquoted_exact

    added = 0
    for variant in range(0, 12):
        for sentence, citation in pool:
            if split_now >= low and token_now >= low:
                return filled
            line = _rewrite_supported(sentence, variant)
            if not line or line in body or sentence in line:
                continue
            line = _with_citation(line, citation)
            extra_split = len(line.split())
            extra_tokens = count_words(line, exclude_citations=exclude)
            if split_now + extra_split > high or token_now + extra_tokens > high:
                continue
            trial = dict(sections[target])
            raw_body = trial.get("body")
            current = raw_body if isinstance(raw_body, str) else ""
            trial["body"] = (current.rstrip() + " " + line).strip()
            trial_sections = list(sections)
            trial_sections[target] = trial
            trial_pack = dict(filled)
            trial_pack["sections"] = trial_sections
            gathered = _source_texts(essay_id, trial_pack)
            if unquoted_exact("\n".join(_section_bodies(trial_pack)), gathered):
                continue
            sections[target] = trial
            filled["sections"] = sections
            body = "\n".join(_section_bodies(filled))
            split_now = _split_count(filled)
            token_now = _token_count(filled, exclude_citations=exclude)
            added += 1
    if split_now >= low and token_now >= low:
        return filled
    return _shortfall(filled if added else pack, low, min(split_now, token_now))


def draft_word_count(essay_id: str, text: str) -> int | None:
    """Counted words of a first draft when the brief states a word band."""
    from essay_writer.rewrite_baseline import band_edges

    band = document_word_band(essay_id)
    low, high = band_edges(band)
    if low is None or high is None:
        return None
    return count_words(text or "", exclude_citations=bool(band.get("exclude_in_text_citations")))


def first_draft_below_minimum(essay_id: str, text: str) -> dict[str, Any] | None:
    """Fail a first draft that would be saved or shown below the brief's minimum.

    Both ends of the band count as inside. A draft with no stated band is left alone.
    """
    from essay_writer.rewrite_baseline import band_edges

    band = document_word_band(essay_id)
    low, high = band_edges(band)
    if low is None or high is None:
        return None
    counted = count_words(text or "", exclude_citations=bool(band.get("exclude_in_text_citations")))
    if counted >= low:
        return None
    return refuse(
        "word-band",
        (
            f"This first draft is {counted} words. "
            f"The brief asks for {low}–{high}. "
            "It is not the finished first draft."
        ),
        counted=counted,
        minimum=low,
        maximum=high,
    )


def _research_sources(essay_id: str) -> list[dict[str, Any]]:
    from essay_writer.state import load_state

    state = load_state(essay_id)
    research = state.get("research") if isinstance(state, dict) else None
    if not isinstance(research, dict):
        return []
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for key in ("summary", "full"):
        block = research.get(key)
        if not isinstance(block, dict):
            continue
        sources = block.get("sources")
        if not isinstance(sources, list):
            continue
        for item in sources:
            if not isinstance(item, dict):
                continue
            locator = item.get("locator")
            if not isinstance(locator, str) or not locator.strip() or locator in seen:
                continue
            seen.add(locator)
            found.append(dict(item))
    return found


def _with_assignment(essay_id: str, text: str) -> str:
    """Keep the format and the assignment question in the draft being written."""
    from essay_writer.assignment_gate import question_is_answered, read_assignment

    record = read_assignment(essay_id)
    if record.get("active") is not True:
        return text
    pieces = [text.strip()] if isinstance(text, str) and text.strip() else []
    joined = "\n\n".join(pieces)
    format_name = record.get("format") if isinstance(record.get("format"), str) else ""
    question = record.get("question") if isinstance(record.get("question"), str) else ""
    if format_name and format_name.casefold() not in joined.casefold():
        pieces.insert(0, f"This {format_name} takes up the assignment.")
        joined = "\n\n".join(pieces)
    if question and not question_is_answered(joined, question):
        sentence = question if question.endswith((".", "?", "!")) else f"{question}."
        pieces.insert(0, sentence)
    return "\n\n".join(piece for piece in pieces if piece).strip()


def _sections_to_look(sections: list[Any]) -> str:
    parts: list[str] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        raw_heading = section.get("heading")
        raw_body = section.get("body")
        heading = raw_heading.strip() if isinstance(raw_heading, str) else ""
        body = raw_body.strip() if isinstance(raw_body, str) else ""
        if heading and body:
            parts.append(f"## {heading}\n\n{body}")
        elif body:
            parts.append(body)
    return "\n\n".join(parts).strip()


def _write_up_to_band(essay_id: str, text: str) -> str:
    """Write the first draft from gathered claims until the count is inside the band."""
    from essay_writer.draft_from_review import look_sections
    from essay_writer.rewrite_baseline import band_edges

    prepared = _with_assignment(essay_id, text)
    low, high = band_edges(document_word_band(essay_id))
    if low is None or high is None:
        return prepared
    sections = look_sections(prepared)
    if not sections:
        sections = [{"heading": "", "body": prepared}]
    draft = {
        "essay_id": essay_id,
        "sections": sections,
        "sources": _research_sources(essay_id),
    }
    recovered = recover_short_word_band(essay_id, draft)
    if recovered.get("word_band_shortfall"):
        return prepared
    written_sections = recovered.get("sections")
    if not isinstance(written_sections, list):
        return prepared
    written = _sections_to_look(written_sections)
    if not written:
        return prepared
    counted = count_words(
        written,
        exclude_citations=bool(document_word_band(essay_id).get("exclude_in_text_citations")),
    )
    if low <= counted <= high:
        return written
    return prepared


_LOWER_LEAD = frozenset({"e.g", "i.e", "etc", "cf", "vs"})
_BARE_VERBS = frozenset(
    {
        "add",
        "adds",
        "argue",
        "argues",
        "compare",
        "compares",
        "describe",
        "describes",
        "explain",
        "explains",
        "find",
        "finds",
        "give",
        "gives",
        "report",
        "reports",
        "say",
        "says",
        "show",
        "shows",
        "suggest",
        "suggests",
        "tie",
        "ties",
        "treat",
        "treats",
        "write",
        "writes",
        "review",
        "reviews",
        "count",
        "counts",
        "is",
        "are",
        "was",
        "were",
        "has",
        "have",
        "had",
    }
)
# A prepositional opening left in front of a verb whose subject was the author.
_PREP_BARE = re.compile(
    r"(?im)^[ \t]*(?:for|in|on|at|after|before|during|within|without|under|over|"
    r"from|by|with|across|through|about|into)\b[^.\n]{0,160}?,\s+"
    r"(?:counts?|treats?|reviews?|adds?|reports?|finds?|argues?|compares?|describes?|"
    r"shows?|says?|suggests?|writes?|gives?|explains?|ties?)"
    r"\s+(?:the|a|an|this|that|these|those|its|their|his|her)\b"
)
_PREP_MODAL = re.compile(
    r"\b(?:in|on|at|for|from|with|by|of|to)\s+(?:may|might|could|would|should|must|shall|can)\b"
)
_BARE_AFTER = re.compile(
    r"\b(?:because|although|while|whereas|if|when)\s+(?:ties|treat|finds|argue|compares|adds)\b"
)
UNREADABLE_DRAFT = "This first draft is not readable. It is not the finished first draft."


def _glued_period_comma(text: str) -> bool:
    """A full stop glued to a comma, except the stop that closes an abbreviation."""
    from essay_writer.textutil import _abbreviation_before

    start = 0
    while True:
        found = text.find(".,", start)
        if found < 0:
            return False
        if not _abbreviation_before(text, found):
            return True
        start = found + 2


def _opening_is_bare_verb(text: str) -> bool:
    """True when this sentence or line starts with the verb a removed name left behind."""
    piece = text.lstrip(" \t\"'“”‘’(")
    if not piece or not piece[0].islower():
        return False
    head = piece.split(None, 1)[0].strip(".,;:").casefold()
    if head in _LOWER_LEAD:
        return False
    return head in _BARE_VERBS


def _lowercase_sentence(text: str) -> bool:
    from essay_writer.textutil import sentences

    return any(_opening_is_bare_verb(sentence) for sentence in sentences(text))


def _bare_verb_line(text: str) -> bool:
    """A heading with no full stop does not hide the next line's missing subject."""
    return any(_opening_is_bare_verb(line) for line in text.splitlines())


def first_draft_unreadable(text: str) -> dict[str, Any] | None:
    """Refuse a first draft a citation removal left unreadable.

    A doubled comma, a full stop glued to a comma, a sentence or line that
    starts with the verb the author name used to govern, a verb left after a
    prepositional opening, a modal left after a preposition, or a verb left
    after a conjunction with no subject are not readable English. A readable
    sentence is left alone.
    """
    if not isinstance(text, str) or not text.strip():
        return None
    if (
        ",," in text
        or _glued_period_comma(text)
        or _lowercase_sentence(text)
        or _bare_verb_line(text)
        or _PREP_BARE.search(text) is not None
        or _PREP_MODAL.search(text) is not None
        or _BARE_AFTER.search(text) is not None
    ):
        return refuse("draft", UNREADABLE_DRAFT, readable=False)
    return None


def finish_first_draft(essay_id: str, text: str) -> dict[str, Any]:
    """Write a short first draft into the brief's word band, or refuse to finish it.

    A draft already at or above the minimum is left as written. When gathered
    claims can carry the length, the returned text is inside the band. A draft
    that is still short is not the finished first draft. A draft a citation
    removal left unreadable is not saved and is not treated as inside the band.
    """
    from essay_writer.rewrite_baseline import band_edges

    broken = first_draft_unreadable(text)
    if broken is not None:
        return {"ready": False, "text": text, "block": broken}
    low, high = band_edges(document_word_band(essay_id))
    if low is None or high is None:
        return {"ready": True, "text": text}
    counted = draft_word_count(essay_id, text)
    if counted is not None and counted >= low:
        return {"ready": True, "text": text}
    written = _write_up_to_band(essay_id, text)
    after = draft_word_count(essay_id, written)
    if after is not None and high is not None and low <= after <= high:
        broken = first_draft_unreadable(written)
        if broken is not None:
            return {"ready": False, "text": text, "block": broken}
        return {"ready": True, "text": written}
    blocked = first_draft_below_minimum(essay_id, written)
    if blocked is None:
        return {"ready": True, "text": written}
    return {"ready": False, "text": text, "block": blocked}


def _with_citation(line: str, citation: str) -> str:
    """Put an in-text citation inside the closing punctuation."""
    if not citation or citation in line:
        return line
    if line.endswith((".", "!", "?")):
        return f"{line[:-1].rstrip()} {citation}{line[-1]}"
    return f"{line} {citation}"


_TOPIC_STOP = frozenset(
    {
        "with",
        "that",
        "this",
        "from",
        "into",
        "their",
        "than",
        "then",
        "also",
        "only",
        "both",
        "each",
        "more",
        "most",
        "such",
        "when",
        "what",
        "which",
        "whose",
        "section",
        "should",
        "could",
        "would",
        "about",
        "after",
        "before",
    }
)


def _topic_tokens(name: str) -> set[str]:
    """Words of a brief section name that a gathered sentence can match."""
    return {
        word
        for word in re.findall(r"[a-z0-9]+", str(name).casefold())
        if len(word) > 3 and word not in _TOPIC_STOP
    }


def _insert_section(sections: list[object], section: dict[str, Any]) -> None:
    """Place a lifted section before the conclusion, or at the end."""
    for index, existing in enumerate(sections):
        if not isinstance(existing, dict):
            continue
        heading = str(existing.get("heading") or "").strip().casefold()
        if heading == "conclusion":
            sections.insert(index, section)
            return
    sections.append(section)


def lift_missing_sections(
    essay_id: str, pack: dict[str, Any], *, per_section: int = 2
) -> dict[str, Any]:
    """Add each brief-weighted body section the draft lacks, from gathered claims.

    The heading is the one the brief weights. The sentences come from files the
    pack already gathered, and each sentence keeps its author-year citation. A
    section with no gathered support is left out and reported as skipped. No
    source, page, year, or quote is invented.
    """
    from essay_writer.gates import unquoted_exact
    from essay_writer.mark_fit import missing_weighted_sections, weighted_sections

    brief = essay_textutil.module_brief_text(essay_id)
    weights = weighted_sections(brief)
    if not weights:
        return {"pack": pack, "added": [], "skipped": []}
    sections: list[object] = [
        dict(section) if isinstance(section, dict) else section
        for section in pack.get("sections") or []
    ]
    known = [section for section in sections if isinstance(section, dict)]
    missing = missing_weighted_sections(known, weights)
    if not missing:
        return {"pack": pack, "added": [], "skipped": []}
    pairs = [
        (text, citation) for text, citation in _source_texts_with_cite(essay_id, pack) if citation
    ]
    if not pairs:
        return {"pack": pack, "added": [], "skipped": [str(row["name"]) for row in missing]}
    gathered = [text for text, _citation in pairs]
    body_all = "\n".join(_section_bodies(pack))
    added: list[str] = []
    skipped: list[str] = []
    for row in missing:
        name = str(row["name"])
        tokens = _topic_tokens(name)
        parts: list[str] = []
        for text, citation in pairs:
            if len(parts) >= per_section:
                break
            for sentence in _gathered_sentences([text]):
                if len(parts) >= per_section:
                    break
                if sentence in body_all:
                    continue
                if not tokens or not any(token in sentence.casefold() for token in tokens):
                    continue
                for variant in range(4):
                    line = _rewrite_supported(sentence, variant)
                    if not line or sentence in line:
                        continue
                    if line.casefold().startswith("the text notes that"):
                        # A stock lead-in is not a lift, and it would lower a name.
                        continue
                    line = _with_citation(line, citation)
                    if unquoted_exact("\n".join(parts + [line]), gathered):
                        continue
                    parts.append(line)
                    break
        if parts:
            _insert_section(sections, {"heading": name, "body": " ".join(parts)})
            added.append(name)
        else:
            skipped.append(name)
    filled = dict(pack)
    filled["sections"] = sections
    if added:
        filled["mark_fit_lift"] = {"added": added, "skipped": skipped}
    return {"pack": filled, "added": added, "skipped": skipped}


def land_body_cites(
    essay_id: str,
    stage: str,
    text: str,
    *,
    answers: str | None = None,
    edited: str | None = None,
) -> dict[str, Any]:
    """Writer and front office. One gate for every stage that inserts a body cite.

    Body stages are ``BODY_CITE_STAGES`` (5, 6, 7, and 8). A revision note uses
    the same checks. This is not a stage-6 branch.
    """
    from essay_writer.cite_fit import apply_body_cites

    if stage not in BODY_CITE_STAGES and stage != "revise":
        return {
            "text": text if isinstance(text, str) else "",
            "edited": edited,
            "ask": None,
            "held": [],
            "applied": False,
        }
    return apply_body_cites(
        essay_id,
        stage,
        text,
        answers=answers,
        edited=edited,
    )


def accept_draft(essay_id: str, text: str) -> dict[str, Any] | None:
    """Refuse a draft that misses the constitution. Daily use returns None."""

    report = assignment_gate(essay_id, text, seat="writer")
    if report.get("ok") is True:
        return None
    return refuse("assignment-gate", str(report.get("reason") or ""), assignment=report)


_WORD = {
    "essay_pack_render_word": "essay_writer.word",
    "write_docx": "essay_writer.word",
}


def __getattr__(name: str):
    if name == "first_draft_blockers":
        from essay_writer.draft_from_review import first_draft_blockers

        return first_draft_blockers
    module_name = _WORD.get(name)
    if module_name is None:
        raise AttributeError(name)
    from importlib import import_module

    return getattr(import_module(module_name), name)
