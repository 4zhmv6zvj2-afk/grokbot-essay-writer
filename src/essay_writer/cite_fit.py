"""Shared body-cite gate for the writer and the front office.

A paper stays in the body only when its gathered text supports the
student's own sentence: the same idea, not a shared topic. A paper the
student did not ask for is asked about before it is pasted. A cite the
student rejected stays out when a swap does not succeed, and it stays out
for every later save too: a snapshot restore, a draft overwrite, or a Word
re-land does not put that paper back. The student is offered the gap instead.

Stages 5, 6, 7, and 8, and a revision note, use this one function.
The decision does not branch on stage 6. Stage 4a, stage 4b, and stage 9
do not gain a new door here. Word still omits a cite this gate withheld,
so a later file cannot put that cite back into the body or the reference list.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from essay_writer import assignment_gate as essay_assignment_gate
from essay_writer.known_paths import refuse_repo_write
from essay_writer.paths import work_dir
from essay_writer.state import load_state
from essay_writer.textutil import (
    NARRATIVE,
    PAREN,
    citation_tokens,
    family_name,
    in_text_forms,
    norm_space,
    token_allowed,
)

BODY_CITE_STAGES = frozenset({"5", "6", "7", "8"})
_ACTIVE = BODY_CITE_STAGES | {"revise"}
_BODY_ORDER = ("5", "6", "7", "8")
_STUDENT_STAGES = ("1", "2", "3", "4")

_STOP = frozenset(
    {
        "a",
        "about",
        "after",
        "also",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "because",
        "been",
        "being",
        "between",
        "but",
        "by",
        "could",
        "for",
        "from",
        "has",
        "have",
        "into",
        "its",
        "not",
        "of",
        "on",
        "only",
        "or",
        "over",
        "should",
        "such",
        "than",
        "that",
        "the",
        "their",
        "them",
        "then",
        "these",
        "they",
        "this",
        "those",
        "through",
        "to",
        "under",
        "was",
        "were",
        "when",
        "where",
        "which",
        "while",
        "with",
        "would",
        "your",
    }
)

_ADD = re.compile(
    r"(?i)\b(?:yes[, ]+)?(?:please[, ]+)?(?:add|use|include|keep)\s+([A-Z][A-Za-z'’\-]+)"
)
_DROP = re.compile(
    r"(?i)\b(?:do not use|don't use|do not add|don't add|do not include|don't include|"
    r"do not keep|don't keep|drop|remove|reject|leave out)\s+([A-Z][A-Za-z'’\-]+)"
)
_SWAP = re.compile(
    r"(?i)\b(?:swap|replace)\s+([A-Z][A-Za-z'’\-]+)\s+(?:for|with)\s+([A-Z][A-Za-z'’\-]+)"
)
_WORD = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)?")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def _blank() -> dict[str, Any]:
    return {"ok": [], "rejected": [], "withheld": []}


def _record_path(essay_id: str):

    return work_dir(essay_id) / "cite-fit.json"


def load_record(essay_id: str) -> dict[str, Any]:
    """Surnames the student allowed or rejected, and cites withheld from Word."""
    path = _record_path(essay_id)
    record = _blank()
    if not path.is_file():
        return record
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return record
    if not isinstance(data, dict):
        return record
    for key in ("ok", "rejected", "withheld"):
        raw = data.get(key)
        if isinstance(raw, list):
            record[key] = [item.strip().casefold() for item in raw if isinstance(item, str) and item.strip()]
    return record


def _write_record(essay_id: str, record: dict[str, Any]) -> None:

    path = _record_path(essay_id)
    refuse_repo_write(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _names(pattern: re.Pattern[str], text: str) -> set[str]:
    if not text:
        return set()
    return {match.group(1).casefold() for match in pattern.finditer(text)}


def _swap_old(text: str) -> set[str]:
    if not text:
        return set()
    return {match.group(1).casefold() for match in _SWAP.finditer(text)}


def _added_names(text: str) -> set[str]:
    """Surnames the student asked to add. A negated ask is a drop, not an add.

    "Do not use Beldad" carries the same verb as "use Beldad". Reading the
    first as a yes would put back the paper the student just rejected.
    """
    return _names(_ADD, text) - _names(_DROP, text)


def _content_words(text: str) -> list[str]:
    return [word for word in _WORD.findall(text.casefold()) if len(word) > 3 and word not in _STOP]


def _bare(text: str) -> str:

    cleaned = PAREN.sub(" ", text)
    cleaned = NARRATIVE.sub(" ", cleaned)
    return norm_space(cleaned)


def _claim_words(sentence: str, topic: str = "") -> list[str]:
    """Content words of the student's sentence that are not the assignment topic."""
    topic_words = set(_content_words(topic))
    seen: set[str] = set()
    claim: list[str] = []
    for word in _content_words(_bare(sentence)):
        if word in topic_words or word in seen:
            continue
        seen.add(word)
        claim.append(word)
    return claim


def same_idea(sentence: str, excerpt: str, topic: str = "") -> bool:
    """True when the locked excerpt supports the sentence, not only its topic.

    The sentence does not have to repeat the excerpt word for word. Most of
    its claim words still have to be in the excerpt, and at least three of
    them. Overlap that is only the shared topic does not count. Fewer than
    three claim words is not an idea this gate can keep a paper for.
    """
    claim = _claim_words(sentence, topic)
    if len(claim) < 3:
        return False
    if not isinstance(excerpt, str) or not excerpt.strip():
        return False
    have = set(_content_words(excerpt))
    found = sum(1 for word in claim if word in have)
    need = max(3, len(claim) // 2 + 1)
    return found >= need


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE.split(text) if part.strip()]


def _topic(essay_id: str) -> str:

    record = essay_assignment_gate.read_assignment(essay_id)
    if record.get("active") is not True:
        return ""
    question = record.get("question")
    return question.strip() if isinstance(question, str) else ""


def _student_sentences(essay_id: str, answers: str) -> list[str]:
    from essay_writer.stage_track import _note_look

    chunks: list[str] = []
    for stage in _STUDENT_STAGES:
        look = _note_look(essay_id, stage)
        if isinstance(look, str) and look.strip():
            chunks.append(look)
    if answers.strip():
        chunks.append(answers)
    found: list[str] = []
    for chunk in chunks:
        for sentence in _sentences(chunk):
            if len(_claim_words(sentence)) >= 3:
                found.append(sentence)
    return found


def _prior_body(essay_id: str, stage: str) -> str:
    from essay_writer.stage_track import _note_look

    if stage in _BODY_ORDER:
        earlier = _BODY_ORDER[: _BODY_ORDER.index(stage)]
    else:
        earlier = _BODY_ORDER
    latest = ""
    for item in earlier:
        look = _note_look(essay_id, item)
        if isinstance(look, str) and look.strip():
            latest = look
    return latest


def _sources(essay_id: str) -> list[dict[str, Any]]:
    from essay_writer.validate import research_index

    allowed, _digests = research_index(load_state(essay_id))
    return [row for row in allowed.values() if isinstance(row, dict)]


def _excerpt(source: dict[str, Any]) -> str:
    quote = source.get("quote")
    if isinstance(quote, str) and quote.strip():
        return quote
    excerpt = source.get("excerpt")
    if isinstance(excerpt, str) and excerpt.strip():
        return excerpt
    from essay_writer.invent import load_text_for

    try:
        return load_text_for(source)
    except (KeyError, OSError, ValueError):
        return ""


def _source_for(token: str, sources: list[dict[str, Any]]) -> dict[str, Any] | None:

    for source in sources:
        author = source.get("author")
        year = source.get("year")
        if not author or year is None or year == "":
            continue
        forms = in_text_forms(str(author), str(year))
        if token_allowed(token, forms):
            return source
    return None


def _surname(token: str) -> str:
    return token.split(",", 1)[0].strip().casefold()


def rejected_names(record: dict[str, Any]) -> set[str]:
    """Surnames the student dropped. A reject outlives one body, one snapshot, one draft."""
    names: set[str] = set()
    for item in record.get("rejected") or []:
        if isinstance(item, str) and item.strip():
            names.add(item.strip().casefold())
    return names


def _sentence_with(text: str, token: str) -> str:

    for sentence in _sentences(text):
        if token in citation_tokens(sentence):
            return sentence
    return text


def _on_student_sentence(sentence: str, students: list[str], topic: str) -> str | None:
    bare_words = set(_content_words(_bare(sentence)))
    for student in students:
        claim = _claim_words(student, topic)
        if len(claim) < 3:
            continue
        if all(word in bare_words for word in claim):
            return student
    return None


def _label(token: str, text: str) -> str:
    name, _, year = token.partition(",")
    name = name.strip()
    year = year.strip()
    found = re.search(rf"\b({re.escape(name)})\b", text, flags=re.IGNORECASE)
    shown = found.group(1) if found else name
    return f"{shown} ({year})"


def strip_token(text: str, token: str) -> str:
    """Remove one author-year cite. The student's sentence stays."""

    if not isinstance(text, str) or not text or "," not in token:
        return text
    name, year = [part.strip() for part in token.split(",", 1)]
    if not name or not year:
        return text
    name_re = re.escape(name)
    year_re = re.escape(year)
    et_al = r"(?:\s+et\s+al\.?)?"
    page = r"(?:\s*,\s*(?:pp?\.\s*)?\d+(?:\s*[-–—]\s*\d+)?)?"
    piece_re = rf"{name_re}{et_al}\s*,\s*{year_re}{page}"

    def repl_paren(match: re.Match[str]) -> str:
        kept: list[str] = []
        for part in match.group(1).split(";"):
            piece = norm_space(part)
            if re.fullmatch(piece_re, piece, flags=re.IGNORECASE):
                continue
            kept.append(piece)
        if not kept:
            return ""
        return "(" + "; ".join(kept) + ")"

    cleaned = re.sub(r"\(([^)]*\d{4}[^)]*)\)", repl_paren, text)
    narrative = rf"\b{name_re}{et_al}\s*\(\s*{year_re}{page}\s*\)"
    cleaned = re.sub(narrative, "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r" +([,.;:!?])", r"\1", cleaned)
    return cleaned


def _asked_names(essay_id: str, answers: str, ok: set[str]) -> set[str]:
    from essay_writer.stage_track import _note_look

    names = set(ok)
    names |= _added_names(answers)
    for stage in _STUDENT_STAGES:
        look = _note_look(essay_id, stage)
        if not isinstance(look, str):
            continue
        names |= _added_names(look)
        for token in citation_tokens(look):
            names.add(_surname(token))
    return names


def _ask_sentence(labels: list[str]) -> str | None:
    if not labels:
        return None
    if len(labels) == 1:
        return f"Do you want {labels[0]} added? You did not ask for this paper."
    joined = ", ".join(labels[:-1]) + " and " + labels[-1]
    return f"Do you want these papers added? You did not ask for them: {joined}."


def _gate_text(
    text: str,
    *,
    prior: str,
    students: list[str],
    sources: list[dict[str, Any]],
    topic: str,
    asked: set[str],
    rejected: set[str],
    withheld: set[str],
) -> tuple[str, list[dict[str, str]], set[str]]:

    prior_tokens = set(citation_tokens(prior))
    held: list[dict[str, str]] = []
    seen: set[str] = set()
    for token in citation_tokens(text):
        if token in seen:
            continue
        seen.add(token)
        surname = _surname(token)
        if surname in rejected:
            withheld.add(token)
            held.append({"token": token, "reason": "rejected", "label": _label(token, text)})
            continue
        # A cite already in an earlier body is not a new insert, so it is not
        # asked about twice. A cite this gate withheld is not in that body for
        # that reason: a snapshot restore can still carry it, and that restored
        # copy does not clear the withhold.
        if token in prior_tokens and token not in withheld:
            continue
        source = _source_for(token, sources)
        excerpt = _excerpt(source) if source is not None else ""
        student = _on_student_sentence(_sentence_with(text, token), students, topic)
        if student is None or not same_idea(student, excerpt, topic):
            withheld.add(token)
            held.append({"token": token, "reason": "claim-fit", "label": _label(token, text)})
            continue
        if surname not in asked:
            withheld.add(token)
            held.append({"token": token, "reason": "ask", "label": _label(token, text)})
            continue
        withheld.discard(token)
    cleaned = text
    for item in held:
        cleaned = strip_token(cleaned, item["token"])
    for token in withheld:
        cleaned = strip_token(cleaned, token)
    return cleaned, held, withheld


def _passthrough(text: str, edited: str | None) -> dict[str, Any]:
    return {"text": text, "edited": edited, "ask": None, "held": [], "applied": False}


def apply_body_cites(
    essay_id: str,
    stage: str,
    text: str,
    *,
    answers: str | None = None,
    edited: str | None = None,
) -> dict[str, Any]:
    """Return the body that may be stored, plus any ask still waiting.

    ``applied`` is false for stages that do not insert a body cite, and when
    this text neither adds a cite nor records a student yes, drop, or swap.
    """

    incoming = text if isinstance(text, str) else ""
    if stage not in _ACTIVE:
        return _passthrough(incoming, edited)
    answers_text = answers if isinstance(answers, str) else ""
    edited_text = edited if isinstance(edited, str) else None
    cites = bool(citation_tokens(incoming)) or bool(edited_text and citation_tokens(edited_text))
    intent = bool(
        _added_names(answers_text)
        or _names(_DROP, answers_text)
        or _swap_old(answers_text)
        or _names(_DROP, incoming)
        or _swap_old(incoming)
        or (edited_text and (_names(_DROP, edited_text) or _swap_old(edited_text)))
    )
    if not cites and not intent:
        record = load_record(essay_id)
        cleaned = incoming
        gated_edited = edited_text
        for token in record.get("withheld") or []:
            cleaned = strip_token(cleaned, token)
            if isinstance(gated_edited, str):
                gated_edited = strip_token(gated_edited, token)
        if cleaned != incoming or gated_edited != edited_text:
            return {
                "text": cleaned,
                "edited": gated_edited if edited_text is not None else edited,
                "ask": None,
                "held": [],
                "applied": True,
            }
        return _passthrough(incoming, edited)

    record = load_record(essay_id)
    ok = set(record["ok"]) | _added_names(answers_text)
    rejected = set(record["rejected"])
    rejected |= _names(_DROP, answers_text)
    rejected |= _names(_DROP, incoming)
    rejected |= _swap_old(answers_text)
    rejected |= _swap_old(incoming)
    if edited_text:
        rejected |= _names(_DROP, edited_text)
        rejected |= _swap_old(edited_text)
    for name in _added_names(answers_text):
        rejected.discard(name)
    asked = _asked_names(essay_id, answers_text, ok)
    topic = _topic(essay_id)
    students = _student_sentences(essay_id, answers_text)
    sources = _sources(essay_id)
    prior = _prior_body(essay_id, stage)
    withheld = set(record["withheld"])
    cleaned, held, withheld = _gate_text(
        incoming,
        prior=prior,
        students=students,
        sources=sources,
        topic=topic,
        asked=asked,
        rejected=rejected,
        withheld=withheld,
    )
    gated_edited = edited_text
    if edited_text is not None:
        gated_edited, edited_held, withheld = _gate_text(
            edited_text,
            prior=prior,
            students=students,
            sources=sources,
            topic=topic,
            asked=asked,
            rejected=rejected,
            withheld=withheld,
        )
        seen = {item["token"] for item in held}
        for item in edited_held:
            if item["token"] not in seen:
                held.append(item)
                seen.add(item["token"])
    labels: list[str] = []
    for item in held:
        if item["reason"] == "ask" and item["label"] not in labels:
            labels.append(item["label"])
    stored = {
        "ok": sorted(ok),
        "rejected": sorted(rejected),
        "withheld": sorted(withheld),
    }
    if stored["ok"] or stored["rejected"] or stored["withheld"]:
        _write_record(essay_id, stored)
    return {
        "text": cleaned,
        "edited": gated_edited if edited_text is not None else edited,
        "ask": _ask_sentence(labels),
        "gap": gap_ask(held),
        "held": held,
        "applied": True,
    }


def cited_pairs(text: str) -> list[str]:
    """Author-year pairs in the body, page locator and narrative et al. included."""
    from essay_writer.word_references import readable_cite_text

    return citation_tokens(readable_cite_text(text))


def strip_withheld(text: str, withheld: set[str], rejected: set[str]) -> str:
    """Remove every cite this essay withholds or whose author the student rejected."""
    cleaned = text
    for token in sorted(withheld):
        cleaned = strip_token(cleaned, token)
    if not rejected:
        return cleaned
    for token in cited_pairs(cleaned):
        if _surname(token) in rejected:
            cleaned = strip_token(cleaned, token)
    return cleaned


def withhold_body_cites(
    essay_id: str,
    sources: list[object],
    sections: list[object],
) -> tuple[list[object], list[object]]:
    """Drop cites the gate withheld from the Word body and the reference list.

    A withheld token and a rejected surname both count. Word is the last door
    before the file, so a body that a snapshot restore or a draft overwrite
    put back does not print a paper the student rejected.
    """

    record = load_record(essay_id)
    withheld = {
        str(token).strip().casefold()
        for token in record.get("withheld") or []
        if str(token).strip()
    }
    rejected = rejected_names(record)
    if not withheld and not rejected:
        return sources, sections
    cleaned_sections: list[object] = []
    for section in sections:
        if not isinstance(section, dict):
            cleaned_sections.append(section)
            continue
        row = dict(section)
        body = row.get("body")
        if isinstance(body, str):
            body = strip_withheld(body, withheld, rejected)
            row["body"] = body
        cleaned_sections.append(row)
    kept: list[object] = []
    for source in sources:
        if not isinstance(source, dict):
            kept.append(source)
            continue
        author = source.get("author")
        year = source.get("year")
        if author and year is not None and year != "":
            forms = in_text_forms(str(author), str(year))
            if any(token_allowed(token, forms) for token in withheld):
                continue
            if family_name(str(author)).casefold() in rejected:
                continue
        kept.append(source)
    return kept, cleaned_sections


def gap_ask(held: list[dict[str, str]]) -> str | None:
    """Say the gap out loud when a rejected cite was not replaced.

    A rejected paper stays out. When its replacement does not match the
    sentence, the point is left open and the student says what goes there.
    Nothing is put back and no paper is invented.
    """
    rejected = [item for item in held if item.get("reason") == "rejected"]
    failed = [item for item in held if item.get("reason") == "claim-fit"]
    if not rejected or not failed:
        return None
    gone = str(rejected[0].get("label") or "That paper")
    miss = str(failed[0].get("label") or "The replacement")
    return (
        f"{gone} stays out because you rejected it, and {miss} does not match "
        "the sentence it was swapped for. That point is left open: name a paper "
        "you want there, or keep the gap."
    )


def in_line(body: dict[str, Any], field: str) -> dict[str, Any]:
    text = body.get(field)
    if not isinstance(text, str) or not text.strip():
        return body
    for key in ("next", "chat"):
        current = body.get(key)
        if not isinstance(current, str) or not current.strip():
            body[key] = text
        elif text not in current:
            body[key] = f"{current.rstrip()} {text}"
    return body


def speak_cite_ask(body: dict[str, Any]) -> dict[str, Any]:
    """Keep the cite ask, the gap, and the cite length in the line the front office says."""
    return in_line(in_line(in_line(body, "cite_ask"), "cite_gap"), "cite_short_line")
