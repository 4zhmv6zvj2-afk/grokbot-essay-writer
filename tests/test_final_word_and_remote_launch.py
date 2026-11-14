"""A stored stage 10 reply does not write a missing final Word file again.

A web link inside a stage rule or a longer instruction is not a remote launch.
A command that is itself a remote or cloud launch is still refused.
"""

import copy

from docx import Document
from helpers import mac_handoff_sequence_dir, open_sequence, picked
from test_stage10_sequence_write import MODULE, NUMBER, _brief, _kick, _output, _pack, _park

import essay_writer.stage_hold as stage_hold
from essay_writer.brief_contract import remember_registration
from essay_writer.build_office import spawn_grok, stage_launch
from essay_writer.cursor_office import (
    REMOTE_CLOUD_BANNED,
    cursor_stage_launch,
    spawn_agent,
    start_stage_mid,
)
from essay_writer.late_chain import finish_stage_reply
from essay_writer.paths import work_dir
from essay_writer.specialists.grok_bot import basics_pass_lines
from essay_writer.stage_llm import stage_settings
from essay_writer.stage_state import load_pointer
from essay_writer.stage_track import essay_stage
from essay_writer.state import load_state, save_state

MISSING = "The final Word file is missing."
LINK = (
    "A later rule may mention https://library.example.edu/harvard or a notes://handbook spelling."
)


class _Proc:
    pid = 2_000_000_001


class _Launcher:
    def __init__(self):
        self.calls: list[list[str]] = []

    def __call__(self, argv):
        self.calls.append(list(argv))
        return _Proc(), None


def _copied(documents, seq: str):
    return mac_handoff_sequence_dir(documents, seq) / f"{MODULE}-final.docx"


def _sequence_final(seq: str):
    return work_dir(seq) / "output" / f"{MODULE}-10" / f"{MODULE}-final.docx"


def _stamp(path):
    return path.read_bytes(), path.stat().st_mtime_ns


def _text(path):
    return "\n".join(paragraph.text for paragraph in Document(str(path)).paragraphs)


def _confirm(monkeypatch, documents, *, mounted: bool) -> tuple[str, dict]:
    if mounted:
        monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", str(documents))
    else:
        monkeypatch.setenv("ESSAY_WRITER_MAC_DIR", "open")
    _brief()
    seq = _kick()["sequence_id"]
    assert remember_registration(seq, NUMBER) == NUMBER
    state = load_state(seq)
    state["saved_pack"] = _pack(seq)
    save_state(seq, state)
    _park(seq)
    seen = {"before_close": False}
    real = stage_hold._commit_pointer

    def watching(essay_id, base, proposed, *, note=None, note_text=None):
        if proposed.get("closed") is True:
            assert base.get("closed") is not True
            if mounted:
                assert _copied(documents, seq).is_file()
            assert _output(seq).is_file()
            seen["before_close"] = True
        return real(essay_id, base, proposed, note=note, note_text=note_text)

    monkeypatch.setattr(stage_hold, "_commit_pointer", watching)
    look = "\n".join(basics_pass_lines(seq)) + "\nThe final file is ready."
    draft = essay_stage(seq, "10", "draft", look)
    assert draft["ok"] is True, draft
    saved = essay_stage(seq, "10", "confirm", **picked(draft))
    assert seen["before_close"] is True
    monkeypatch.setattr(stage_hold, "_commit_pointer", real)
    return seq, saved


def _forbid_rewrite(monkeypatch) -> None:
    def forbid(*_args, **_kwargs):
        raise AssertionError("the final Word file was written again")

    monkeypatch.setattr("essay_writer.word.write_docx", forbid)


def _says_missing(body: dict) -> None:
    heard = " ".join(str(body.get(key) or "") for key in ("reason", "next", "final_word"))
    assert MISSING in heard
    assert body.get("ok") is False


def test_stage10_confirm_writes_the_copy_before_the_pointer_closes(
    workspace, monkeypatch, tmp_path
):
    """Confirm writes and copies the final Word file, then the pointer closes."""
    documents = tmp_path / "Documents"
    seq, saved = _confirm(monkeypatch, documents, mounted=True)
    assert saved["ok"] is True, saved
    assert saved["stored"] is True
    assert saved["closed"] is True
    assert load_pointer(seq)["closed"] is True
    assert "10" in load_pointer(seq)["saved"]
    final = saved["final_word"]
    assert final["copied"] is True
    assert "copied" in final
    assert MISSING not in str(saved.get("next") or "")
    copied = _copied(documents, seq)
    assert copied.is_file()
    assert _output(seq).is_file()
    assert _sequence_final(seq).is_file()
    assert _text(copied) == _text(_output(seq))
    assert _sequence_final(seq).read_bytes() == _output(seq).read_bytes()
    assert "Registration number:" in _text(copied)


def test_a_later_visit_leaves_a_present_final_word_file(workspace, monkeypatch, tmp_path):
    """The copied file stays as it is when a later visit finds it still there."""
    documents = tmp_path / "Documents"
    seq, saved = _confirm(monkeypatch, documents, mounted=True)
    copied = _copied(documents, seq)
    stamps = {
        "copied": _stamp(copied),
        "sequence": _stamp(_output(seq)),
        "final": _stamp(_sequence_final(seq)),
    }
    _forbid_rewrite(monkeypatch)
    visit = essay_stage(seq, "10", "draft", "A later visit.")
    assert visit["ok"] is False
    assert MISSING not in str(visit.get("reason") or "")
    again = essay_stage(seq, "10", "confirm")
    assert again["ok"] is False
    assert MISSING not in str(again.get("reason") or "")
    emitted = finish_stage_reply(copy.deepcopy(saved), seq, "10", armed=False)
    assert emitted["ok"] is True, emitted
    assert MISSING not in str(emitted.get("next") or "")
    assert _stamp(copied) == stamps["copied"]
    assert _stamp(_output(seq)) == stamps["sequence"]
    assert _stamp(_sequence_final(seq)) == stamps["final"]


def test_a_missing_copied_final_is_not_written_again(workspace, monkeypatch, tmp_path):
    """After the copy is gone, a later visit and a later reply stop and do not write it."""
    documents = tmp_path / "Documents"
    seq, saved = _confirm(monkeypatch, documents, mounted=True)
    copied = _copied(documents, seq)
    sequence = _stamp(_output(seq))
    final = _stamp(_sequence_final(seq))
    copied.unlink()
    _forbid_rewrite(monkeypatch)
    for phase in ("draft", "confirm"):
        visit = essay_stage(seq, "10", phase, "A later visit.")
        _says_missing(visit)
        assert not copied.exists()
        assert _stamp(_output(seq)) == sequence
        assert _stamp(_sequence_final(seq)) == final
    emitted = finish_stage_reply(copy.deepcopy(saved), seq, "10", armed=False)
    _says_missing(emitted)
    assert not copied.exists()
    assert _stamp(_output(seq)) == sequence
    assert _stamp(_sequence_final(seq)) == final


def test_a_stored_reply_with_no_copy_result_is_not_written_again(workspace, monkeypatch, tmp_path):
    """A stored stage 10 reply with no copy result does not write the Word file."""
    documents = tmp_path / "Documents"
    seq, saved = _confirm(monkeypatch, documents, mounted=True)
    copied = _copied(documents, seq)
    sequence = _stamp(_output(seq))
    final = _stamp(_sequence_final(seq))
    place = saved["final_word"]["place"]
    copied_stamp = _stamp(copied)
    _forbid_rewrite(monkeypatch)
    for body in (
        {"ok": True, "stored": True, "next": "Kept."},
        {"ok": True, "stored": True, "final_word": {"ok": True, "place": place}},
    ):
        emitted = finish_stage_reply(body, seq, "10", armed=True)
        _says_missing(emitted)
        assert _stamp(copied) == copied_stamp
        assert _stamp(_output(seq)) == sequence
        assert _stamp(_sequence_final(seq)) == final


def test_an_unmounted_final_word_is_not_rewritten(workspace, monkeypatch, tmp_path):
    """Documents left unmounted keep that reply. The sequence file is not written again."""
    documents = tmp_path / "Documents"
    seq, saved = _confirm(monkeypatch, documents, mounted=False)
    assert saved["ok"] is True, saved
    assert saved["final_word"]["copied"] is False
    assert "copied" in saved["final_word"]
    assert saved["final_word"]["reason"] == "mac-not-mounted"
    assert "this chat" in saved["next"]
    assert MISSING not in saved["next"]
    sequence = _stamp(_output(seq))
    _forbid_rewrite(monkeypatch)
    emitted = finish_stage_reply(copy.deepcopy(saved), seq, "10", armed=False)
    assert emitted["final_word"]["reason"] == "mac-not-mounted"
    assert emitted["final_word"]["copied"] is False
    assert "copied" in emitted["final_word"]
    assert MISSING not in str(emitted.get("next") or "")
    assert "this chat" in emitted["next"]
    assert _stamp(_output(seq)) == sequence
    assert not _copied(documents, seq).exists()
    visit = essay_stage(seq, "10", "confirm")
    assert visit["ok"] is False
    assert MISSING not in str(visit.get("reason") or "")
    assert _stamp(_output(seq)) == sequence


def _with_link(command: list[str]) -> list[str]:
    """Put a web link in the rules text, or in a longer instruction token."""
    command = list(command)
    if "--rules" in command:
        index = command.index("--rules") + 1
        command[index] = f"{command[index]}\n{LINK}"
        return command
    return [*command, LINK]


def _patch_binaries(monkeypatch) -> _Launcher:
    launch = _Launcher()
    monkeypatch.setattr("essay_writer.setup.cursor_cli_binary", lambda: "/bin/agent")
    monkeypatch.setattr("essay_writer.setup.grokbuild_binary", lambda: "/bin/grok")
    monkeypatch.setattr("essay_writer.mid_spawn.open_mid_child", launch)
    return launch


def test_a_link_in_a_rule_or_instruction_is_not_a_remote_launch(workspace, monkeypatch):
    """spawn_agent and spawn_grok start when a rule or instruction only mentions a link."""
    launch = _patch_binaries(monkeypatch)
    cursor = _with_link(cursor_stage_launch("6")["command"])
    grok = _with_link(stage_launch("6")["command"])
    assert LINK in cursor[-1]
    assert "https://library.example.edu/harvard" in grok[grok.index("--rules") + 1]
    assert "notes://handbook" in grok[grok.index("--rules") + 1]
    started_agent = spawn_agent(cursor, launch=launch)
    started_grok = spawn_grok(grok, launch=launch)
    spelling = spawn_agent(
        ["agent", "--model", "grok-4.7-high", "notes://handbook"],
        launch=launch,
    )
    named = spawn_agent(["agent", "--model", "cloud-agent"], launch=launch)
    named_equals = spawn_agent(["agent", "--model=cloud-agent"], launch=launch)
    named_grok = spawn_grok(
        ["grok", "--model", "cloud-agent", "--effort", "high"],
        launch=launch,
    )
    for started in (started_agent, started_grok, spelling, named, named_equals, named_grok):
        assert started["started"] is True, started
        assert started["reason"] == ""
        assert started["reason"] != REMOTE_CLOUD_BANNED
        assert started["reason"] != "not-grok-build"
    assert launch.calls
    seq = open_sequence()
    other = open_sequence()
    cursor_start = start_stage_mid(
        seq, "8", launch={"command": cursor, "settings": stage_settings("8")}
    )
    grok_start = start_stage_mid(
        other, "8", launch={"command": grok, "settings": stage_settings("8")}
    )
    assert cursor_start["started"] is True, cursor_start
    assert grok_start["started"] is True, grok_start
    assert cursor_start["reason"] != REMOTE_CLOUD_BANNED
    assert grok_start["reason"] != "not-grok-build"
    assert "https://library.example.edu/harvard" in " ".join(cursor_start["command"])
    assert "notes://handbook" in " ".join(grok_start["command"])
    assert "https://library.example.edu/harvard" in " ".join(grok_start["command"])


def test_a_remote_launch_target_is_still_refused(monkeypatch):
    """A bare link, an endpoint URL, or a cloud flag is refused before the binary starts."""
    launch = _patch_binaries(monkeypatch)
    agent_targets = [
        ["agent", "https://cursor.com/agents/bc-1"],
        ["agent", "https://library.example.edu/job"],
        ["agent", "http://library.example.edu/job"],
        ["agent", "cursor.com/agents/bc-1"],
        ["agent", "--endpoint", "https://remote.example"],
        ["agent", "--endpoint=https://remote.example"],
        ["agent", "-e", "https://remote.example"],
        ["agent", "-e", "http://remote.example"],
        ["agent", "--cloud"],
        ["agent", "--remote"],
        ["agent", "--cloud-agent"],
        ["agent", "--remote-agent"],
        ["agent", "--cloud-agent=true"],
        ["agent", "--remote-agent=1"],
    ]
    grok_targets = [
        ["grok", "https://library.example.edu/job"],
        ["grok", "http://library.example.edu/job"],
        ["grok", "cursor.com/agents/bc-1"],
        ["grok", "--endpoint", "https://remote.example"],
        ["grok", "-e", "https://remote.example"],
        ["grok", "--cloud"],
        ["grok", "--remote"],
        ["grok", "--cloud-agent"],
        ["grok", "--remote-agent"],
    ]
    for command in agent_targets:
        refused = spawn_agent(command, launch=launch)
        assert refused["started"] is False, command
        assert refused["reason"] == REMOTE_CLOUD_BANNED
    for command in grok_targets:
        refused = spawn_grok(command, launch=launch)
        assert refused["started"] is False, command
        assert refused["reason"] == "not-grok-build"
    assert launch.calls == []
