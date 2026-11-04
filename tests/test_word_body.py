import re
import zipfile

from helpers import (
    ESSAY,
    OTHER,
    REPORT_HEADINGS,
    TOPIC,
    open_sequence,
    pack,
    source,
    write_upload,
)

from essay_writer.research import essay_research_summary
from essay_writer.validate import essay_pack_validate
from essay_writer.word import essay_pack_render_word


def _confirm_pipeline(workspace, essay_id=ESSAY, body=None):
    write_upload(workspace, essay_id=essay_id)
    seq = open_sequence(essay_id)
    essay_research_summary(seq, TOPIC, "draft", [source(essay_id)])
    essay_research_summary(seq, TOPIC, "confirm", [source(essay_id)])
    payload = body or pack(essay_id)
    essay_pack_validate(seq, payload, "draft")
    essay_pack_validate(seq, payload, "confirm")
    preview = essay_pack_render_word(seq, payload, "draft")
    written = essay_pack_render_word(seq, payload, "confirm")
    path = workspace / "Essay-writer" / essay_id / "sequences" / "1" / "output" / f"{seq}.docx"
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
    return preview, written, xml, path


def _plain_text(xml: str) -> str:
    return re.sub(r"<[^>]+>", "", xml)


def test_docx_layout_preview_matches_file(workspace):
    preview, written, xml, _path = _confirm_pipeline(workspace)
    assert written["wrote"] is True
    assert preview["wrote"] is False
    assert preview["headings"] == list(REPORT_HEADINGS)
    assert preview["genre"] == "report"
    for heading in preview["headings"]:
        assert heading in xml
    assert preview["cover"] == written["cover"]
    for line in preview["cover"]:
        assert line in xml
    for ref in preview["references"]:
        assert ref in _plain_text(xml)
    assert "References" in xml
    assert "Conclusion: noted" in xml
    assert "Student" not in xml
    assert "doi:" not in xml
    assert 'w:ascii="Arial"' in xml or "Arial" in xml
    assert 'w:val="Heading1"' in xml
    assert 'w:line="360"' in xml or 'w:lineRule="auto"' in xml
    assert 'w:firstLine="-720"' in xml or 'w:firstLine="-7200"' in xml or 'w:left="720"' in xml
    footer = zipfile.ZipFile(_path).read("word/footer1.xml").decode("utf-8")
    assert "PAGE" in footer


def test_open_conclusion_cover_line(workspace):
    open_pack = pack(conclusion="open")
    preview, _, xml, _ = _confirm_pipeline(workspace, body=open_pack)
    assert "Conclusion: open — not a settled finding" in preview["cover"]
    assert "Conclusion: open — not a settled finding" in xml


def test_report_refuses_essay_only_headings(workspace):
    write_upload(workspace)
    seq = open_sequence()
    essay_research_summary(seq, TOPIC, "draft", [source()])
    essay_research_summary(seq, TOPIC, "confirm", [source()])
    essay_only = pack(
        sections=[
            {"heading": "Introduction", "body": "The corridor depends on a narrow strait (Smith, 2020)."},
            {"heading": "Conclusion", "body": "The Strait handles a large share of flows (Smith, 2020)."},
        ],
    )
    result = essay_pack_validate(seq, essay_only, "draft")
    assert result["passed"] is False
    assert any(item["code"] == "genre" for item in result["blockers"])
    preview = essay_pack_render_word(seq, essay_only, "draft")
    assert preview["wrote"] is False


def test_section_plan_from_brief_is_enforced(workspace):
    write_upload(workspace)
    seq = open_sequence()
    essay_research_summary(seq, TOPIC, "draft", [source()])
    essay_research_summary(seq, TOPIC, "confirm", [source()])
    plan = ["Introduction", "Custom brief section", "Conclusion"]
    payload = pack(
        section_plan=plan,
        sections=[
            {"heading": "Introduction", "body": "Scope (Smith, 2020)."},
            {"heading": "Wrong heading", "body": "Detail (Smith, 2020)."},
            {"heading": "Conclusion", "body": "The Strait handles a large share of flows (Smith, 2020)."},
        ],
    )
    result = essay_pack_validate(seq, payload, "draft")
    assert result["passed"] is False
    assert any(item["code"] == "genre" for item in result["blockers"])


def test_word_count_uses_brief_citation_rule(workspace):
    write_upload(workspace, essay_id="MOD1011AA")
    write_upload(workspace, essay_id="MOD1008AA")
    essay_sections = {
        "sections": [
            {
                "heading": "Introduction",
                "body": "Flows matter (Smith, 2020) and trade shifts (Smith, 2020).",
            },
            {
                "heading": "Conclusion",
                "body": "The Strait handles a large share of flows (Smith, 2020).",
            },
        ],
    }
    report_sections = {
        "sections": [
            {"heading": "Introduction", "body": "Flows matter (Smith, 2020)."},
            {"heading": "Market analysis", "body": "Trade shifts matter (Smith, 2020)."},
            {"heading": "Conclusion", "body": "The Strait handles a large share of flows (Smith, 2020)."},
        ],
    }
    for essay_id, expected, sections in (
        ("MOD1011AA", 13, essay_sections),
        ("MOD1008AA", 19, report_sections),
    ):
        seq = open_sequence(essay_id)
        essay_research_summary(seq, TOPIC, "draft", [source(essay_id)])
        essay_research_summary(seq, TOPIC, "confirm", [source(essay_id)])
        payload = pack(essay_id, conclusion="open", **sections)
        report = essay_pack_validate(seq, payload, "draft")
        assert report["word_count"]["counted"] == expected


def test_cross_essay_pack_refused_on_word(workspace):
    write_upload(workspace)
    seq = open_sequence()
    essay_research_summary(seq, TOPIC, "draft", [source()])
    essay_research_summary(seq, TOPIC, "confirm", [source()])
    foreign = pack(OTHER)
    result = essay_pack_render_word(seq, foreign, "draft")
    assert result["ok"] is False
    assert any(item["code"] == "cross-essay" for item in result["blockers"])


def test_pdf_request_writes_nothing(workspace):
    write_upload(workspace)
    seq = open_sequence()
    essay_research_summary(seq, TOPIC, "draft", [source()])
    essay_research_summary(seq, TOPIC, "confirm", [source()])
    result = essay_pack_render_word(seq, pack(format="pdf"), "draft")
    assert result["refused"] == "word-only"
    assert result["wrote"] is False
    target = workspace / "Essay-writer" / ESSAY / "output" / f"{ESSAY}.docx"
    assert not target.exists()
    output = workspace / "Essay-writer" / ESSAY / "sequences" / "1" / "output"
    assert not (output / f"{seq}.docx").exists()
    assert not list(output.glob("*.pdf"))
