"""Brief weight-table fit for a report draft. Notes only, never a block.

The brief may list section weights in a table or on their own line. A draft
that misses a weighted section, or that carries a heading the brief does not
weight, gets a note. The weights and section names come from the brief text;
nothing is invented, and no new pass or fail is added.
"""

from __future__ import annotations

import re
from typing import Any

from essay_writer import assignment_gate as essay_assignment_gate
from essay_writer import textutil as essay_textutil
from essay_writer.textutil import genre_from_brief_text

_TABLE_ROW = re.compile(r"^\s*\|(.+)\|\s*$")
_PERCENT = re.compile(r"(\d{1,3})\s*%")
_PLAIN_WEIGHT = re.compile(
    r"^\s*(?:[-*]\s*)?(?P<name>[A-Za-z][^|%]{2,64}?)\s*(?:—|-|:)?\s*(?P<pct>\d{1,3})\s*%\s*$"
)
_HEADER_WORDS = frozenset(
    {"section", "sections", "part", "parts", "criterion", "criteria", "weight", "weights", "mark", "marks"}
)
# A weight row that is not a body section a draft can carry.
_NON_BODY = ("presentation", "referencing", "references", "bibliography", "overall", "total")
_STOP = frozenset(
    {"the", "and", "for", "with", "into", "from", "that", "this", "its", "their", "of", "to", "in", "on", "or", "a", "an"}
)
_CHAIN_ASK = re.compile(r"(?i)named\s+(?:supply\s+)?chain|one\s+named\s+chain")
_CHAIN_LIST = re.compile(r"(?i)(?:allow-?list(?:\s+is)?|such as|e\.g\.|for example)\s*:?\s*")
_CHAIN_PHRASE = re.compile(r"(?i)\b(?:supply\s+chains?|chains?)\b")
_CHAIN_NAME = re.compile(r"\b([A-Z][A-Za-z'’.-]{1,}(?:\s+[A-Z][A-Za-z'’.-]{1,})?)\b")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_CASE_ASK = re.compile(r"(?i)\bnamed\s+(.+)$")
_NON_CASE_KINDS = frozenset({"supply chain", "supply chains", "chain", "chains"})
_CASE_KINDS = (
    "supply chain",
    "company",
    "organisation",
    "organization",
    "firm",
    "case",
    "jurisdiction",
    "country",
    "region",
    "institution",
    "brand",
    "city",
    "river",
    "industry",
    "sector",
    "market",
)
_SOURCE_ASK = re.compile(r"(?i)specialist\s+(?:industry\s+)?source")
_SOURCE_PAREN = re.compile(r"\(([^)]{3,200})\)")
_GENERIC_HEADS = frozenset(
    {"the", "this", "that", "these", "those", "a", "an", "one", "it", "its", "in", "on", "for", "when", "if", "and", "but", "however", "there", "each", "every", "our"}
)


def _norm(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(text).casefold()))


def _tokens(text: str) -> set[str]:
    return {word for word in _norm(text).split() if len(word) > 2 and word not in _STOP}


def weighted_sections(text: str) -> list[dict[str, Any]]:
    """Section names and weights the brief prints, in brief order.

    A markdown table row and a plain "Drivers 20%" line both count. A row with
    no percentage, a header row, and a percentage outside 1–100 are left out.
    Nothing is added when the brief prints no weight list.
    """
    if not isinstance(text, str) or not text.strip():
        return []
    found: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(name: str, pct: str | int) -> None:
        label = " ".join(str(name).split()).strip(" .:—-|")
        weight = int(pct)
        key = _norm(label)
        if not label or not key or key in seen or weight <= 0 or weight > 100:
            return
        seen.add(key)
        found.append({"name": label, "weight": weight})

    for line in text.splitlines():
        row = _TABLE_ROW.match(line)
        if row:
            cells = [cell.strip() for cell in row.group(1).split("|")]
            if len(cells) < 2:
                continue
            name = cells[0]
            if name.casefold() in _HEADER_WORDS or set(name) <= {"-", ":", " "}:
                continue
            percent = _PERCENT.search(" ".join(cells[1:]))
            if percent:
                add(name, percent.group(1))
            continue
        plain = _PLAIN_WEIGHT.match(line)
        if plain:
            name = plain.group("name")
            if name.casefold() not in _HEADER_WORDS:
                add(name, plain.group("pct"))
    return found


def _is_body_section(name: str) -> bool:
    folded = _norm(name)
    return not (folded and folded.startswith(_NON_BODY))


def _matches_weight(heading: str, name: str) -> bool:
    """True when a draft heading is the weighted section the brief names."""
    folded_heading = _norm(heading)
    folded_name = _norm(name)
    if not folded_heading or not folded_name:
        return False
    if folded_heading == folded_name or folded_name in folded_heading:
        return True
    heading_tokens = _tokens(heading)
    name_tokens = _tokens(name)
    if not name_tokens:
        return False
    return len(heading_tokens & name_tokens) / len(name_tokens) >= 0.7


def missing_weighted_sections(
    sections: list[dict[str, Any]], weights: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Body sections the brief weights that the draft heading list does not carry."""
    headings = [
        str(section.get("heading") or "")
        for section in sections
        if isinstance(section, dict)
    ]
    missing: list[dict[str, Any]] = []
    for row in weights:
        if not _is_body_section(str(row.get("name") or "")):
            continue
        if any(_matches_weight(heading, str(row["name"])) for heading in headings):
            continue
        missing.append(row)
    return missing


def unweighted_headings(
    sections: list[dict[str, Any]], weights: list[dict[str, Any]]
) -> list[str]:
    """Draft headings that are not a weighted section and not a reference part."""
    if not weights:
        return []
    found: list[str] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        heading = " ".join(str(section.get("heading") or "").split())
        if not heading:
            continue
        folded = _norm(heading)
        if folded.startswith(("reference", "bibliography", "appendix", "appendices")):
            continue
        if any(_matches_weight(heading, str(row["name"])) for row in weights):
            continue
        if heading not in found:
            found.append(heading)
    return found


def allow_list(brief: str) -> list[str]:
    """Names the brief offers in its list sentence, whenever it names one."""
    if not isinstance(brief, str) or not brief.strip():
        return []
    for sentence in _SENTENCE.split(brief):
        cue = _CHAIN_LIST.search(sentence)
        if cue is None:
            continue
        names: list[str] = []
        for piece in re.split(r"[/,;]|\bor\b|\band\b", sentence[cue.end() :]):
            name = " ".join(piece.split()).strip(" .:—-")
            name = re.sub(r"(?i)^(?:a|an|the)\s+", "", name)
            if not name or len(name) > 40:
                continue
            if "comparable" in name.casefold() or name.casefold() in {"chain you name", "you name"}:
                continue
            if name not in names:
                names.append(name)
        if names:
            return names
    return []


def chain_allow_list(brief: str) -> list[str]:
    """Supply-chain names the brief offers, from the list sentence."""
    if not isinstance(brief, str) or _CHAIN_ASK.search(brief) is None:
        return []
    return allow_list(brief)


def named_case_kind(brief: str) -> str | None:
    """The kind of named thing the brief asks for, such as a case or a company."""
    if not isinstance(brief, str) or not brief.strip():
        return None
    for sentence in _SENTENCE.split(brief):
        match = _CASE_ASK.search(sentence)
        if match is None:
            continue
        rest = " ".join(match.group(1).split()).strip(" .:—-").casefold()
        if not rest:
            continue
        for kind in _CASE_KINDS:
            if rest == kind or rest.startswith(f"{kind} "):
                if kind in _NON_CASE_KINDS:
                    return None
                return kind
        words = rest.split()
        return " ".join(words[:2])
    return None


def generic_case_note(sections: list[dict[str, Any]], brief: str) -> str | None:
    """A note when the brief names a case or organisation and the draft names none."""
    kind = named_case_kind(brief)
    if not kind:
        return None
    names = allow_list(brief)
    if not names:
        return None
    body = "\n".join(
        str(section.get("body") or "") for section in sections if isinstance(section, dict)
    )
    if any(name.casefold() in body.casefold() for name in names):
        return None
    shown = ", ".join(names)
    return (
        f"The brief asks for one named {kind}. The draft does not name one. "
        f"Name the {kind} the draft follows, from the brief's list ({shown}), "
        "or name the agreed alternative."
    )


def _chain_is_named(body: str, names: list[str]) -> bool:
    folded = body.casefold()
    if any(name.casefold() in folded for name in names):
        return True
    for sentence in _SENTENCE.split(body):
        if _CHAIN_PHRASE.search(sentence) is None:
            continue
        head = sentence.lstrip()
        first = re.match(r"[A-Za-z'’.-]+", head)
        first_word = first.group(0).casefold() if first else ""
        for name in _CHAIN_NAME.findall(sentence):
            if name.casefold() in _GENERIC_HEADS or name.casefold() == first_word:
                continue
            return True
    return False


def generic_chain_note(sections: list[dict[str, Any]], brief: str) -> str | None:
    """A note when the brief asks for one named chain and the draft names none."""
    names = chain_allow_list(brief)
    if not names:
        return None
    body = "\n".join(
        str(section.get("body") or "") for section in sections if isinstance(section, dict)
    )
    if not body.strip() or _CHAIN_PHRASE.search(body) is None:
        return None
    if _chain_is_named(body, names):
        return None
    shown = ", ".join(names)
    return (
        "The brief asks for one named supply chain. The draft talks about a supply chain "
        f"without naming one. Name the chain the draft follows, from the brief's list ({shown}), "
        "or name the agreed alternative."
    )


def specialist_source_classes(brief: str) -> list[str]:
    """Source classes the brief names after its specialist-source ask."""
    if not isinstance(brief, str) or not brief.strip():
        return []
    for sentence in _SENTENCE.split(brief):
        if _SOURCE_ASK.search(sentence) is None:
            continue
        listed = _SOURCE_PAREN.search(sentence)
        if listed is None:
            return []
        classes: list[str] = []
        for piece in re.split(r",|;|\bor\b|\band\b", listed.group(1)):
            name = " ".join(piece.split()).strip(" .:—-")
            if not name or len(name) > 40 or name.casefold() in {"etc", "and so on"}:
                continue
            if name not in classes:
                classes.append(name)
        return classes
    return []


def _mentions(haystack: str, name: str) -> bool:
    if len(name) <= 3:
        return re.search(rf"(?<![A-Za-z]){re.escape(name)}(?![A-Za-z])", haystack, re.IGNORECASE) is not None
    return name.casefold() in haystack.casefold()


def specialist_source_note(
    brief: str, sources: list[dict[str, Any]], sections: list[dict[str, Any]]
) -> str | None:
    """A note when the brief names a specialist source class the draft does not use."""
    classes = specialist_source_classes(brief)
    if not classes:
        return None
    parts: list[str] = []
    for source in sources or []:
        if not isinstance(source, dict):
            continue
        for key in ("title", "author", "container", "publisher", "url", "locator", "annotation"):
            value = source.get(key)
            if isinstance(value, str):
                parts.append(value)
    for section in sections or []:
        if isinstance(section, dict) and isinstance(section.get("body"), str):
            parts.append(section["body"])
    haystack = "\n".join(parts)
    if not haystack.strip():
        return None
    if any(_mentions(haystack, name) for name in classes):
        return None
    return (
        "The brief asks for at least one specialist industry source ("
        + ", ".join(classes)
        + "). The draft's sources do not name any of them. Add one, or say why the source set cannot."
    )


def mark_fit_notes(
    essay_id: str,
    sections: list[dict[str, Any]],
    sources: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    """Notes about how the draft fits the brief's weight table. Never a block."""

    brief = essay_textutil.module_brief_text(essay_id)
    genre = (genre_from_brief_text(brief) or "").casefold()
    if genre in {"reflective", "reflective diary", "diary"} or "reflective diary" in brief.casefold():
        # A diary keeps its own entry parts. The weight table is not its shape.
        return []
    weights = weighted_sections(brief)
    notes: list[dict[str, str]] = []
    for row in missing_weighted_sections(sections, weights):
        notes.append(
            {
                "code": "mark-fit-section",
                "reason": (
                    f"The brief weights {row['name']} at {row['weight']}%, and the draft has no "
                    "section with that heading. Add the section, or say which weighted section it serves."
                ),
            }
        )
    chain = generic_chain_note(sections, brief)
    if chain:
        notes.append({"code": "mark-fit-chain", "reason": chain})
    case = generic_case_note(sections, brief)
    if case:
        notes.append({"code": "mark-fit-case", "reason": case})
    specialist = specialist_source_note(brief, list(sources or []), sections)
    if specialist:
        notes.append({"code": "mark-fit-source", "reason": specialist})
    weighted = ", ".join(str(row["name"]) for row in weights if _is_body_section(str(row["name"])))
    for heading in unweighted_headings(sections, weights):
        notes.append(
            {
                "code": "mark-fit-heading",
                "reason": (
                    f"The brief weights these sections: {weighted}. This heading is not one of "
                    f"them: {heading}. Use a weighted section name, or say which one it serves."
                ),
            }
        )
    return notes


def _default_specialist_search(query: str) -> dict[str, Any]:
    """The one live look-up. Consensus is the service the search already uses."""
    from essay_writer.dig import consensus_search

    return consensus_search(query)


def specialist_lookup_query(essay_id: str, classes: list[str]) -> str:
    """One plain query: the source class, then the assignment question."""

    question = essay_assignment_gate.read_assignment(essay_id).get("question")
    words = question.strip() if isinstance(question, str) else ""
    head = classes[0] if classes else ""
    return " ".join(part for part in (head, words) if part).strip()[:200]


def final_specialist_lookup(
    essay_id: str,
    pack: dict[str, Any],
    *,
    identity: str = "",
    state: dict[str, Any] | None = None,
    search: Any = None,
) -> dict[str, Any]:
    """At most one live look-up for a missing specialist source class.

    The lookup runs only when the brief names a class and the pack does not
    already name one. A hit is reported, never added: no source, reference
    line, or claim is invented. One attempt is kept per pack identity, so
    showing the same preview twice does not search twice.
    """

    brief = essay_textutil.module_brief_text(essay_id)
    classes = specialist_source_classes(brief)
    if not classes:
        return {"attempted": False, "reason": "no-class", "note": ""}
    sources = [s for s in pack.get("sources") or [] if isinstance(s, dict)]
    sections = [s for s in pack.get("sections") or [] if isinstance(s, dict)]
    if specialist_source_note(brief, sources, sections) is None:
        return {"attempted": False, "reason": "present", "note": ""}

    if isinstance(state, dict) and identity:
        previous = state.get("specialist_lookup")
        if isinstance(previous, dict) and previous.get("pack_digest") == identity:
            kept = previous.get("result")
            if isinstance(kept, dict):
                reused = dict(kept)
                reused["reused"] = True
                return reused

    query = specialist_lookup_query(essay_id, classes)
    lookup = search or _default_specialist_search
    try:
        result = lookup(query)
    except Exception:  # a look-up never blocks the Word save
        result = {"called": False, "hits": [], "error": "lookup-failed"}
    if not isinstance(result, dict):
        result = {"called": False, "hits": [], "error": "lookup-failed"}
    hits = [
        hit
        for hit in (result.get("hits") or [])
        if isinstance(hit, dict) and str(hit.get("title") or "").strip()
    ]
    candidate = hits[0] if hits else None
    shown = ", ".join(classes)
    if candidate is not None:
        title = " ".join(str(candidate.get("title") or "").split())
        year = str(candidate.get("year") or "").strip()
        doi = str(candidate.get("doi") or "").strip()
        where = f" doi:{doi}" if doi else ""
        note = (
            f"The brief asks for one specialist industry source ({shown}). One live look-up "
            f"found a possible source: {title}"
            + (f" ({year})" if year else "")
            + f".{where} Nothing was added and no reference line was invented. "
            "Add it to the sources if it is the class the brief wants."
        )
    else:
        why = ""
        if result.get("skipped"):
            why = f" The look-up could not run ({result['skipped']})."
        elif result.get("remind"):
            why = f" The look-up could not run: {result['remind']}"
        note = (
            f"The brief asks for one specialist industry source ({shown}). The gathered files "
            f"do not name one, and one live look-up found none.{why} "
            "Add one, or say why the source set cannot. No source was invented."
        )
    attempt = {
        "attempted": True,
        "reason": "missing",
        "classes": classes,
        "query": query,
        "called": bool(result.get("called")),
        "found": candidate is not None,
        "candidate": (
            {
                "title": str(candidate.get("title") or ""),
                "year": str(candidate.get("year") or ""),
                "doi": str(candidate.get("doi") or ""),
            }
            if candidate is not None
            else None
        ),
        "note": note,
        "reused": False,
    }
    if isinstance(state, dict) and identity:
        state["specialist_lookup"] = {"pack_digest": identity, "result": attempt}
    return attempt
