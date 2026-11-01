"""Citation tokens, word counts, and Harvard Referencing lines.

Lines contain only fields the caller already gathered or read from an opened
file. Missing pages, DOIs, and access dates are left out. The stage 9 line
is Harvard Referencing: heading References, Available at: doi:,
and an italic journal or report title.
"""

from __future__ import annotations

import re
from typing import Any

from essay_writer.paths import BRIEF_NAMES, essay_dir, module_code
from essay_writer.programme import MODULE_EXAMPLES
from essay_writer.state import load_state

# Word-count bands and citation counting from synthetic module briefs (`docs/samples-study.md`).
# Pack `word_rules` may override; unknown essay ids rely on the pack alone.
# Genre and default section shape from module briefs (`docs/academic-writing-helpers.md`).
BRIEF_GENRE: dict[str, dict[str, Any]] = {
    "MOD1004AA": {
        "genre": "report",
        "default_section_headings": [
            "Introduction",
            "Supply chain context",
            "Analysis and findings",
            "Conclusion",
        ],
    },
    "MOD1011AA": {"genre": "essay"},
    "MOD1008AA": {
        "genre": "report",
        "default_section_headings": [
            "Executive summary",
            "Introduction",
            "Market analysis",
            "Application of theory",
            "Strategic decisions",
            "Reflection",
        ],
    },
    "RPT1008AA": {"genre": "report"},
}

_ESSAY_ONLY_HEADINGS = frozenset({"introduction", "conclusion"})

BRIEF_WORD_RULES: dict[str, dict[str, Any]] = {
    "MOD1011AA": {
        "limit": 3000,
        "tolerance": 0.10,
        "exclude_in_text_citations": True,
    },
    "MOD1008AA": {
        "limit": 2000,
        "tolerance": 0.10,
        "exclude_in_text_citations": False,
    },
}

_GENRE_LINE = re.compile(r"(?im)^\s*genre\s*:\s*([a-z][a-z0-9_-]{0,40})\b")
_EMPHASIS = re.compile(r"[*_`]+")
_WORD_TOKEN = re.compile(r"(?i)words?")
_RANGE = re.compile(r"(\d[\d,]*)\s*(?:–|-|—|to)\s*(\d[\d,]*)")
_STATED_COUNT = re.compile(r"(?i)\b(\d[\d,]*)\s+words?\b")
_SECTION_NEAR = re.compile(
    r"(?i)\b(?:each|per|every)\s+(?:entry|section|part)\b|\bper[- ]entry\b|\beach entry\b"
)
_CITATIONS_COUNT = re.compile(r"(?i)in-text citations?\s+count")
_CITATIONS_EXCLUDE = re.compile(
    r"(?i)(?:exclud\w+|not count|do not count).{0,48}in-text citations?"
    r"|in-text citations?.{0,48}(?:exclud|not count|do not count)"
)


def _count_token(token: str) -> int:
    return int(token.replace(",", ""))


def module_brief_text(essay_id: str) -> str:
    """Text of the module brief file. Empty when the slot is empty."""
    from essay_writer.invent import read_gathered_text

    folder = essay_dir(essay_id)
    if not folder.is_dir():
        return ""
    chunks: list[str] = []
    for name in ("brief.md", "brief.txt", "brief.docx"):
        if name not in BRIEF_NAMES:
            continue
        path = folder / name
        if not path.is_file():
            continue
        try:
            chunks.append(read_gathered_text(path, essay_id))
        except (OSError, ValueError):
            continue
    return "\n".join(chunks)


def unmarked_labels(text: str) -> str:
    """Drop markdown emphasis so Genre, Format, and Question labels can be read.

    **Genre:** report and *Format:* essay are the same labels as the plain lines.
    The stored brief is unchanged.
    """
    if not isinstance(text, str) or not text:
        return ""
    return "\n".join(_EMPHASIS.sub("", line) for line in text.splitlines())


def genre_from_brief_text(text: str) -> str | None:
    """Genre the brief names. Nothing is guessed from the module code.

    A reflective diary of entries is chosen before a missing essay or report
    label is treated as no format. An explicit essay or report line still wins
    when the assignment is that kind of writing.
    """
    if not isinstance(text, str) or not text.strip():
        return None
    from essay_writer.diary import diary_signals

    if diary_signals(text):
        return "diary"
    match = _GENRE_LINE.search(unmarked_labels(text))
    if match is None:
        return None
    return match.group(1).casefold()


def _count_role(text: str, start: int, end: int) -> str:
    """Entry length is marked only in the same sentence as the count."""
    left = max(text.rfind("\n", 0, start), text.rfind(".", 0, start))
    window = text[left + 1 : end + 40]
    if _SECTION_NEAR.search(window):
        return "section"
    return "total"


def _matches_for(text: str, pattern: re.Pattern[str], role: str) -> list[re.Match[str]]:
    matches = list(pattern.finditer(text))
    sectionish = [match for match in matches if _count_role(text, match.start(), match.end()) == "section"]
    plain = [match for match in matches if _count_role(text, match.start(), match.end()) != "section"]
    if role == "section":
        return sectionish
    if sectionish and plain:
        return plain
    if sectionish:
        return []
    return matches


def _band_from_matches(
    text: str,
    word_matches: list[re.Match[str]],
    stated_matches: list[re.Match[str]],
) -> dict[str, Any]:
    """One band. A bare count uses the ten-percent band. A printed range wins."""
    rules: dict[str, Any] = {}
    low: int | None = None
    high: int | None = None
    for match in word_matches:
        window = text[max(0, match.start() - 80) : match.end() + 80]
        found = _RANGE.search(window)
        if found is None:
            continue
        left = _count_token(found.group(1))
        right = _count_token(found.group(2))
        if left > right:
            left, right = right, left
        if right <= left:
            continue
        low, high = left, right
        break
    stated: int | None = None
    if stated_matches:
        stated = _count_token(stated_matches[0].group(1))
    if low is None and stated is not None and stated > 0:
        low = round(stated * 0.9)
        high = round(stated * 1.1)
    if low is None or high is None:
        return rules
    rules["min"] = low
    rules["max"] = high
    if stated is not None and low <= stated <= high:
        rules["limit"] = stated
        rules["tolerance"] = round((high - stated) / stated, 4) if stated else 0.10
    else:
        rules["limit"] = (low + high) // 2
    return rules


def word_band_from_brief_text(text: str) -> dict[str, Any]:
    """Word band for the whole piece. An entry length stays on the entry.

    800 words is 720 to 880. An explicit range next to the word count wins.
    """
    if not isinstance(text, str) or not text.strip():
        return {}
    rules = _band_from_matches(
        text,
        _matches_for(text, _WORD_TOKEN, "total"),
        _matches_for(text, _STATED_COUNT, "total"),
    )
    if not rules:
        return rules
    if _CITATIONS_COUNT.search(text):
        rules["exclude_in_text_citations"] = False
    elif _CITATIONS_EXCLUDE.search(text):
        rules["exclude_in_text_citations"] = True
    return rules


def section_word_band(text: str) -> dict[str, Any]:
    """Length the brief gives each entry or section. Empty when it gives none."""
    if not isinstance(text, str) or not text.strip():
        return {}
    return _band_from_matches(
        text,
        _matches_for(text, _WORD_TOKEN, "section"),
        _matches_for(text, _STATED_COUNT, "section"),
    )


def brief_file_genre(essay_id: str) -> str | None:
    return genre_from_brief_text(module_brief_text(essay_id))


def brief_file_word_rules(essay_id: str) -> dict[str, Any]:
    return word_band_from_brief_text(module_brief_text(essay_id))


def genre_for(essay_id: str, pack: dict[str, Any]) -> dict[str, Any]:
    """Genre and optional section plan: requirement list, then pack fields."""
    from essay_writer.assignment_gate import (
        assignment_requirements,
        study_defaults_allowed,
    )

    essay_id = module_code(essay_id)
    info: dict[str, Any] = {}
    record = assignment_requirements(essay_id)
    if record.get("active") is True:
        prescribed = record.get("format")
        if prescribed == "reflective diary":
            info["genre"] = "diary"
        elif isinstance(prescribed, str) and prescribed.strip():
            info["genre"] = prescribed.strip().casefold()
    elif study_defaults_allowed(essay_id) and (
        essay_id in MODULE_EXAMPLES or essay_id in BRIEF_GENRE
    ):
        info.update(BRIEF_GENRE.get(essay_id, {}))
    if isinstance(pack.get("genre"), str) and pack["genre"].strip():
        info["genre"] = pack["genre"].strip().casefold()
    plan = pack.get("section_plan")
    if isinstance(plan, list):
        cleaned = [norm_space(str(item)) for item in plan if norm_space(str(item))]
        if cleaned:
            info["section_plan"] = cleaned
    return info


def check_genre(essay_id: str, pack: dict[str, Any], headings: list[str]) -> dict[str, str] | None:
    """Return a blocker when section headings contradict the brief genre."""
    info = genre_for(essay_id, pack)
    genre = info.get("genre")
    if not genre:
        return None
    clean = [norm_space(h) for h in headings if norm_space(h)]
    plan = info.get("section_plan")
    if plan:
        if clean != plan:
            return {
                "code": "genre",
                "reason": (
                    "Section headings do not match the brief section plan on this pack. "
                    "Use the headings gathered from the brief; the door does not rename sections."
                ),
            }
        return None
    if genre == "report":
        lowered = {h.casefold() for h in clean}
        if len(clean) == 2 and lowered <= _ESSAY_ONLY_HEADINGS:
            return {
                "code": "genre",
                "reason": (
                    f"{essay_id} is an individual report on the module brief. "
                    "Introduction and Conclusion alone are essay-shaped headings. "
                    "Add headed report sections from the brief (for example supply chain context, "
                    "analysis, and findings), or put the brief section plan on the pack."
                ),
            }
    return None


def word_rules_for(essay_id: str, pack: dict[str, Any]) -> dict[str, Any]:
    """Word-count rules. A mark scheme or brief band wins over a pack or studied default.

    When neither document states a band, studied defaults and the pack still apply.
    """
    from essay_writer.specialists.writer import document_word_band

    stated = document_word_band(essay_id)
    if stated:
        return dict(stated)
    from essay_writer.assignment_gate import study_defaults_allowed

    module = module_code(essay_id)
    base: dict[str, Any] = {}
    if study_defaults_allowed(essay_id) and (
        module in MODULE_EXAMPLES or module in BRIEF_WORD_RULES
    ):
        base.update(BRIEF_WORD_RULES.get(module, {}))
    override = pack.get("word_rules")
    if isinstance(override, dict):
        base.update(override)
    return base

YEAR = r"\d{4}[a-z]?"
PAREN = re.compile(r"\(([^)]*\d{4}[^)]*)\)")
# One narrative citation, including "A, B and C (2024)". Leading Both / In are not names.
# A sentence-initial transition (Similarly, and the same shape) is not an author.
NARRATIVE = re.compile(
    rf"\b([A-Z][A-Za-z'’\-]*(?:\s*,\s*[A-Z][A-Za-z'’\-]*)*(?:\s+[A-Z][A-Za-z'’\-]*)*(?:\s+and\s+[A-Z][A-Za-z'’\-]*)?)\s+\(({YEAR})\)"
)
_LEADING_NAME = frozenset({"both", "in"})
# Discourse words that open a sentence before the author. Not surnames.
# Stripped only when an author token remains, so "Similarly (2024)" stays a name.
_LEADING_TRANSITION = frozenset(
    {
        "accordingly",
        "additionally",
        "also",
        "alternatively",
        "and",
        "arguably",
        "but",
        "comparably",
        "consequently",
        "conversely",
        "correspondingly",
        "crucially",
        "equally",
        "finally",
        "furthermore",
        "generally",
        "hence",
        "however",
        "importantly",
        "incidentally",
        "indeed",
        "instead",
        "interestingly",
        "lastly",
        "likewise",
        "meanwhile",
        "moreover",
        "nevertheless",
        "next",
        "nonetheless",
        "notably",
        "often",
        "or",
        "otherwise",
        "overall",
        "previously",
        "recently",
        "relatedly",
        "similarly",
        "so",
        "specifically",
        "still",
        "subsequently",
        "then",
        "therefore",
        "thus",
        "usually",
        "yet",
    }
)
WORD = re.compile(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*")
ET_AL = re.compile(r"\s+et al\.", re.IGNORECASE)


def norm_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _narrative_name(raw: str) -> str:
    parts = raw.split()
    while len(parts) > 1 and parts[0].strip(",").casefold() in _LEADING_TRANSITION:
        parts = parts[1:]
    while parts and parts[0].strip(",").casefold() in _LEADING_NAME:
        parts = parts[1:]
    return " ".join(parts)


def _without_leading_transition(label: str) -> str:
    """Drop a leading Similarly-shaped word from an author-year label."""
    pieces = [norm_space(part) for part in label.split(",")]
    while len(pieces) > 2 and pieces[0].casefold() in _LEADING_TRANSITION:
        pieces = pieces[1:]
    return ", ".join(piece for piece in pieces if piece)


def citation_tokens(text: str) -> list[str]:
    found: list[str] = []
    for match in PAREN.finditer(text):
        inner = norm_space(match.group(1))
        if re.fullmatch(YEAR, inner):
            continue
        for part in match.group(1).split(";"):
            part = norm_space(part)
            if re.fullmatch(rf".+,\s*{YEAR}", part):
                found.append(_without_leading_transition(part).casefold())
    for match in NARRATIVE.finditer(text):
        name = _narrative_name(norm_space(match.group(1)))
        if not name:
            continue
        found.append(norm_space(f"{name}, {match.group(2)}").casefold())
    return found


def in_text_forms(author: str, year: str) -> set[str]:
    author = norm_space(author)
    year = norm_space(str(year))
    forms = {f"{author}, {year}".casefold()}
    if "," in author:
        forms.add(f"{norm_space(author.split(',', 1)[0])}, {year}".casefold())
    return forms


_BIBLIO_FILL = (
    "year",
    "title",
    "container",
    "volume",
    "issue",
    "pages",
    "doi",
    "url",
    "accessed",
    "publisher",
    "place",
    "edition",
    "article_number",
)
_REF_HEADINGS = frozenset({"references", "reference list", "bibliography"})
_BARE_PAREN = re.compile(r"\(([^()\d]{1,80})\)")
_NAME_ONLY = re.compile(
    r"[A-Z][A-Za-z'’\-]+(?:\s+(?:and|&)\s+[A-Z][A-Za-z'’\-]+|\s+[A-Z][A-Za-z'’\-]+)*"
)


def _field_text(value: object) -> str:
    if isinstance(value, bool) or value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return value.strip()
    return ""


def family_name(author: str) -> str:
    """Family name used in the text. Initials after a comma stay off this label."""
    return norm_space(author.split(",", 1)[0])


def bare_surname(author: str) -> bool:
    """True when the author slot is only a family name, with no initial and no year."""
    text = _field_text(author)
    if not text or "," in text or any(character.isdigit() for character in text):
        return False
    if re.search(r"\b[A-Z]\.", text):
        return False
    return _NAME_ONLY.fullmatch(text) is not None


def same_author(left: str, right: str) -> bool:
    """True when both labels name the same gathered author, including a surname stub."""
    left_text = _field_text(left)
    right_text = _field_text(right)
    if not left_text or not right_text:
        return False
    if left_text.casefold() == right_text.casefold():
        return True
    left_family = family_name(left_text).casefold()
    right_family = family_name(right_text).casefold()
    if left_family == right_family:
        return True
    if bare_surname(left_text) and left_text.casefold() == right_family.split()[-1].casefold():
        return True
    if bare_surname(right_text) and right_text.casefold() == left_family.split()[-1].casefold():
        return True
    return False


def _given_initials(author: str) -> tuple[str, ...]:
    """Initials after the comma in an author label. Empty when there is no comma."""
    _, comma, given = author.partition(",")
    if not comma:
        return ()
    return tuple(piece[0].upper() for piece in re.findall(r"[A-Za-z]+", given))


def same_author_initials(left: str, right: str) -> bool:
    """True when both labels name the same author, not only the same family name.

    A bare surname stub can still fill from one of that family's sources.
    Smith, J. does not fill from Smith, A.: those are two authors.
    """
    if not same_author(left, right):
        return False
    if bare_surname(left) or bare_surname(right):
        return True
    left_initials = _given_initials(_field_text(left))
    right_initials = _given_initials(_field_text(right))
    if not left_initials or not right_initials:
        return True
    short, long = sorted((left_initials, right_initials), key=len)
    return long[: len(short)] == short


def _research_for(source: dict[str, Any], research_by_locator: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    locator = _field_text(source.get("locator"))
    if locator and isinstance(research_by_locator.get(locator), dict):
        return research_by_locator[locator]
    ident = _field_text(source.get("id"))
    if ident:
        for row in research_by_locator.values():
            if isinstance(row, dict) and _field_text(row.get("id")) == ident:
                return row
    author = _field_text(source.get("author"))
    if not author:
        return None
    matches = [
        row
        for row in research_by_locator.values()
        if isinstance(row, dict) and same_author_initials(author, _field_text(row.get("author")))
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def complete_citation_source(
    source: dict[str, Any], research: dict[str, Any] | None
) -> dict[str, Any]:
    """Fill a surname stub from the confirmed gathered source. Nothing is invented."""
    if not isinstance(research, dict):
        return source
    merged = dict(source)
    for key in _BIBLIO_FILL:
        if _field_text(merged.get(key)):
            continue
        filled = _field_text(research.get(key))
        if filled:
            merged[key] = filled
    stub = _field_text(merged.get("author"))
    full = _field_text(research.get("author"))
    if full and (not stub or (bare_surname(stub) and same_author(stub, full))):
        merged["author"] = full
    return merged


def complete_citation_sources(
    sources: list[Any], research_by_locator: dict[str, dict[str, Any]]
) -> list[Any]:
    """Reference-list rows for Word. A gathered record supplies fields the pack left off."""
    completed: list[Any] = []
    for source in sources:
        if not isinstance(source, dict):
            completed.append(source)
            continue
        completed.append(complete_citation_source(source, _research_for(source, research_by_locator)))
    return completed


def align_in_text_cites(text: str, sources: list[Any]) -> str:
    """Bare `(Surname)` becomes `(Surname, Year)` when one gathered source owns that name."""
    if not isinstance(text, str) or not text:
        return text

    def replace(match: re.Match[str]) -> str:
        inner = norm_space(match.group(1))
        if not inner or _NAME_ONLY.fullmatch(inner) is None:
            return match.group(0)
        hits: list[tuple[str, str]] = []
        for source in sources:
            if not isinstance(source, dict):
                continue
            author = _field_text(source.get("author"))
            year = _field_text(source.get("year"))
            if not author or not year or not same_author(inner, author):
                continue
            hits.append((family_name(author), year))
        unique = list(dict.fromkeys(hits))
        if len(unique) != 1:
            return match.group(0)
        family, year = unique[0]
        return f"({family}, {year})"

    return _BARE_PAREN.sub(replace, text)


def _surname_stub_line(line: str, families: set[str]) -> bool:
    token = line.strip().rstrip(".").strip()
    if not token:
        return True
    return token.casefold() in families


def without_surname_stub_lists(sections: list[Any], sources: list[Any]) -> list[Any]:
    """Drop a body section that is only surnames. Word prints the full list itself."""
    families: set[str] = set()
    for source in sources:
        if not isinstance(source, dict):
            continue
        author = _field_text(source.get("author"))
        if not author:
            continue
        families.add(author.casefold())
        families.add(family_name(author).casefold())
        families.add(family_name(author).split()[-1].casefold())
    kept: list[Any] = []
    for section in sections:
        if not isinstance(section, dict):
            kept.append(section)
            continue
        heading = _field_text(section.get("heading")).casefold()
        raw_body = section.get("body")
        body = raw_body if isinstance(raw_body, str) else ""
        if heading in _REF_HEADINGS:
            lines = [line.strip() for line in body.splitlines() if line.strip()]
            if not lines or all(_surname_stub_line(line, families) for line in lines):
                continue
        kept.append(section)
    return kept


def prepare_word_citations(
    essay_id: str, sources: list[Any], sections: list[Any]
) -> tuple[list[Any], list[Any]]:
    """Full CTR rows and matching in-text cites for the student Word file."""
    from essay_writer.validate import research_index

    allowed, _digests = research_index(load_state(essay_id))
    completed = complete_citation_sources(sources, allowed)
    prepared = without_surname_stub_lists(sections, completed)
    aligned: list[Any] = []
    for section in prepared:
        if not isinstance(section, dict):
            aligned.append(section)
            continue
        body = section.get("body")
        row = dict(section)
        if isinstance(body, str):
            row["body"] = align_in_text_cites(body, completed)
        aligned.append(row)
    from essay_writer.cite_fit import withhold_body_cites

    return withhold_body_cites(essay_id, completed, aligned)


def token_allowed(token: str, forms: set[str]) -> bool:
    if token in forms:
        return True
    stripped = norm_space(ET_AL.sub("", token)).casefold()
    return stripped in forms


def count_words(text: str, *, exclude_citations: bool) -> int:
    if exclude_citations:
        text = PAREN.sub(" ", text)
    return len(WORD.findall(text))


def reference_parts(source: dict[str, Any]) -> list[tuple[str, bool]]:
    """Harvard Referencing pieces for the first Word file and later saves.

    A missing locator stays blank. A surname stub is completed before this
    runs, from the gathered source, so the list is not a family name alone.
    """
    from essay_writer.cite_open import apply_opened_citation
    from essay_writer.harvard_4a import harvard_4a_parts

    return harvard_4a_parts(apply_opened_citation(source))


def reference_line(source: dict[str, Any]) -> str:
    return "".join(text for text, _italic in reference_parts(source)).strip()


def figure_source_line(source: dict[str, Any]) -> str | None:
    """Author-year source line. A URL is never the figure source."""
    author = source.get("author")
    if not author:
        return None
    year = source.get("year")
    label = author.split(",", 1)[0].strip() if "," in author else str(author)
    if year:
        return f"Source: {label} ({year})"
    return f"Source: {label}"
