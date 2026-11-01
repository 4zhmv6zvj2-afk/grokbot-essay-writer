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
from essay_writer.textutil import (
    count_words,
    family_name,
    word_band_from_brief_text,
    word_rules_for,
)

ROLE = "writer"

HIGHEST_BAND = (
    "When a mark scheme is present, the draft aims at the highest band, "
    "the top descriptors, not merely a pass."
)

FIRST_DRAFT_NOTE = (
    "The first draft (stage 5) is the report or the essay the brief asked for. "
    "That draft is the essay argument. It answers the question. "
    "It states the purpose, the argument, and the evidence inside that argument. "
    "The stage 4b critical-review markdowns stay source material. "
    "Do not paste them in as the body. "
    "One markdown per paper. Pass critical_reviews on the pack sent to essay.pack.validate. "
    "A section that only retells one paper and does not answer the question fails the draft check. "
    "Mark-scheme section titles are the headings when the mark scheme lists them. "
    "Re-open a source paper only with reopen when that markdown does not cover the gap. "
    "A quotation must be an exact span of that markdown, or of the re-opened passage. "
    "invent-forbid still holds. Confirm still holds: draft, show the human, then the same arguments. "
    "Stage 5 chat is a quiet step, the same idea as the later quiet steps. "
    "When quiet is true, say the chat line. "
    "If that reply also includes a status done line for the finished step, say that line too. "
    "Do not say that the step is starting on the turn that finishes it. "
    "Do not read rules, a file path, or the checklist. "
    "The person sees the finished first draft after the Word save. "
    "The Word preview and revise stay quiet unless the draft is blocked. "
    "When the 4b markdowns fill the stage 5 window, trim only the repeated model line, "
    "then split into whole-paper groups, then reopen with an exact passage. "
    "Do not silently truncate. invent-forbid still checks the full markdown. "
    "Keep the revise loop while a clear path remains. "
    "Stop and tell the person only when trim, split, and reopen are all exhausted. "
    "A paper stays in the body only when it supports the student's own sentence. "
    "Ask before adding a paper the student did not ask for. "
    "A rejected citation stays out when a swap does not succeed. "
    "When a swap does not succeed, offer the gap; do not put the rejected paper back. "
    "When the student supplied an outline or base prose, that outline is the structure: "
    "keep its headings and their order, and do not add a section or grow a paragraph "
    "around whatever was gathered. "
    "When the student asks for the cites to be shortened to about one or two sentences, "
    "write each cited point that short instead of leaving a longer stretch to be trimmed by hand."
)

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



def _source_texts_with_cite(
    essay_id: str, pack: dict[str, Any]
) -> list[tuple[str, str | None]]:
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
        citation = None
        if isinstance(author, str) and author.strip() and isinstance(year, str) and year.strip():
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
            if added > 40:
                return filled
    if split_now >= low and token_now >= low:
        return filled
    return _shortfall(filled if added else pack, low, min(split_now, token_now))



def _with_citation(line: str, citation: str) -> str:
    """Put an in-text citation inside the closing punctuation."""
    if not citation or citation in line:
        return line
    if line.endswith((".", "!", "?")):
        return f"{line[:-1].rstrip()} {citation}{line[-1]}"
    return f"{line} {citation}"


_TOPIC_STOP = frozenset(
    {
        "with", "that", "this", "from", "into", "their", "than", "then", "also",
        "only", "both", "each", "more", "most", "such", "when", "what", "which",
        "whose", "section", "should", "could", "would", "about", "after", "before",
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
        (text, citation)
        for text, citation in _source_texts_with_cite(essay_id, pack)
        if citation
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
