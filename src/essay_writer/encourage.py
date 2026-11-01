"""One optional question after the Stage 3 plan is saved.

The front office may ask the student for one substance detail at a time.
Choices come from the locked plan, the brief, and those sections. Each ask
also offers type-your-own and skip. Silence does not block the saved stage
and does not invent a detail. A skip records nothing. The next ask waits
until this one is answered or skipped.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

from essay_writer import textutil as essay_textutil
from essay_writer.paths import work_dir
from essay_writer.state import load_state
from essay_writer.student_voice import say

DEPTH = "depth"
EXAMPLE = "example"
SURPRISED = "surprised"

DEPTH_PROMPT = "Which part of the saved plan should the draft lean on hardest?"
EXAMPLE_PROMPT = "Which example or case from the saved plan may the draft use?"
SURPRISED_PROMPT = "What in the saved plan surprised you?"

_PROMPTS = {
    DEPTH: DEPTH_PROMPT,
    EXAMPLE: EXAMPLE_PROMPT,
    SURPRISED: SURPRISED_PROMPT,
}

_LOCK_LINE = re.compile(
    r"(?i)^(?:thesis|central theme|theme|purpose and scope|purpose)\s*:\s*(.+)$"
)
_RESEARCH_LINE = re.compile(r"(?i)^research\s*:\s*(.+)$")
_EXAMPLE_LINE = re.compile(r"(?i)^(?:example|case)\s*:\s*(.+)$")
_SECTION_LINE = re.compile(r"(?i)^section\s*:\s*(.+)$")
_HEADING = re.compile(r"^(?:#{1,3}\s+|(?:\d{1,2}|[A-Za-z])[.)]\s+)(.+)$")
_NEG = re.compile(
    r"(?i)\b(?:not|never|no|without|opposite|against|isn['’]t|aren['’]t|"
    r"don['’]t|doesn['’]t|cannot|can['’]t)\b"
)
_REFLECT = re.compile(
    r"(?i)\b(?:reflective diary|learning diary|reflective journal|"
    r"reflection|what surprised|surprised by)\b"
)
_TYPE_OWN = re.compile(r"(?i)^type(?:\s*|-)?own\s*:\s*(.*)$")
_WORD = re.compile(r"[A-Za-z][A-Za-z'-]{3,}")
_STOP = frozenset(
    {
        "that",
        "this",
        "with",
        "from",
        "have",
        "been",
        "were",
        "they",
        "them",
        "your",
        "into",
        "over",
        "only",
        "when",
        "what",
        "which",
        "their",
        "there",
        "about",
        "after",
        "before",
        "would",
        "could",
        "should",
        "shall",
        "than",
        "then",
        "also",
        "just",
        "more",
        "most",
        "some",
        "such",
        "other",
        "another",
        "between",
        "within",
    }
)
_RESERVED = frozenset({"type your own", "type-own", "skip"})
_SKIP = frozenset({"skip", "skipped", "skip it", "skip this"})


def _record_path(essay_id: str):

    return work_dir(essay_id) / "tracking" / "encourage.json"


def _blank() -> dict[str, Any]:
    return {
        "plan_text": "",
        "order": [],
        "shown": None,
        "slots": {},
        "facts": {},
        "own": {},
    }


def load_encourage(essay_id: str) -> dict[str, Any] | None:
    path = _record_path(essay_id)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    record = _blank()
    plan = data.get("plan_text")
    if isinstance(plan, str):
        record["plan_text"] = plan
    order = data.get("order")
    if isinstance(order, list):
        record["order"] = [item for item in order if item in _PROMPTS]
    shown = data.get("shown")
    record["shown"] = shown if shown in _PROMPTS else None
    slots = data.get("slots")
    if isinstance(slots, dict):
        record["slots"] = {
            key: value
            for key, value in slots.items()
            if key in _PROMPTS and value in {"open", "waiting", "answered", "skipped"}
        }
    facts = data.get("facts")
    if isinstance(facts, dict):
        record["facts"] = {
            key: value
            for key, value in facts.items()
            if key in _PROMPTS and isinstance(value, str) and value.strip()
        }
    own = data.get("own")
    if isinstance(own, dict):
        record["own"] = {key: True for key, value in own.items() if key in _PROMPTS and value is True}
    return record


def _save(essay_id: str, record: dict[str, Any]) -> None:
    path = _record_path(essay_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _words(text: str) -> list[str]:
    found: list[str] = []
    for match in _WORD.finditer(text):
        word = match.group(0).casefold().strip("'-")
        if len(word) < 4 or word in _STOP or word in found:
            continue
        found.append(word)
    return found


def _overlaps(option: str, lock: str) -> bool:
    words = _words(lock)
    if len(words) < 2:
        return False
    folded = option.casefold()
    hits = 0
    for word in words:
        stem = word[:-1] if word.endswith("s") and len(word) > 4 else word
        if word in folded or (stem != word and stem in folded):
            hits += 1
    return hits >= 2


def contradicts(option: str, locks: list[str]) -> bool:
    """True when an option negates a locked theme, thesis, or research line."""
    if not option.strip() or _NEG.search(option) is None:
        return False
    return any(_overlaps(option, lock) for lock in locks if isinstance(lock, str) and lock.strip())


def _collect(text: str) -> tuple[list[str], list[str], list[str]]:
    sections: list[str] = []
    examples: list[str] = []
    locks: list[str] = []
    if not isinstance(text, str):
        return sections, examples, locks
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        lock = _LOCK_LINE.match(line)
        if lock:
            locks.append(lock.group(1).strip())
            continue
        research = _RESEARCH_LINE.match(line)
        if research:
            locks.append(research.group(1).strip())
            continue
        example = _EXAMPLE_LINE.match(line)
        if example:
            examples.append(example.group(1).strip())
            continue
        section = _SECTION_LINE.match(line)
        if section:
            sections.append(section.group(1).strip())
            continue
        heading = _HEADING.match(line)
        if heading:
            title = heading.group(1).strip()
            if title and _LOCK_LINE.match(title) is None and _EXAMPLE_LINE.match(title) is None:
                sections.append(title)
    return sections, examples, locks


def _dedupe(items: list[str]) -> list[str]:
    kept: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = re.sub(r"\s+", " ", item).strip()
        if not text or len(text) > 160:
            continue
        key = text.casefold()
        if key in seen or key in _RESERVED:
            continue
        seen.add(key)
        kept.append(text)
    return kept


def _research_locks(essay_id: str) -> list[str]:

    try:
        state = load_state(essay_id)
    except (OSError, ValueError):
        return []
    research = state.get("research") if isinstance(state.get("research"), dict) else {}
    locks: list[str] = []
    if not isinstance(research, dict):
        return locks
    for depth in ("summary", "full"):
        record = research.get(depth)
        sources = record.get("sources") if isinstance(record, dict) else None
        if not isinstance(sources, list):
            continue
        for source in sources:
            if not isinstance(source, dict):
                continue
            for key in ("title", "quote"):
                value = source.get(key)
                if isinstance(value, str) and value.strip():
                    locks.append(value.strip())
    return locks


def _materials(essay_id: str, plan_text: str) -> tuple[list[str], list[str], list[str]]:

    plan_sections, plan_examples, plan_locks = _collect(plan_text)
    brief_sections, brief_examples, brief_locks = _collect(essay_textutil.module_brief_text(essay_id))
    sections = _dedupe(plan_sections + brief_sections)
    examples = _dedupe(plan_examples + brief_examples)
    locks = _dedupe(plan_locks + brief_locks + _research_locks(essay_id))
    sections = [item for item in sections if not contradicts(item, locks)]
    examples = [item for item in examples if not contradicts(item, locks)]
    return sections, examples, locks


def wants_reflection(essay_id: str) -> bool:
    """True when the brief or the diary asks for reflection. The plan alone does not."""
    from essay_writer.stage_llm import brief_genre

    if brief_genre(essay_id) == "diary":
        return True
    return _REFLECT.search(essay_textutil.module_brief_text(essay_id) or "") is not None


def ask_order(essay_id: str) -> tuple[str, ...]:
    if wants_reflection(essay_id):
        return (DEPTH, EXAMPLE, SURPRISED)
    return (DEPTH, EXAMPLE)


def _slug(label: str) -> str:
    token = re.sub(r"[^a-z0-9]+", "-", label.casefold()).strip("-")
    return token[:48] or "item"


def _options(labels: list[str], prefix: str) -> list[dict[str, str]]:
    options: list[dict[str, str]] = []
    for label in labels:
        options.append({"id": f"{prefix}:{_slug(label)}", "label": label})
    options.append({"id": "type-own", "label": "Type your own"})
    options.append({"id": "skip", "label": "Skip"})
    return options


def _labels_for(slot: str, sections: list[str], examples: list[str]) -> list[str]:
    if slot == EXAMPLE:
        return examples
    return sections


def _speech(prompt: str, options: list[dict[str, str]]) -> str:
    numbered = " ".join(f"{index}. {item['label']}" for index, item in enumerate(options, 1))
    return f"{prompt} {numbered}"


def _ask(slot: str, sections: list[str], examples: list[str]) -> dict[str, Any]:
    prompt = _PROMPTS[slot]
    prefix = "example" if slot == EXAMPLE else "section"
    options = _options(_labels_for(slot, sections, examples), prefix)
    return {
        "id": slot,
        "prompt": prompt,
        "options": options,
        "speech": _speech(prompt, options),
    }


def _pack(ask: dict[str, Any] | None) -> dict[str, Any]:
    if ask is None:
        return {"count": 0, "ask": None, "speech": ""}
    return {"count": 1, "ask": ask, "speech": ask["speech"]}


def _facts(record: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(record, dict):
        return {}
    facts = record.get("facts")
    if not isinstance(facts, dict):
        return {}
    return {
        key: value.strip()
        for key, value in facts.items()
        if isinstance(value, str) and value.strip()
    }


def student_facts(essay_id: str) -> dict[str, str]:
    """Details the student actually gave. Skipped and silent slots stay absent."""
    return _facts(load_encourage(essay_id))


def _current_ask(essay_id: str, record: dict[str, Any]) -> dict[str, Any] | None:
    shown = record.get("shown")
    if shown not in _PROMPTS:
        return None
    if record.get("slots", {}).get(shown) != "open":
        return None
    sections, examples, _locks = _materials(essay_id, str(record.get("plan_text") or ""))
    return _ask(shown, sections, examples)


def _new_record(essay_id: str, plan_text: str) -> dict[str, Any]:
    order = list(ask_order(essay_id))
    slots = {name: "waiting" for name in order}
    slots[order[0]] = "open"
    return {
        "plan_text": plan_text,
        "order": order,
        "shown": order[0],
        "slots": slots,
        "facts": {},
        "own": {},
    }


def _drop_stale_facts(essay_id: str, record: dict[str, Any]) -> None:
    sections, examples, _locks = _materials(essay_id, str(record.get("plan_text") or ""))
    own_raw = record.get("own")
    own: dict[str, Any] = own_raw if isinstance(own_raw, dict) else {}
    facts_raw = record.get("facts")
    facts: dict[str, Any] = facts_raw if isinstance(facts_raw, dict) else {}
    for slot, value in list(facts.items()):
        if own.get(slot) is True:
            continue
        allowed = {label.casefold() for label in _labels_for(slot, sections, examples)}
        if not isinstance(value, str) or value.casefold() not in allowed:
            facts.pop(slot, None)
            own.pop(slot, None)
    record["facts"] = facts
    record["own"] = own


def attach_plan_encourage(body: dict[str, Any], essay_id: str, plan_text: str) -> dict[str, Any]:
    """One ask on a saved Stage 3 plan. The save itself is already done."""
    if body.get("stored") is not True:
        return body
    record = load_encourage(essay_id)
    if record is None or not record.get("order"):
        record = _new_record(essay_id, plan_text)
    else:
        record["plan_text"] = plan_text
        _drop_stale_facts(essay_id, record)
    try:
        _save(essay_id, record)
    except OSError:
        return body
    ask = _current_ask(essay_id, record)
    if ask is None:
        return body
    body["encourage"] = _pack(ask)
    return body


def _advance(record: dict[str, Any]) -> None:
    order = [name for name in record.get("order") or [] if name in _PROMPTS]
    slots_raw = record.get("slots")
    slots: dict[str, Any] = slots_raw if isinstance(slots_raw, dict) else {}
    shown = record.get("shown")
    nxt = None
    passed = shown not in order
    for name in order:
        if not passed:
            if name == shown:
                passed = True
            continue
        if slots.get(name) == "waiting":
            nxt = name
            break
    if nxt is None:
        record["shown"] = None
        return
    slots[nxt] = "open"
    record["slots"] = slots
    record["shown"] = nxt


def _classify(choice: str, options: list[dict[str, str]]) -> tuple[str, str | None]:
    text = choice.strip()
    if not text:
        return "silence", None
    folded = re.sub(r"\s+", " ", text).strip().casefold().strip(" .!")
    if folded in _SKIP:
        return "skip", None
    own = _TYPE_OWN.match(text)
    if own:
        body = own.group(1).strip()
        if not body:
            return "silence", None
        return "own", body
    if folded in {"type-own", "type your own", "type own"}:
        return "silence", None
    for option in options:
        if folded == option["id"].casefold() or folded == option["label"].casefold():
            if option["id"] == "skip":
                return "skip", None
            if option["id"] == "type-own":
                return "silence", None
            return "pick", option["label"]
    return "unknown", None


def _reply(
    essay_id: str,
    record: dict[str, Any] | None,
    *,
    silence: bool,
    accepted: bool,
) -> dict[str, Any]:
    ask = _current_ask(essay_id, record) if isinstance(record, dict) else None
    packed = _pack(ask)
    speech = packed["speech"]
    return {
        "ok": True,
        "essay_id": essay_id,
        "blocked": False,
        "invented": False,
        "silence": silence,
        "accepted": accepted,
        "facts": _facts(record),
        "encourage": packed,
        "next": speech or "The plan is saved.",
    }


def answer_encourage(essay_id: str, choice: str | None) -> dict[str, Any]:
    """Record one answer or skip. Silence leaves the same ask open and invents nothing."""
    record = load_encourage(essay_id)
    if record is None or record.get("shown") not in _PROMPTS:
        return _reply(essay_id, record, silence=not (choice or "").strip(), accepted=False)
    ask = _current_ask(essay_id, record)
    if ask is None:
        return _reply(essay_id, record, silence=not (choice or "").strip(), accepted=False)
    kind, value = _classify(choice or "", ask["options"])
    if kind in {"silence", "unknown"}:
        return _reply(essay_id, record, silence=kind == "silence", accepted=False)
    slot = ask["id"]
    slots = record["slots"]
    if kind == "skip":
        slots[slot] = "skipped"
        record["facts"].pop(slot, None)
        record["own"].pop(slot, None)
    elif kind == "own" and isinstance(value, str):
        slots[slot] = "answered"
        record["facts"][slot] = value
        record["own"][slot] = True
    elif kind == "pick" and isinstance(value, str):
        slots[slot] = "answered"
        record["facts"][slot] = value
        record["own"].pop(slot, None)
    else:
        return _reply(essay_id, record, silence=False, accepted=False)
    record["slots"] = slots
    _advance(record)
    try:
        _save(essay_id, record)
    except OSError:
        return _reply(essay_id, record, silence=False, accepted=False)
    return _reply(essay_id, record, silence=False, accepted=True)


def append_encourage_speech(body: dict[str, Any]) -> dict[str, Any]:
    """Front-office speech. One question is added to next. The stage line stays."""

    encourage = body.get("encourage")
    if not isinstance(encourage, dict) or encourage.get("count") != 1:
        return body
    speech = encourage.get("speech")
    if not isinstance(speech, str) or not speech.strip():
        return body
    spoken = say(speech.strip())
    if not spoken:
        return body
    nxt = body.get("next")
    if isinstance(nxt, str) and spoken in nxt:
        return body
    if isinstance(nxt, str) and nxt.strip():
        body["next"] = f"{nxt.rstrip()} {spoken}"
    else:
        body["next"] = spoken
    return body
