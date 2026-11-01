"""Research summary and full research. Draft, then confirm. invent-forbid."""

from __future__ import annotations

from typing import Any

from essay_writer.canon import digest, file_sha256
from essay_writer.clarify import parse_clarify
from essay_writer.confirm import (
    CONFIRM,
    DRAFT,
    confirm_ready,
    now,
    phase_refusal,
    refuse,
    save_draft,
)
from essay_writer.gathered_set import collapse_same_work, gathered_set_issues
from essay_writer.harvard_4a import annotation_notes, review_markdowns
from essay_writer.invent import check_claims, gather_sources, load_text_for
from essay_writer.known_paths import guard_write_door
from essay_writer.originals import material_locators
from essay_writer.paths import local_pack_names, sequence_write_error, work_dir, workspace_root
from essay_writer.resolvers import enrich_sources, field_provenance, find_opposing_point
from essay_writer.specialists.researcher import ship_4a, ship_4b
from essay_writer.state import load_state, save_state
from essay_writer.student_voice import say

SUMMARY = "essay.research.summary"
FULL = "essay.research.full"
GAP_FIELDS = ("pages", "doi", "accessed")


def _gaps_for_sources(sources: list[dict[str, Any]]) -> list[str]:
    return [
        f"{source['id']}: {field} not gathered; left blank"
        for source in sources
        for field in GAP_FIELDS
        if field not in source
    ]


def _topic_error(topic: object) -> str | None:
    if not isinstance(topic, str) or not topic.strip():
        return "topic is required. The door does not invent the essay question."
    return None


def _door_options(
    essay_id: str,
    packs: list[Any] | None,
    exclude_section_ids: list[Any] | None,
    industry: dict[str, Any] | None,
    host_voice: Any,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Optional research fields, bound to this essay's local store."""
    if packs is None:
        names: list[str] = []
    elif (
        not isinstance(packs, list)
        or any(not isinstance(item, str) or not item.strip() for item in packs)
    ):
        return None, refuse(
            "packs",
            "packs must be a list of local pack names from essay.health. Do not invent one.",
        )
    elif len(packs) > 2:
        return None, refuse("packs", "At most two local packs. Do not invent extras.")
    else:
        allowed = set(local_pack_names(essay_id))
        names = []
        for item in packs:
            name = item.strip().replace("\\", "/")
            if name not in allowed:
                return None, refuse(
                    "packs",
                    f"{name} is not a local pack on essay.health for this essay. "
                    "The door does not invent packs.",
                )
            names.append(name)
    if exclude_section_ids is None:
        excluded: list[str] = []
    elif (
        not isinstance(exclude_section_ids, list)
        or any(not isinstance(item, str) or not item.strip() for item in exclude_section_ids)
    ):
        return None, refuse(
            "exclude",
            "exclude_section_ids must be the section ids a person chose to leave closed.",
        )
    else:
        excluded = [item.strip() for item in exclude_section_ids]
    if industry is not None and not isinstance(industry, dict):
        return None, refuse("industry", "industry must be an object when it is sent. It is not evidence.")
    try:
        digest({"industry": industry, "host_voice": host_voice})
    except TypeError:
        return None, refuse("host_voice", "host_voice must be data the door can store. It is not evidence.")
    return {
        "packs": names,
        "exclude_section_ids": excluded,
        "industry": industry,
        "host_voice": host_voice,
    }, None


def _open_named_packs(names: list[str], excluded: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    opened: list[dict[str, Any]] = []
    skipped: list[str] = []
    banned = set(excluded)
    for name in names:
        if name in banned:
            skipped.append(name)
            continue
        path = workspace_root() / name
        opened.append(
            {
                "name": name,
                "sha256": file_sha256(path),
                "evidence": False,
            }
        )
    return opened, skipped


def _without_dropped(items: list[Any] | None, dropped: set[str], key: str) -> list[Any] | None:
    """Drop rows whose id belonged to a file the gathered-set gate collapsed."""
    if not isinstance(items, list) or not dropped:
        return items
    kept_items: list[Any] = []
    for item in items:
        if isinstance(item, dict):
            ident = item.get(key)
            if isinstance(ident, str) and ident.strip() in dropped:
                continue
        kept_items.append(item)
    return kept_items


def _excluded_sources(sources: list[Any] | None, excluded: list[str]) -> list[dict[str, str]]:
    if not excluded or not sources:
        return []
    banned = set(excluded)
    issues: list[dict[str, str]] = []
    for index, raw in enumerate(sources):
        if not isinstance(raw, dict):
            continue
        locator = raw.get("locator")
        locator_text = locator.strip().replace("\\", "/") if isinstance(locator, str) else ""
        if raw.get("id") in banned or locator_text in banned:
            issues.append(
                {
                    "code": "exclude",
                    "reason": (
                        f"sources[{index}] is in exclude_section_ids. "
                        "A person closed that section, so it is not evidence."
                    ),
                }
            )
    return issues


def _payload(
    essay_id: str,
    topic: str,
    sources: list[Any] | None,
    claims: list[Any] | None,
    depth: str,
    clarify: dict[str, Any] | None,
    options: dict[str, Any],
    reviews: list[Any] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "essay_id": essay_id,
        "topic": topic.strip(),
        "sources": sources or [],
        "claims": claims or [],
        "depth": depth,
        "packs": options["packs"],
        "exclude_section_ids": options["exclude_section_ids"],
        "industry": options["industry"],
        "host_voice": options["host_voice"],
    }
    if depth == "full":
        payload["clarify_context"] = clarify
        payload["reviews"] = reviews
    return payload


def _surface_refuse(issues: list[dict[str, Any]]) -> dict[str, Any]:
    """One note or review reply. Several codes name every current miss."""
    codes: list[str] = []
    for item in issues:
        code = item.get("code")
        if isinstance(code, str) and code not in codes:
            codes.append(code)
    if len(codes) <= 1:
        code = codes[0] if codes else "invent-forbid"
        return refuse(
            code,
            str(issues[0].get("reason") or ""),
            issues=issues,
            invent_forbid="refuse" if code == "invent-forbid" else "pass",
        )
    misses: list[dict[str, Any]] = []
    words: list[str] = []
    for item in issues:
        miss: dict[str, Any] = {"code": item.get("code"), "reason": item.get("reason")}
        item_words = item.get("words")
        if isinstance(item_words, list) and item_words:
            miss["words"] = list(item_words)
            for word in item_words:
                if isinstance(word, str) and word not in words:
                    words.append(word)
        misses.append(miss)
    extra: dict[str, Any] = {
        "issues": issues,
        "misses": misses,
        "invent_forbid": "refuse" if "invent-forbid" in codes else "pass",
    }
    if words:
        extra["words"] = words
    reasons = [str(item.get("reason") or "") for item in issues if item.get("reason")]
    return refuse("misses", " ".join(reasons), **extra)


def _prepare(
    essay_id: str,
    topic: str,
    sources: list[Any] | None,
    claims: list[Any] | None,
    options: dict[str, Any],
    reviews: list[Any] | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    excluded_issues = _excluded_sources(sources, options["exclude_section_ids"])
    if excluded_issues:
        return None, refuse(
            "exclude",
            excluded_issues[0]["reason"],
            issues=excluded_issues,
        )
    kept, issues = gather_sources(essay_id, sources)
    texts = {source["locator"]: load_text_for(source) for source in kept}
    issues.extend(check_claims(kept, claims, texts, essay_id))
    if issues:
        code = "cross-essay" if any(item["code"] == "cross-essay" for item in issues) else "invent-forbid"
        return None, refuse(code, issues[0]["reason"], issues=issues, invent_forbid="refuse")
    kept, resolvers_called, _resolver_values = enrich_sources(kept, texts)
    kept, dropped_ids = collapse_same_work(kept, texts)
    claims = _without_dropped(claims, dropped_ids, "source_id")
    notes, note_issues = annotation_notes(kept, sources, texts)
    if note_issues:
        return None, _surface_refuse(note_issues)
    gate_issues = gathered_set_issues(essay_id, kept, texts, notes)
    if gate_issues:
        return None, refuse(
            gate_issues[0]["code"],
            gate_issues[0]["reason"],
            issues=gate_issues,
        )
    for source in kept:
        note = notes.get(source["id"])
        if isinstance(note, str) and note.strip():
            source["annotation"] = note.strip()
    reviews = _without_dropped(reviews, dropped_ids, "paper_id")
    papers, review_issues = review_markdowns(kept, reviews, texts)
    if review_issues:
        return None, _surface_refuse(review_issues)
    opened_set = {source["locator"] for source in kept}
    gaps = _gaps_for_sources(kept)
    grounded_claims: list[dict[str, Any]] = []
    if claims:
        by_id = {source["id"]: source for source in kept}
        for claim in claims:
            source = by_id[claim["source_id"]]
            item = {"source_id": source["id"], "quote": claim["quote"]}
            if claim.get("page") is not None:
                item["page"] = str(claim["page"]).strip()
            grounded_claims.append(item)
    preview = {
        "topic": topic.strip(),
        "opened": [
            {
                "id": source["id"],
                "origin": source["origin"],
                "locator": source["locator"],
                "sha256": source["sha256"],
            }
            for source in kept
        ],
        "not_opened": [locator for locator in material_locators(essay_id) if locator not in opened_set],
        "sources": kept,
        "claims": grounded_claims,
        "gaps": gaps,
        "invent_forbid": "pass",
        "referencing": "harvard",
        "resolvers_called": resolvers_called,
        "resolver_policy": "free-only",
        "field_provenance": {source["id"]: field_provenance(source) for source in kept},
        "clarify_is_not_evidence": True,
        "conclusion_choices": ["noted", "open"],
    }
    named, skipped = _open_named_packs(options["packs"], options["exclude_section_ids"])
    preview["packs"] = named
    preview["packs_excluded"] = skipped
    preview["exclude_section_ids"] = options["exclude_section_ids"]
    preview["not_evidence"] = {
        "industry": options["industry"],
        "host_voice": options["host_voice"],
        "clarify_context": "frames the question only",
        "packs": "named notes are not citations until a gathered source points at them",
    }
    files = {source["locator"]: source["sha256"] for source in kept}
    for pack in named:
        files[pack["name"]] = pack["sha256"]
    opposing = find_opposing_point(kept, texts)
    preview["opposing_point"] = opposing
    # Student arguments and gathered-file hashes. Resolver fills stay on the
    # shown card. A second enrich that disagrees is not a confirm failure.
    fingerprint = {
        "topic": topic.strip(),
        "sources": sources or [],
        "files": files,
    }
    research_pack = {
        "topic": topic.strip(),
        "opened_files": preview["opened"],
        "sources": kept,
        "field_provenance": preview["field_provenance"],
        "claims": grounded_claims,
        "gaps": gaps,
        "resolvers_called": resolvers_called,
        "opposing_point": opposing,
        "not_evidence": preview["not_evidence"],
    }
    return {
        "preview": preview,
        "fingerprint": fingerprint,
        "sources": kept,
        "research_pack": research_pack,
        "annotation_notes": notes,
        "review_markdowns": papers,
    }, None


def _shown_research(prepared: dict[str, Any]) -> dict[str, Any]:
    """Resolver fields and sources from the draft. Confirm saves this card."""
    return {
        "preview": prepared["preview"],
        "sources": prepared["sources"],
        "research_pack": prepared["research_pack"],
        "annotation_notes": prepared["annotation_notes"],
        "review_markdowns": prepared["review_markdowns"],
        "files": dict(prepared["fingerprint"]["files"]),
    }


def _stored_research(record: dict[str, Any]) -> dict[str, Any] | None:
    shown = record.get("shown")
    if not isinstance(shown, dict):
        return None
    if not isinstance(shown.get("preview"), dict) or not isinstance(shown.get("sources"), list):
        return None
    if not isinstance(shown.get("research_pack"), dict) or not isinstance(shown.get("files"), dict):
        return None
    return shown


def _run(
    tool: str,
    depth: str,
    essay_id: str,
    topic: str,
    confirmPhase: str | None,
    sources: list[Any] | None,
    claims: list[Any] | None,
    clarify_context: dict[str, Any] | None,
    packs: list[Any] | None,
    exclude_section_ids: list[Any] | None,
    industry: dict[str, Any] | None,
    host_voice: Any,
    reviews: list[Any] | None = None,
) -> dict[str, Any]:
    id_error = sequence_write_error(essay_id)
    if id_error:
        return refuse("essay-id", id_error)
    topic_error = _topic_error(topic)
    if topic_error:
        return refuse("topic", topic_error)
    phase = phase_refusal(confirmPhase)
    if phase:
        return phase

    blocked = guard_write_door(work_dir(essay_id))
    if blocked:
        return blocked
    clarify = None
    if depth == "full":
        clarify, errors = parse_clarify(clarify_context)
        if errors:
            return refuse(
                "clarify",
                errors[0],
                issues=[{"code": "clarify", "reason": item} for item in errors],
            )
    options, option_refusal = _door_options(
        essay_id, packs, exclude_section_ids, industry, host_voice
    )
    if option_refusal or options is None:
        assert option_refusal is not None
        option_refusal["confirmPhase"] = confirmPhase
        return option_refusal
    payload = _payload(
        essay_id,
        topic,
        sources,
        claims,
        depth,
        clarify_context if depth == "full" else None,
        options,
        reviews if depth == "full" else None,
    )
    prepared, refusal = _prepare(
        essay_id,
        topic,
        sources,
        claims,
        options,
        reviews if depth == "full" else None,
    )
    if refusal or prepared is None:
        assert refusal is not None
        refusal["confirmPhase"] = confirmPhase
        return refusal
    fingerprint = prepared["fingerprint"]
    body = {
        "ok": True,
        "essay_id": essay_id,
        "depth": depth,
        "confirmPhase": confirmPhase,
        "wrote": False,
        "referencing": "harvard",
        "same_arguments_required": True,
        **prepared["preview"],
    }
    if depth == "full":
        body["clarify_context"] = clarify
    if confirmPhase == DRAFT:
        body["digest"] = save_draft(
            essay_id, tool, payload, fingerprint, shown=_shown_research(prepared)
        )
        body["stored"] = False
        body["next"] = say(
            "Show this draft to the human. Say yes only for these same arguments "
            "after you have seen this result."
        )
        return body
    ready = confirm_ready(essay_id, tool, payload, fingerprint)
    if ready.get("ok") is False:
        ready["confirmPhase"] = CONFIRM
        return ready
    shown = _stored_research(ready)
    if shown is None:
        return refuse(
            "confirm",
            "No matching draft is waiting. Show this step in the chat again before it can be saved. "
            "If the draft, the topic, or the source list changed, show it again.",
            confirmPhase=CONFIRM,
        )
    # A second enrich may have filled a field the draft missed. The saved
    # source keeps the draft's fields. The file-hash half already matched.
    body.update(shown["preview"])
    body["sources"] = shown["sources"]
    body["research_pack"] = shown["research_pack"]
    state = load_state(essay_id)
    record = {
        "digest": ready["digest"],
        "topic": topic.strip(),
        "depth": depth,
        "sources": shown["sources"],
        "claims": shown["preview"]["claims"],
        "opened": shown["preview"]["opened"],
        "not_opened": shown["preview"]["not_opened"],
        "gaps": shown["preview"]["gaps"],
        "files": shown["files"],
        "clarify_context": clarify,
        "packs": options["packs"],
        "exclude_section_ids": options["exclude_section_ids"],
        "not_evidence": shown["preview"]["not_evidence"],
        "resolvers_called": shown["preview"]["resolvers_called"],
        "field_provenance": shown["preview"]["field_provenance"],
        "opposing_point": shown["preview"]["opposing_point"],
        "research_pack": shown["research_pack"],
        "confirmed_at": now(),
    }
    if depth == "summary":
        delivery = ship_4a(essay_id, shown["sources"], shown["annotation_notes"])
        if delivery.get("ok") is False:
            delivery["confirmPhase"] = CONFIRM
            delivery["stored"] = False
            return delivery
    state["research"][depth] = record
    save_state(essay_id, state)
    body["stored"] = True
    body["digest"] = ready["digest"]
    body["confirmed_at"] = record["confirmed_at"]
    body["research_pack"] = shown["research_pack"]
    if depth == "summary":
        body["delivery"] = delivery
        body["next"] = say(
            "Research is stored for this essay. The annotated bibliography is the Word file in the chat. "
            "Next is essay.pack.validate."
        )
    else:
        body["delivery"] = ship_4b(
            essay_id,
            shown["sources"],
            shown["review_markdowns"],
        )
        body["next"] = say(
            "Research is stored for this essay. One Word file per paper is in the zip. "
            "Next is essay.pack.validate."
        )
    return body


def essay_research_summary(
    essay_id: str,
    topic: str,
    confirmPhase: str | None = None,
    sources: list[Any] | None = None,
    claims: list[Any] | None = None,
    packs: list[str] | None = None,
    exclude_section_ids: list[str] | None = None,
    industry: dict[str, Any] | None = None,
    host_voice: Any = None,
) -> dict[str, Any]:
    return _run(
        SUMMARY,
        "summary",
        essay_id,
        topic,
        confirmPhase,
        sources,
        claims,
        None,
        packs,
        exclude_section_ids,
        industry,
        host_voice,
    )


def essay_research_full(
    essay_id: str,
    topic: str,
    confirmPhase: str | None = None,
    sources: list[Any] | None = None,
    claims: list[Any] | None = None,
    clarify_context: dict[str, Any] | None = None,
    packs: list[str] | None = None,
    exclude_section_ids: list[str] | None = None,
    industry: dict[str, Any] | None = None,
    host_voice: Any = None,
    reviews: list[Any] | None = None,
) -> dict[str, Any]:
    return _run(
        FULL,
        "full",
        essay_id,
        topic,
        confirmPhase,
        sources,
        claims,
        clarify_context,
        packs,
        exclude_section_ids,
        industry,
        host_voice,
        reviews,
    )
