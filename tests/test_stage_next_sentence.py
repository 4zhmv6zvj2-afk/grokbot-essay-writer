"""One module stores the stage "what happens next" sentence."""

import ast
from pathlib import Path

import pytest
from helpers import open_sequence, picked, plant_gathered_source

from essay_writer.late_chain import STAGE6_OPEN, finish_stage_reply
from essay_writer.paths import work_dir
from essay_writer.server import HANDLERS
from essay_writer.shells import cursor_shell, front_office, mount_handler
from essay_writer.spine import advances_without_confirm
from essay_writer.stage_next import (
    mid_run_wait_next,
    rewrite_essay_stage_next,
    write_draft_stage_next,
)
from essay_writer.stage_track import essay_stage
from essay_writer.student_voice import speak

REPO = Path(__file__).resolve().parents[1]
PACKAGE = REPO / "src" / "essay_writer"
LAYERS = (
    "stage_state.py",
    "stage_note.py",
)
OWN_SENTENCE = {
    "dig.py": "This source card is not on disk yet. Choose Confirm to keep this step.",
    "shelf.py": "Say yes to keep this step. That stores this copy on this computer.",
    "setup.py": "Nothing has been written. Say yes to create these folders.",
    "intake.py": (
        "These loose files will move into unassigned/. "
        "READMEs stay. Nothing moves until you say yes."
    ),
    "review.py": "The review opened the saved Word file.",
    "projects.py": "Archiving this module hides every sequence. Say yes to continue.",
}
STAGE_ONE = "A full sentence for stage one."
DIGEST = "a" * 64


def _function(path: Path, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(name)


def _stores_next(node: ast.AST) -> bool:
    if isinstance(node, ast.Assign):
        return any(_target_is_next(target) for target in node.targets)
    if isinstance(node, ast.AnnAssign):
        return _target_is_next(node.target)
    if isinstance(node, ast.AugAssign):
        return _target_is_next(node.target)
    if isinstance(node, ast.Call):
        return any(keyword.arg == "next" for keyword in node.keywords)
    if isinstance(node, ast.Dict):
        return any(isinstance(key, ast.Constant) and key.value == "next" for key in node.keys)
    return False


def _target_is_next(target: ast.AST) -> bool:
    return (
        isinstance(target, ast.Subscript)
        and isinstance(target.slice, ast.Constant)
        and target.slice.value == "next"
        and isinstance(target.ctx, ast.Store)
    )


def _next_stores(tree: ast.AST) -> list[ast.AST]:
    return [node for node in ast.walk(tree) if _stores_next(node)]


def _imports_stage_track(source: str) -> bool:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and "stage_track" in node.module:
            return True
        if isinstance(node, ast.Import) and any(
            "stage_track" in alias.name for alias in node.names
        ):
            return True
    return False


def _idle(*_args: object, **_kwargs: object) -> dict[str, object]:
    return {"started": False, "reason": "absent", "command": []}


def _save_through(seq: str, stop: str) -> None:
    from essay_writer.writing_basics import STAGE_ORDER

    for stage in STAGE_ORDER:
        look = f"Saved from the brief. This sentence belongs to stage {stage}."
        draft = essay_stage(seq, stage, "draft", look)
        assert draft["ok"] is True, draft
        if stage == "4a":
            plant_gathered_source(seq)
        if stage == "5":
            assert draft["stored"] is True, draft
            if stage == stop:
                return
            continue
        saved = essay_stage(seq, stage, "confirm", look, **picked(draft))
        assert saved["stored"] is True, saved
        if stage == stop:
            return


@pytest.mark.parametrize(
    "case_id",
    [pytest.param("AC-ew-stage-next-1", id="AC-ew-stage-next-1")],
)
def test_one_module_stores_the_stage_sentence(case_id: str, workspace) -> None:
    """AC-ew-stage-next-1: After any essay.stage reply, the next sentence comes only from one writer."""
    del case_id, workspace
    tree = ast.parse((PACKAGE / "stage_next.py").read_text(encoding="utf-8"))
    owners = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _next_stores(node)
    }
    assert owners == {"write_stage_next"}
    seq = open_sequence()
    draft = essay_stage(seq, "1", "draft", STAGE_ONE)
    assert isinstance(draft.get("next"), str)
    assert draft["next"].startswith("Open the Confirm card to save Stage 1")
    saved = essay_stage(seq, "1", "confirm", STAGE_ONE, **picked(draft))
    assert saved["stored"] is True, saved
    assert isinstance(saved.get("next"), str)
    assert "Stage 2" in str(saved["next"])


@pytest.mark.parametrize(
    "case_id",
    [pytest.param("AC-ew-stage-next-2", id="AC-ew-stage-next-2")],
)
def test_stage_paths_leave_the_sentence_to_that_module(case_id: str) -> None:
    """AC-ew-stage-next-2: The reply, hold, landing, and finish paths no longer assign that sentence."""
    del case_id
    finish = _function(PACKAGE / "late_chain.py", "finish_stage_reply")
    assert _next_stores(finish) == []
    for name in ("stage_track.py",):
        assert _next_stores(ast.parse((PACKAGE / name).read_text(encoding="utf-8"))) == [], name
    from essay_writer.stage_next import ANSWER_NEXT, answer_next

    assert answer_next("stored", None) == ANSWER_NEXT


@pytest.mark.parametrize(
    "case_id",
    [pytest.param("AC-ew-stage-next-3", id="AC-ew-stage-next-3")],
)
def test_upload_ask_wait_and_card_lines_stay(case_id: str, workspace) -> None:
    """AC-ew-stage-next-3: The upload line, the stage 7 ask, the mid-run wait, and Confirm wording stripped during a mid-run still come from that one writer."""
    del case_id, workspace
    uploaded = {
        "ok": True,
        "stage": "4a",
        "next": "Open the Confirm card to save Stage 4a — Sources.",
        "download_check": {"matched": [{"name": "notes.txt"}]},
    }
    rewrite_essay_stage_next(uploaded, mid_started=True)
    assert uploaded["next"] == "I saved notes.txt. I am continuing this step."
    assert "confirm" not in str(uploaded["next"]).lower()

    asked = {
        "ok": True,
        "stage": "7",
        "card": {"kind": "confirm", "digest": DIGEST},
        "cardDigest": DIGEST,
        "next": (
            "Please answer these questions in this chat. 1. Is the claim fair? "
            "Then open the Confirm card to save Stage 7 — Analysis."
        ),
    }
    rewrite_essay_stage_next(asked, mid_started=True)
    assert "Please answer these questions" in str(asked["next"])
    assert "Confirm" in str(asked["next"])

    waiting = {
        "ok": True,
        "stage": "6",
        "next": "Open the Confirm card to save Stage 6 — Structure.",
    }
    rewrite_essay_stage_next(waiting, mid_started=True)
    assert waiting["next"] == mid_run_wait_next("6")
    assert "confirm" not in str(waiting["next"]).lower()

    stripped = {
        "ok": True,
        "stage": "4b",
        "next": "Don't click the Stage 4b Confirm card while this step is still running.",
    }
    rewrite_essay_stage_next(stripped, mid_started=True)
    assert stripped["next"] == mid_run_wait_next("4b")
    assert "confirm" not in str(stripped["next"]).lower()

    seq = open_sequence()
    draft_body = {
        "ok": True,
        "stage": "7",
        "stage_title": "Analysis",
        "questions": ["Is the claim fair?"],
    }
    write_draft_stage_next(draft_body, stage="7", essay_id=seq)
    assert "Please answer these questions" in str(draft_body["next"])
    assert "Is the claim fair?" in str(draft_body["next"])
    assert "Confirm" in str(draft_body["next"])

    live = essay_stage(seq, "1", "draft", STAGE_ONE)
    assert str(live["next"]).startswith("Open the Confirm card to save Stage 1")


@pytest.mark.parametrize(
    "case_id",
    [pytest.param("AC-ew-stage-next-4", id="AC-ew-stage-next-4")],
)
def test_other_doors_keep_their_own_sentence(case_id: str) -> None:
    """AC-ew-stage-next-4: Dig, shelf, setup, intake, review, and projects still write their own next sentence."""
    del case_id
    for name, sentence in OWN_SENTENCE.items():
        source = (PACKAGE / name).read_text(encoding="utf-8")
        assert sentence in source
        assert "stage_next" not in source
        assert _next_stores(ast.parse(source))


@pytest.mark.parametrize(
    "case_id",
    [pytest.param("AC-ew-stage-next-5", id="AC-ew-stage-next-5")],
)
def test_cleaning_does_not_pick_the_stage_sentence(case_id: str) -> None:
    """AC-ew-stage-next-5: Speech cleaning does not choose which stage sentence wins."""
    del case_id
    raw = "Open the saved copy."
    one = {"ok": True, "stage": "1", "next": raw, "reason": "Wait."}
    two = {"ok": True, "stage": "10", "next": raw, "reason": "Wait."}
    speak(one)
    speak(two)
    assert one["next"] == two["next"] == raw
    spoken = _function(PACKAGE / "student_voice.py", "speak")
    names = {node.id for node in ast.walk(spoken) if isinstance(node, ast.Name)}
    assert "stage" not in names
    stores = [node for node in _next_stores(spoken) if isinstance(node, ast.Assign)]
    assert len(stores) == 1
    value = stores[0].value
    assert isinstance(value, ast.Call)
    assert isinstance(value.func, ast.Name) and value.func.id == "say"


@pytest.mark.parametrize(
    "case_id",
    [pytest.param("AC-ew-stage-next-6", id="AC-ew-stage-next-6")],
)
def test_stage_split_and_stored_final_stay(case_id: str, workspace, monkeypatch) -> None:
    """AC-ew-stage-next-6: The stage split, stage 5 storing and opening stage 6 with no card, and a stored stage 10 that does not write the Word file again all stay."""
    del case_id
    for name in LAYERS:
        source = (PACKAGE / name).read_text(encoding="utf-8")
        assert not _imports_stage_track(source), name
    assert advances_without_confirm("5") == "6"
    finish = _function(PACKAGE / "late_chain.py", "finish_stage_reply")
    called = {node.id for node in ast.walk(finish) if isinstance(node, ast.Name)}
    assert "write_docx" not in called
    monkeypatch.setattr("essay_writer.cursor_office.start_stage_mid", _idle)
    monkeypatch.setattr("essay_writer.cursor_office.start_4a_research", _idle)
    seq = open_sequence()
    _save_through(seq, "4b")
    draft = essay_stage(seq, "5", "draft", "The first draft can start.")
    assert draft["stored"] is True, draft
    assert draft["current"] == "6"
    assert "card" not in draft
    assert draft["next"] == STAGE6_OPEN
    assert draft["chat"] == draft["next"]
    kept = workspace / "kept.docx"
    kept.write_bytes(b"kept")
    before = kept.read_bytes()
    output = work_dir(seq) / "output" / f"{seq}.docx"
    stored = finish_stage_reply(
        {
            "ok": True,
            "stored": True,
            "final_word": {"ok": True, "copied": True, "place": str(kept)},
        },
        seq,
        "10",
        armed=False,
    )
    assert stored["ok"] is True, stored
    assert kept.read_bytes() == before
    assert not output.exists()
    assert "keep a copy" in str(stored["next"]).lower()
    missing = finish_stage_reply(
        {
            "ok": True,
            "stored": True,
            "final_word": {"ok": True, "copied": True, "place": str(workspace / "gone.docx")},
        },
        seq,
        "10",
        armed=False,
    )
    assert missing["ok"] is False
    assert "missing" in str(missing["next"]).lower()
    assert not output.exists()


@pytest.mark.parametrize(
    "case_id",
    [pytest.param("AC-ew-stage-next-7", id="AC-ew-stage-next-7")],
)
def test_both_hosts_share_one_stage_reply(case_id: str, workspace) -> None:
    """AC-ew-stage-next-7: Cursor and Grok Build both read the same reply dict and show the same next sentence for the same essay.stage result. Build covered."""
    del case_id, workspace
    cursor_handlers = cursor_shell()["handlers"]
    office_handlers = front_office()["handlers"]
    assert cursor_handlers is office_handlers
    assert (
        cursor_handlers["essay.stage"] is office_handlers["essay.stage"] is HANDLERS["essay.stage"]
    )
    writer = (PACKAGE / "stage_next.py").read_text(encoding="utf-8")
    for token in ("SHELL_CURSOR", "SHELL_GROK", "spawn_agent", "spawn_grok"):
        assert token not in writer
    for name in ("cursor_office.py", "build_office.py"):
        assert "stage_next" not in (PACKAGE / name).read_text(encoding="utf-8")
    first = open_sequence()
    second = open_sequence()
    mounted = mount_handler("essay.stage")
    left = mounted(
        essay_id=first,
        stage="1",
        confirmPhase="draft",
        look=STAGE_ONE,
    )
    right = mounted(
        essay_id=second,
        stage="1",
        confirmPhase="draft",
        look=STAGE_ONE,
    )
    assert left["next"] == right["next"]
    assert str(left["next"]).startswith("Open the Confirm card to save Stage 1")
