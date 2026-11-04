"""First-run blockers."""

import json
import zipfile
from pathlib import Path

from helpers import ESSAY, open_sequence, picked

from essay_writer.first_run import (
    attach_build_mcp,
    attach_custom_mcp,
    mcp_launch_command,
)
from essay_writer.gates import essay_gates
from essay_writer.health import essay_health
from essay_writer.intake import essay_intake
from essay_writer.originals import essay_originals
from essay_writer.paths import student_chat_path
from essay_writer.setup import essay_setup
from essay_writer.stage_llm import brief_genre
from essay_writer.stage_track import essay_stage, load_pointer
from essay_writer.state import load_state, save_state

MODULE = "RPT6001AA"
BRIEF = "\n".join(
    [
        "Genre: report",
        "Database: council published spreadsheet",
        "Word count: 800 words (720 to 880).",
        "In-text citations count.",
        "A public annual report should include the recycling figure an opened source states.",
    ]
) + "\n"


def _gate(report: dict, number: int) -> dict:
    return next(item for item in report["gates"] if item["gate"] == number)


def _save(seq: str, stage: str, look: str) -> dict:
    draft = essay_stage(seq, stage, "draft", look)
    assert draft["ok"] is True, draft
    saved = essay_stage(seq, stage, "confirm", look, **picked(draft))
    assert saved["ok"] is True, saved
    return saved


def test_mcp_command_is_absolute_when_the_bare_name_is_off_path(tmp_path, monkeypatch):
    import sysconfig

    home = tmp_path / "home"
    script = home / ".local" / "bin" / "essay-writer"
    script.parent.mkdir(parents=True)
    script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    script.chmod(0o755)
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.setattr(sysconfig, "get_path", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("essay_writer.first_run.shutil.which", lambda _name: None)

    command = mcp_launch_command()
    assert command == str(script.resolve())
    assert command != "essay-writer"
    assert Path(command).is_file()

    project = tmp_path / "project"
    project.mkdir()
    def enable(name):
        return {"identifier": name, "enabled": False}
    cursor = attach_custom_mcp(project, enable=enable)
    assert cursor["ok"] is True
    written = json.loads((project / ".cursor" / "mcp.json").read_text(encoding="utf-8"))
    assert written["mcpServers"]["essay-writer"]["command"] == command
    assert written["mcpServers"]["essay-writer"]["args"] == []

    build = attach_build_mcp(project, reviewer=True, enable=enable)
    text = Path(build["project_config"]).read_text(encoding="utf-8")
    assert f'command = "{command}"' in text
    assert 'command = "essay-writer"' not in text
    assert text.count(f'command = "{command}"') == 2
    assert 'args = ["--reviewer"]' in text


def test_bare_mcp_name_stays_when_the_script_is_already_on_path(monkeypatch):
    monkeypatch.setattr(
        "essay_writer.first_run.shutil.which",
        lambda name: "/usr/bin/essay-writer" if name == "essay-writer" else None,
    )
    assert mcp_launch_command() == "essay-writer"


def test_setup_confirm_names_distinct_folders_and_health_uses_the_app(tmp_path, monkeypatch):
    monkeypatch.delenv("ESSAY_WRITER_ROOT", raising=False)
    cloud = tmp_path / "cloud"
    cloud.mkdir()
    monkeypatch.setattr("essay_writer.paths.CLOUD_WORKSPACE", cloud)
    essay_setup(confirmPhase="draft", acknowledge_skipped_searches=True)
    confirmed = essay_setup(confirmPhase="confirm", acknowledge_skipped_searches=True)
    assert confirmed["ok"] is True
    named = {confirmed["app"], confirmed["kb1"], confirmed["setup"]}
    assert len(named) == 3
    for value in (confirmed["app"], confirmed["app_path"], confirmed["kb1"], confirmed["setup"]):
        assert value != "the cloud computer"
        assert value != "open"
    assert confirmed["app"].endswith("Essay-writer/app")
    assert confirmed["app_path"].endswith("Essay-writer/app")
    assert confirmed["kb1"].endswith("Essay-writer/KB1")
    assert confirmed["setup"].endswith("setup.json")

    report = essay_health()
    app = (cloud / "Essay-writer" / "app").resolve()
    assert report["app_path"] == str(app)
    assert report["app_path"] != "open"


def test_cloud_paths_stay_distinct_and_internal_volume_stays_hidden():
    assert student_chat_path("/workspace/Essay-writer/app") == "Essay-writer/app"
    assert student_chat_path("/workspace/Essay-writer/KB1") == "Essay-writer/KB1"
    assert student_chat_path("/workspace/Essay-writer/setup.json") == "Essay-writer/setup.json"
    spoken = {
        student_chat_path("/workspace/Essay-writer/app"),
        student_chat_path("/workspace/Essay-writer/KB1"),
        student_chat_path("/workspace/Essay-writer/setup.json"),
    }
    assert len(spoken) == 3
    assert "the cloud computer" not in spoken
    assert student_chat_path("/Volumes/ResearchDrive/app") == "a folder you named on this computer"


def test_intake_files_brief_md_with_a_word_count_originals_can_read(workspace):
    holding = workspace / "unassigned"
    holding.mkdir()
    (holding / "brief.md").write_text(BRIEF, encoding="utf-8")
    draft = essay_intake("brief.md", "draft", MODULE)
    assert draft["ok"] is True
    assert draft["kind"] == "brief"
    assert draft["summary"]["current_words"] == len(BRIEF.split())
    assert draft["summary"]["current_words"] > 0
    filed = essay_intake("brief.md", "confirm", MODULE)
    assert filed["ok"] is True
    assert filed["path"] == f"Essay-writer/{MODULE}/brief.md"
    slot = workspace / "Essay-writer" / MODULE / "brief.md"
    assert slot.is_file()
    assert slot.read_text(encoding="utf-8") == BRIEF
    assert not (workspace / "uploads" / MODULE / "brief.md").exists()
    listed = essay_originals(MODULE, "list")
    assert listed["brief"]
    assert listed["brief"][0]["name"] == "brief.md"
    assert "council published spreadsheet" in listed["databases"]["names"]
    opened = essay_originals(MODULE, "read", name="brief.md", kind="brief")
    assert opened["ok"] is True
    assert "Genre: report" in opened["text"]
    assert "council published spreadsheet" in opened["text"]


def test_brief_genre_and_word_band_set_one_label_and_gates(workspace):
    folder = workspace / "Essay-writer" / MODULE
    folder.mkdir(parents=True)
    (folder / "brief.md").write_text(BRIEF, encoding="utf-8")
    seq = open_sequence(MODULE)
    assert brief_genre(seq) == "report"
    from essay_writer.specialists.grok_bot import basics_pass_lines

    prefix = "\n".join(basics_pass_lines(seq))
    stage_one = essay_stage(seq, "1", "draft", prefix + "\nThe task is a short public report.")
    assert stage_one["confirm_line"] == (
        "Confirm to save the final look and go to **Stage 2 — Establish purpose and scope**."
    )
    assert "Essay: Establish a thesis" not in stage_one["confirm_line"]
    _save(seq, "1", prefix + "\nThe task is a short public report.")
    stage_two = essay_stage(
        seq,
        "2",
        "draft",
        prefix + "\nPurpose is the recycling report. Scope is household figures an opened source states.",
    )
    assert stage_two["stage_title"] == "Establish purpose and scope"
    assert "Write an essay plan" not in stage_two["stage_title"]
    essay_stage(
        seq,
        "2",
        "confirm",
        prefix + "\nPurpose is the recycling report. Scope is household figures an opened source states.",
        **picked(stage_two),
    )
    stage_three = essay_stage(
        seq,
        "3",
        "draft",
        prefix
        + "\nThe plan follows the sections named in the brief, including the recycling figure in the public report.",
    )
    assert stage_three["stage_title"] == "Write a report plan"

    missing = essay_gates(seq)
    assert "missing" in _gate(missing, 2)["reason"].casefold()
    assert "does not match" not in _gate(missing, 2)["reason"].casefold()
    assert _gate(missing, 4)["passed"] is True
    band = _gate(missing, 8)
    assert "720" in band["reason"]
    assert "880" in band["reason"]
    assert "No word band" not in band["reason"]
    inside = essay_gates(seq, body=" ".join(["household"] * 800))
    assert _gate(inside, 8)["passed"] is True
    assert "720–880" in _gate(inside, 8)["reason"]
    mismatch = essay_gates(seq, {"essay_id": "MOD1011AA", "genre": "essay"})
    assert "does not match" in _gate(mismatch, 2)["reason"]


def test_stage_4a_confirm_needs_sources_and_4b_does_not_invent_a_download_run(workspace):
    seq = open_sequence(MODULE)
    for stage, look in (
        ("1", "The task is a short public report."),
        ("2", "Purpose and scope stay with the brief."),
        ("3", "The plan names the brief sections."),
    ):
        _save(seq, stage, look)
    drafted = essay_stage(seq, "4a", "draft", "No source has been opened. The annotated list is empty.")
    assert drafted["ok"] is True
    folder = workspace / "Essay-writer" / MODULE / "sequences" / "1"
    assert not (folder / "download-run.json").exists()
    refused = essay_stage(
        seq, "4a", "confirm", "No source has been opened. The annotated list is empty.", **picked(drafted)
    )
    assert refused["ok"] is False
    assert refused.get("advanced") is False
    assert load_pointer(seq)["current"] == "4a"
    output = folder / "output"
    assert not (output / "annotation.docx").exists()
    assert not (output / "download-list.docx").exists()
    assert not (output / "papers.zip").exists()

    pointer = load_pointer(seq)
    pointer["current"] = "4b"
    pointer["saved"] = ["1", "2", "3", "4a"]
    (folder / "tracking" / "stage.json").write_text(json.dumps(pointer), encoding="utf-8")
    early = essay_stage(seq, "4b", "draft", "No paper note is written.")
    assert early["ok"] is True
    assert not (folder / "download-run.json").exists()
    assert "Option C" not in early["confirm_line"]
    assert "Stage 5" not in early["confirm_line"]


def test_stage_4a_confirm_delivers_the_bibliography_files(workspace):
    seq = open_sequence()
    for stage, look in (
        ("1", "The task is a report."),
        ("2", "Purpose and scope are locked."),
        ("3", "The plan holds the central theme."),
    ):
        _save(seq, stage, look)
    pdf = workspace / "uploads" / ESSAY / "paper.pdf"
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.write_bytes(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n")
    state = load_state(seq)
    state["research"]["summary"] = {
        "sources": [
            {
                "id": "src-pdf",
                "author": "Smith, J.",
                "year": "2020",
                "title": "Household recycling",
                "locator": f"uploads/{ESSAY}/paper.pdf",
            }
        ]
    }
    save_state(seq, state)
    look = "One gathered PDF is on the list."
    drafted = essay_stage(seq, "4a", "draft", look)
    saved = essay_stage(seq, "4a", "confirm", look, **picked(drafted))
    assert saved["ok"] is True, saved
    assert saved["advanced"] is True
    assert saved["current"] == "4b"
    folder = workspace / "Essay-writer" / ESSAY / "sequences" / "1"
    output = folder / "output"
    assert (output / "annotation.docx").is_file()
    assert (output / "download-list.docx").is_file()
    archive = zipfile.ZipFile(output / "papers.zip")
    assert "paper.pdf" in archive.namelist()
    assert saved["delivery"]["annotation"]["name"] == "annotation.docx"
    assert saved["delivery"]["download_list"]["name"] == "download-list.docx"
    assert "paper.pdf" in saved["delivery"]["papers_zip"]["entries"]

    follow = essay_stage(seq, "4b", "draft", "The read can start from the saved PDF.")
    assert follow["ok"] is True
    assert "Stage 5" in follow["confirm_line"]
    assert "Option C: Download leftovers first." in follow["confirm_line"]
    run = folder / "download-run.json"
    if run.is_file():
        data = json.loads(run.read_text(encoding="utf-8"))
        assert data.get("papers") or data.get("failures")


def test_health_shows_the_writing_stage_and_the_app_folder(workspace):
    seq = open_sequence()
    for stage, look in (
        ("1", "The task is a report."),
        ("2", "Purpose and scope are locked."),
        ("3", "The plan holds the central theme."),
    ):
        _save(seq, stage, look)
    early = essay_health()["packs"][0]
    assert early["writing_stage"] == "4a"
    assert early["writing_saved"] == ["1", "2", "3"]
    assert early["stage"] == "4a"

    from helpers import plant_gathered_source

    plant_gathered_source(seq)
    _save(seq, "4a", "One source is gathered.")
    report = essay_health()
    assert report["app_path"] == str(workspace.resolve())
    assert report["app_path"] != "open"
    pack = report["packs"][0]
    assert pack["writing_stage"] == "4b"
    assert pack["writing_saved"] == ["1", "2", "3", "4a"]
    assert pack["stage"] == "research"


def test_secret_card_speech_cites_the_provider_pages():
    from essay_writer.doors import DOORS
    from essay_writer.first_run import first_run_prompt
    from essay_writer.server import INSTRUCTIONS
    from essay_writer.setup import (
        CARD_RULES,
        CURSOR_SETUP_PROMPT,
        ORDINARY_SETUP_SPEECH,
        SETUP_PROMPT,
    )

    prompt = first_run_prompt()
    for text in (prompt, SETUP_PROMPT, CURSOR_SETUP_PROMPT, INSTRUCTIONS, CARD_RULES):
        assert "https://help.consensus.app/en/articles/16516328-the-consensus-api" in text
        assert "profile icon" in text
        assert "API & MCP Dashboard" in text
        assert "Keys and Clients" in text
        assert "New key" in text
        assert "https://docs.consensus.app/api-plans-and-access" in text
        assert "https://consensus.app/api-mcp" in text
        assert "programmatically searches academic research" in text
        assert "research step" in text
        assert "ESSAY_WRITER_CONSENSUS_PAID" in text
        assert "100,000" in text
        assert "https://unpaywall.org/products/api" in text
        assert "?email=YOUR_EMAIL" in text
        assert "problems with your scripts" in text
        assert "https://github.com/CrossRef/rest-api-doc/blob/master/README.md" in text
        assert "https://github.com/ourresearch/openalex-docs/blob/main/how-to-use-the-api/rate-limits-and-authentication.md" in text
        assert "Do not ask the user to edit a .env file." in text
        assert "LHS" not in text
        assert "never to email" in text
        assert "Unpaywall's own page promised never to email" in text
    assert "Ordinary setup collects the Consensus key" in prompt
    assert ORDINARY_SETUP_SPEECH in SETUP_PROMPT
    assert "secret card" in prompt
    assert "secret card" in SETUP_PROMPT
    assert "Grok Bot secret card" not in prompt
    assert "Grok Bot secret card" not in SETUP_PROMPT
    assert "Cursor" not in SETUP_PROMPT
    assert "Grok Build" not in SETUP_PROMPT
    setup = next(door["description"] for door in DOORS if door["tool"] == "essay.setup")
    assert CARD_RULES in setup
    assert "Grok Bot" not in setup
    assert ".env" in workflow_text()


def workflow_text() -> str:
    from pathlib import Path

    return (Path(__file__).resolve().parents[1] / "docs" / "workflow.md").read_text(encoding="utf-8")


def test_skip_needs_a_warning_confirm_and_the_plan_sets_the_paid_flag(tmp_path, monkeypatch):
    monkeypatch.setenv("ESSAY_WRITER_ROOT", str(tmp_path / "ledger"))
    app = tmp_path / "app"
    kb1 = tmp_path / "KB1"
    bare = essay_setup(app_path=str(app), kb1_path=str(kb1), confirmPhase="draft")
    assert bare["wrote"] is False
    warning = bare["search_warning"]
    assert "Consensus dig will not run" in warning
    assert "Unpaywall free PDF lookup will not run" in warning
    assert "OpenAlex still runs." in warning
    refused = essay_setup(app_path=str(app), kb1_path=str(kb1), confirmPhase="confirm")
    assert refused["ok"] is False
    assert refused["wrote"] is False
    assert refused["search_warning"] == warning
    assert not (tmp_path / "setup.json").exists()

    essay_setup(
        app_path=str(app),
        kb1_path=str(kb1),
        confirmPhase="draft",
        acknowledge_skipped_searches=True,
    )
    saved = essay_setup(
        app_path=str(app),
        kb1_path=str(kb1),
        confirmPhase="confirm",
        acknowledge_skipped_searches=True,
    )
    assert saved["ok"] is True
    assert saved["search_warning"] == warning

    key = "consensus-secret-value"
    missing_plan = essay_setup(
        app_path=str(app),
        kb1_path=str(kb1),
        confirmPhase="confirm",
        consensus_api_key=key,
        unpaywall_email="reader@example.com",
    )
    assert missing_plan["ok"] is False
    assert missing_plan["needs_consensus_plan"] is True
    assert key not in json.dumps(missing_plan)

    for plan, flag in (("free", "0"), ("Pro", "1"), ("teams", "1"), ("Deep", "1"), ("enterprise", "1")):
        essay_setup(
            app_path=str(app),
            kb1_path=str(kb1),
            confirmPhase="draft",
            consensus_api_key=key,
            unpaywall_email="reader@example.com",
            consensus_plan=plan,
        )
        kept = essay_setup(
            app_path=str(app),
            kb1_path=str(kb1),
            confirmPhase="confirm",
            consensus_api_key=key,
            unpaywall_email="reader@example.com",
            consensus_plan=plan,
        )
        assert kept["ok"] is True, kept
        assert kept["consensus_paid"] == flag
        assert key not in json.dumps(kept)
        secrets = json.loads((tmp_path / "setup.secrets.json").read_text(encoding="utf-8"))
        assert secrets["ESSAY_WRITER_CONSENSUS_PAID"] == flag
        assert "search_warning" not in kept

    email_only = essay_setup(
        app_path=str(app),
        kb1_path=str(kb1),
        confirmPhase="draft",
        unpaywall_email="reader@example.com",
    )
    assert "Consensus dig will not run" in email_only["search_warning"]
    assert "Unpaywall free PDF lookup will not run" not in email_only["search_warning"]
    key_only = essay_setup(
        app_path=str(app),
        kb1_path=str(kb1),
        confirmPhase="draft",
        consensus_api_key=key,
        consensus_plan="free",
    )
    assert "Unpaywall free PDF lookup will not run" in key_only["search_warning"]
    assert "Consensus dig will not run" not in key_only["search_warning"]
    assert key not in json.dumps(key_only)


def test_free_pdf_lookup_uses_the_doi_endpoint_and_openalex_best_oa_location():
    from essay_writer.resolvers import openalex_oa_url, unpaywall_doi_url

    url = unpaywall_doi_url("10.1038/nature12373", "reader@example.com")
    assert url.startswith("https://api.unpaywall.org/v2/")
    assert "/v2/search" not in url
    assert "email=reader%40example.com" in url
    pdf = openalex_oa_url(
        {
            "best_oa_location": {"pdf_url": "https://example.org/paper.pdf", "landing_page_url": "https://example.org/abs"},
            "primary_location": {"landing_page_url": "https://example.org/primary"},
        }
    )
    assert pdf == "https://example.org/paper.pdf"
