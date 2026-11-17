"""Install notes live in FIRST-RUN. The friend prompt is local-only. Stable ids: AC1–AC4."""

import subprocess
from pathlib import Path

from essay_writer.first_run import (
    MAC_FOUR_WAY_CARD,
    first_run_prompt,
    package_root,
)

REPO = Path(__file__).resolve().parents[1]


def _prompt_copies(name: str) -> tuple[str, str]:
    root = package_root()
    disk = (root / name).read_text(encoding="utf-8")
    packaged = (root / "src" / "essay_writer" / name).read_text(encoding="utf-8")
    return disk, packaged


def _tracked() -> list[str]:
    out = subprocess.check_output(["git", "-C", str(REPO), "ls-files", "-z"])
    return [name for name in out.decode().split("\0") if name]


def test_ac1_first_time_section_covers_folder_login_consensus():
    """AC1. First-time section names Mac folder, agent login, and Consensus."""
    first_run, packaged_run = _prompt_copies("FIRST-RUN.txt")
    assert first_run == packaged_run == first_run_prompt()
    assert "First-time" in first_run
    assert "Essay Bot" in first_run or "four-way" in first_run.casefold()
    assert "login" in first_run.casefold()
    assert "Consensus" in first_run


def test_ac2_update_section_keeps_mac_login_and_health_commit():
    """AC2. Update section keeps Mac and login; skips re-ask; health commit SHA."""
    first_run, _packaged = _prompt_copies("FIRST-RUN.txt")
    assert "Update" in first_run
    assert "mac folder" in first_run.casefold()
    assert "login" in first_run.casefold()
    assert "four-way" in first_run.casefold()
    assert "ESSAY_WRITER_MAC_DIR" in first_run
    assert "essay.health" in first_run.casefold()


def test_ac3_four_way_and_chat_only_wording_unchanged():
    """AC3. Four-way card and later/skip chat-only wording stay intact."""
    first_run, _packaged = _prompt_copies("FIRST-RUN.txt")
    assert MAC_FOUR_WAY_CARD in first_run
    assert "do not say the mac folder is ready" in first_run.casefold()
    assert "chat-only" in first_run.casefold()


def test_ac4_the_public_tree_tracks_first_run_only():
    """AC4. Root and packaged FIRST-RUN ship; the friend prompt is local-only."""
    tracked = set(_tracked())
    for name in ("FIRST-RUN.txt", "src/essay_writer/FIRST-RUN.txt"):
        assert name in tracked
    assert "FRIEND-PROMPT.txt" not in tracked
    assert "src/essay_writer/FRIEND-PROMPT.txt" not in tracked
