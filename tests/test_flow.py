import zipfile

from helpers import ESSAY, OTHER, TOPIC, open_sequence, pack, source, write_upload

from essay_writer.originals import essay_originals
from essay_writer.research import essay_research_summary
from essay_writer.shelf import essay_shelf_get, essay_shelf_put
from essay_writer.validate import essay_pack_validate
from essay_writer.word import essay_pack_render_word


def test_research_validate_word_and_local_shelf(workspace):
    write_upload(workspace)
    write_upload(workspace, name="unread.md", text="Not gathered.\n")
    seq = open_sequence()
    listed = essay_originals(ESSAY, "list")
    assert {item["name"] for item in listed["uploads"]} == {"smith.md", "unread.md"}

    draft = essay_research_summary(seq, TOPIC, "draft", [source()])
    assert draft["ok"] is True
    assert draft["stored"] is False
    assert any(item.endswith("unread.md") for item in draft["not_opened"])
    assert draft["resolvers_called"] == []
    assert all("doi" in gap or "pages" in gap or "accessed" in gap for gap in draft["gaps"])

    confirmed = essay_research_summary(seq, TOPIC, "confirm", [source()])
    assert confirmed["stored"] is True

    checked = essay_pack_validate(seq, pack(), "draft")
    assert checked["passed"] is True
    assert checked["stored"] is False
    recorded = essay_pack_validate(seq, pack(), "confirm")
    assert recorded["recorded_pass"] is True

    preview = essay_pack_render_word(seq, pack(), "draft")
    assert preview["wrote"] is False
    assert "Conclusion: noted" in preview["cover"]
    target = workspace / "Essay-writer" / ESSAY / "sequences" / "1" / "output" / f"{seq}.docx"
    assert not target.exists()
    assert not (workspace / "Essay-writer" / ESSAY / "output" / f"{ESSAY}.docx").exists()

    written = essay_pack_render_word(seq, pack(), "confirm")
    assert written["wrote"] is True
    assert target.is_file()
    xml = zipfile.ZipFile(target).read("word/document.xml").decode("utf-8")
    assert "References" in xml
    assert "Smith, J." in xml
    assert "Conclusion: noted" in xml
    assert "Student" not in xml
    assert "doi:" not in xml

    shelf_draft = essay_shelf_put(seq, pack(), "draft")
    assert shelf_draft["wrote"] is False
    assert shelf_draft["path"] == f"Essay-writer/{ESSAY}/sequences/1/shelf/{shelf_draft['pack_id']}.json"
    assert not (workspace / "Essay-writer" / ESSAY / "shelf").exists()
    shelf_done = essay_shelf_put(seq, pack(), "confirm")
    assert shelf_done["stored"] is True
    assert shelf_done["path"] == shelf_draft["path"]
    other = essay_shelf_get(OTHER, shelf_done["pack_id"], "draft")
    assert other["ok"] is False
    label = essay_shelf_get(seq, shelf_done["pack_id"], "draft")
    assert "pack" not in label
    full = essay_shelf_get(seq, shelf_done["pack_id"], "confirm")
    assert full["pack"]["title"] == pack()["title"]


def test_research_pack_on_confirm_with_fixture_lookup(workspace, monkeypatch):
    from essay_writer.resolvers import FIXTURE_TITLE

    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "fixture")
    text = (
        f"Smith, J. (2020) {FIXTURE_TITLE}.\n"
        "The Strait handles a large share of flows.\n"
    )
    write_upload(workspace, text=text)
    seq = open_sequence()
    payload = source()
    payload["title"] = FIXTURE_TITLE
    essay_research_summary(seq, TOPIC, "draft", [payload])
    confirmed = essay_research_summary(seq, TOPIC, "confirm", [payload])
    assert confirmed["stored"] is True
    assert confirmed["sources"][0]["doi"] == "10.5555/fixture-chokepoint"
    assert confirmed["research_pack"]["resolvers_called"]


def test_pdf_is_refused(workspace):
    write_upload(workspace)
    seq = open_sequence()
    essay_research_summary(seq, TOPIC, "draft", [source()])
    essay_research_summary(seq, TOPIC, "confirm", [source()])
    result = essay_pack_render_word(seq, pack(format="pdf"), "draft")
    assert result["refused"] == "word-only"
    assert result["wrote"] is False
