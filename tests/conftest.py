import pytest
from pty_support import pty_reason, pty_required


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("ESSAY_WRITER_ROOT", str(tmp_path))
    monkeypatch.setenv("ESSAY_WRITER_RESOLVERS", "off")
    (tmp_path / "uploads").mkdir()
    (tmp_path / "Essay-writer").mkdir()
    return tmp_path


@pytest.fixture
def requires_pty() -> None:
    """Skip when this host refuses a pty; fail instead when CI requires one."""
    reason = pty_reason()
    if reason is None:
        return
    if pty_required():
        pytest.fail(
            f"{reason}. These ACs need a real terminal, and CI must provide one.",
            pytrace=False,
        )
    pytest.skip(
        f"{reason}. Run pytest in a normal terminal for these ACs, "
        "or set ESSAY_WRITER_REQUIRE_PTY=1 to fail instead of skip.",
    )
