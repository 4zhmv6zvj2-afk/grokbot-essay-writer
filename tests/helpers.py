def plant_gathered_source(seq: str) -> None:
    """Store one gathered source so stage 4a confirm has a bibliography."""
    from essay_writer.paths import module_code
    from essay_writer.state import load_state, save_state

    state = load_state(seq)
    research = state.get("research")
    if not isinstance(research, dict):
        research = {"summary": None, "full": None}
        state["research"] = research
    summary = research.get("summary")
    if isinstance(summary, dict) and summary.get("sources"):
        return
    module = module_code(seq)
    research["summary"] = {
        "sources": [
            {
                "id": "src-1",
                "author": "Smith, J.",
                "year": "2020",
                "title": "Chokepoints and crude",
                "locator": f"uploads/{module}/smith.md",
            }
        ]
    }
    save_state(seq, state)


def picked(draft: dict) -> dict:
    """Arguments that pick the Confirm card on this stage draft."""
    return {"cardAction": "confirm", "cardDigest": draft.get("digest")}


SAMPLE_REFERENCE_LINE = (
    "Smith, J. (2020) 'Chokepoints and crude', Maritime Policy, 12(3), pp. 4-9. "
    "Available at: doi:10.1000/strait."
)


def with_word_references(pack: dict) -> dict:
    """Ensure stage 10 and Word writes have at least one reference line."""
    body = dict(pack)
    if body.get("sources"):
        return body
    if isinstance(body.get("references_markdown"), str) and body["references_markdown"].strip():
        return body
    body["references_markdown"] = SAMPLE_REFERENCE_LINE
    return body


def ensure_word_refs(seq: str) -> None:
    """Saved pack carries reference lines so stage 10 Word is not heading-only."""
    from essay_writer.state import load_state, save_state

    state = load_state(seq)
    pack = state.get("saved_pack")
    if not isinstance(pack, dict):
        pack = {
            "essay_id": seq,
            "referencing": "harvard",
            "conclusion": "noted",
            "sections": [{"heading": "Draft", "body": "Draft text for Word."}],
        }
    state["saved_pack"] = with_word_references(pack)
    save_state(seq, state)


def plant_renderable_pack(seq: str) -> None:
    """A small saved pack so stage 10 can write the sequence Word file."""
    from essay_writer.state import load_state, save_state

    state = load_state(seq)
    state["saved_pack"] = with_word_references(
        {
            "essay_id": seq,
            "title": "Kept draft",
            "referencing": "harvard",
            "conclusion": "noted",
            "sections": [
                {"heading": "Draft", "body": "A short draft stays on this sequence."}
            ],
        }
    )
    save_state(seq, state)


def open_sequence(module=None) -> str:
    """Draft and confirm sequence 1 (or the next id) and return its sequence id."""
    from essay_writer.projects import essay_sequence_new

    module = ESSAY if module is None else module
    draft = essay_sequence_new(module, "draft")
    if draft.get("ok") is not True:
        raise AssertionError(draft)
    opened = essay_sequence_new(module, "confirm")
    if opened.get("ok") is not True:
        raise AssertionError(opened)
    return opened["sequence_id"]


def mac_handoff_sequence_dir(handoff_root, seq: str):
    """Per-sequence folder under a remembered Mac handoff root (Essay Bot or ESSAY_WRITER_MAC_DIR)."""
    from pathlib import Path

    from essay_writer.paths import module_code

    return Path(handoff_root) / module_code(seq) / seq


ESSAY = "MOD1004AA"
OTHER = "MOD1011AA"
TOPIC = "How do chokepoints constrain the corridor?"
TEXT = (
    "Smith, J. (2020) Chokepoints and crude.\n"
    "The Strait handles a large share of flows.\n"
)

REPORT_HEADINGS = (
    "Introduction",
    "Supply chain context",
    "Analysis and findings",
    "Conclusion",
)


def report_sections(
    intro: str,
    context: str,
    analysis: str,
    conclusion: str,
) -> list[dict[str, str]]:
    return [
        {"heading": "Introduction", "body": intro},
        {"heading": "Supply chain context", "body": context},
        {"heading": "Analysis and findings", "body": analysis},
        {"heading": "Conclusion", "body": conclusion},
    ]


def write_upload(root, essay_id=ESSAY, name="smith.md", text=TEXT):
    folder = root / "uploads" / essay_id
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(text, encoding="utf-8")
    return folder / name


def source(essay_id=ESSAY, name="smith.md"):
    return {
        "id": "src-1",
        "origin": "upload",
        "locator": f"uploads/{essay_id}/{name}",
        "author": "Smith, J.",
        "year": "2020",
        "title": "Chokepoints and crude",
        "quote": "The Strait handles a large share of flows.",
    }


def pack(essay_id=ESSAY, **overrides):
    cite = "(Smith, 2020)"
    body = {
        "essay_id": essay_id,
        "title": "Chokepoints on the corridor",
        "referencing": "harvard",
        "assessment": "Individual report",
        "conclusion": "noted",
        "sections": report_sections(
            f"The corridor depends on a narrow strait {cite}.",
            f"One named supply chain on the corridor is in scope for this report {cite}.",
            f"The Strait handles a large share of flows through that chain {cite}.",
            f"The Strait handles a large share of flows {cite}.",
        ),
        "sources": [source(essay_id)],
    }
    if essay_id == OTHER:
        body["assessment"] = "Individual essay"
        body["sections"] = [
            {
                "heading": "Introduction",
                "body": f"The corridor depends on a narrow strait {cite}.",
            },
            {
                "heading": "Conclusion",
                "body": f"The Strait handles a large share of flows {cite}.",
            },
        ]
    body.update(overrides)
    return body


CLARIFY_OPEN = {
    "objective": {"leave_open": True},
    "background": {"leave_open": True},
    "issues": {"leave_open": True},
    "guidance": {"leave_open": True},
}
