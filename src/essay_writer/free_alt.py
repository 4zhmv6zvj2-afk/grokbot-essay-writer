"""Fetch leftover free alternatives already stored. No new look-up.

This door runs after stage 4a confirm. It fetches addresses already on the
dig card or the download run. It does not call Consensus or Unpaywall, and
it does not invent an address.
"""

from __future__ import annotations

import json
from typing import Any

from essay_writer.confirm import (
    CONFIRM,
    DRAFT,
    confirm_ready,
    phase_refusal,
    refuse,
    save_draft,
)
from essay_writer.known_paths import guard_write_door
from essay_writer.paths import sequence_write_error, work_dir
from essay_writer.state import load_state
from essay_writer.student_voice import say

TOOL = "essay.download.leftovers"


def _http(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if text.startswith("https://") or text.startswith("http://"):
        return text
    return None


def leftover_addresses(essay_id: str) -> list[dict[str, str]]:
    """Free-alt addresses already stored for leftovers. Nothing is looked up."""
    from essay_writer.downloads import _load_state

    state = _load_state(essay_id)
    saved = {
        item.get("url")
        for item in state.get("papers") or []
        if isinstance(item, dict) and isinstance(item.get("url"), str)
    }
    found: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(url: object, **meta: object) -> None:
        text = _http(url)
        if text is None or text in seen or text in saved:
            return
        seen.add(text)
        row: dict[str, str] = {"url": text}
        for key, value in meta.items():
            if isinstance(value, str) and value.strip():
                row[key] = value.strip()
        found.append(row)

    for item in state.get("failures") or []:
        if isinstance(item, dict):
            add(item.get("url"), doi=item.get("doi"), title=item.get("title"))
    card_path = work_dir(essay_id) / "dig-card.json"
    card: dict[str, Any] = {}
    if card_path.is_file():
        try:
            loaded = json.loads(card_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            loaded = {}
        if isinstance(loaded, dict):
            card = loaded
    for item in card.get("unpaywall") or []:
        if isinstance(item, dict):
            add(item.get("oa_url"), doi=item.get("doi"))

    research = load_state(essay_id).get("research") or {}
    if isinstance(research, dict):
        for depth in ("summary", "full"):
            record = research.get(depth)
            if not isinstance(record, dict):
                continue
            for source in record.get("sources") or []:
                if isinstance(source, dict):
                    add(source.get("url"), doi=source.get("doi"), title=source.get("title"))
    from essay_writer.roll_forward import without_keepers

    return without_keepers(essay_id, found)


def essay_download_leftovers(essay_id: str, confirmPhase: str | None = None) -> dict[str, object]:
    """Draft lists stored leftover addresses. Confirm fetches those addresses only."""
    from essay_writer.specialists.researcher import real_4a_bibliography

    id_error = sequence_write_error(essay_id)
    if id_error:
        return refuse("essay-id", id_error)
    phase = phase_refusal(confirmPhase)
    if phase:
        return phase
    blocked = guard_write_door(work_dir(essay_id))
    if blocked:
        return blocked
    if not real_4a_bibliography(essay_id):
        return refuse(
            "4a",
            "Confirm the annotated bibliography before fetching leftovers.",
            wrote=False,
        )
    rows = leftover_addresses(essay_id)
    payload = {"essay_id": essay_id, "urls": [item["url"] for item in rows]}
    fingerprint = {"urls": payload["urls"]}
    body: dict[str, Any] = {
        "ok": True,
        "essay_id": essay_id,
        "confirmPhase": confirmPhase,
        "wrote": False,
        "stored": False,
        "leftovers": rows,
        "lookup": False,
        "invent_forbid": True,
    }
    if not rows:
        body["next"] = say(
            "No leftover free-alternative address is already stored. "
            "Nothing was fetched. Do not invent an address."
        )
        if confirmPhase == CONFIRM:
            body["ok"] = True
        return body
    if confirmPhase == DRAFT:
        body["digest"] = save_draft(essay_id, TOOL, payload, fingerprint)
        body["next"] = say(
            "These leftover free alternatives were already found. "
            "Say yes to fetch them. No new look-up is opened."
        )
        return body
    ready = confirm_ready(essay_id, TOOL, payload, fingerprint)
    if ready.get("ok") is False:
        ready["confirmPhase"] = CONFIRM
        ready["wrote"] = False
        return ready
    from essay_writer.downloads import run_downloads

    fetched = run_downloads(essay_id, rows, retry_known=True)
    body["downloads"] = fetched
    body["wrote"] = bool(fetched.get("wrote"))
    body["stored"] = True
    body["digest"] = ready["digest"]
    saved = fetched.get("papers") or []
    if saved:
        body["next"] = say("Leftover free alternatives already found were fetched. Only a real PDF is kept.")
    else:
        body["next"] = say(
            "The stored leftover addresses were fetched. No new PDF was saved. Do not invent an address."
        )
    return body
