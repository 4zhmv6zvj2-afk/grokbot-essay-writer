from helpers import CLARIFY_OPEN, ESSAY, TOPIC, open_sequence, source, write_upload

from essay_writer.health import essay_health
from essay_writer.research import essay_research_full, essay_research_summary


def _note(root, name="subject.md"):
    folder = root / "Essay-writer" / ESSAY / "kb1"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text("Local subject note. Not a citation by itself.\n", encoding="utf-8")
    return f"Essay-writer/{ESSAY}/kb1/{name}"


def test_health_lists_local_packs_only_from_disk(workspace):
    name = _note(workspace)
    report = essay_health()
    assert report["local_packs"] == [{"essay_id": ESSAY, "name": name}]


def test_full_refuses_an_invented_pack(workspace):
    write_upload(workspace)
    _note(workspace)
    seq = open_sequence()
    invented = essay_research_full(
        seq,
        TOPIC,
        "draft",
        [source()],
        clarify_context=CLARIFY_OPEN,
        packs=["HKIS Valuation Standards 2024"],
    )
    assert invented["ok"] is False
    assert invented["refused"] == "packs"
    assert invented["stored"] is False


def test_full_accepts_two_local_packs_and_not_three(workspace):
    write_upload(workspace)
    first = _note(workspace, "one.md")
    second = _note(workspace, "two.md")
    third = _note(workspace, "three.md")
    seq = open_sequence()
    opened = essay_research_full(
        seq,
        TOPIC,
        "draft",
        [source()],
        clarify_context=CLARIFY_OPEN,
        packs=[first, second],
        industry={"module": ESSAY},
        host_voice="third person",
    )
    assert opened["ok"] is True
    assert opened["stored"] is False
    assert [item["name"] for item in opened["packs"]] == [first, second]
    assert opened["not_evidence"]["industry"] == {"module": ESSAY}
    assert opened["sources"][0]["locator"].endswith("smith.md")
    assert all(item["evidence"] is False for item in opened["packs"])
    too_many = essay_research_full(
        seq,
        TOPIC,
        "draft",
        [source()],
        clarify_context=CLARIFY_OPEN,
        packs=[first, second, third],
    )
    assert too_many["refused"] == "packs"


def test_exclude_section_blocks_the_source(workspace):
    write_upload(workspace)
    seq = open_sequence()
    blocked = essay_research_summary(
        seq,
        TOPIC,
        "draft",
        [source()],
        exclude_section_ids=["src-1"],
    )
    assert blocked["refused"] == "exclude"
    assert blocked["stored"] is False


def test_industry_change_needs_a_fresh_draft(workspace):
    write_upload(workspace)
    kwargs = {
        "sources": [source()],
        "clarify_context": CLARIFY_OPEN,
        "industry": {"lane": "oil"},
    }
    seq = open_sequence()
    draft = essay_research_full(seq, TOPIC, "draft", **kwargs)
    assert draft["ok"] is True
    moved = essay_research_full(
        seq,
        TOPIC,
        "confirm",
        sources=kwargs["sources"],
        clarify_context=CLARIFY_OPEN,
        industry={"lane": "containers"},
    )
    assert moved["refused"] == "confirm"
    assert moved["stored"] is False
