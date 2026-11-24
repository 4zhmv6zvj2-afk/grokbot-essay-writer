"""Replace one file from a temp file in the same directory.

A crash before ``os.replace`` leaves the previous file. Callers encode JSON
or text and pass the bytes. Append-only logs and directory renames stay
outside this function.
"""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path

# A new file is readable by the student. mkstemp creates the temp as 0600,
# and that mode is replaced before the rename. An existing file keeps its mode.
NEW_FILE_MODE = 0o644


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise OSError("short write")
        view = view[written:]


def _fsync_dir(directory: Path) -> None:
    """Make the replace durable. A failure here does not remove the new file."""
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        return
    finally:
        os.close(fd)


def _publish_mode(target: Path) -> int:
    """The mode the published file keeps. A new file is 0644."""
    if target.is_symlink():
        return NEW_FILE_MODE
    try:
        if target.is_file():
            return stat.S_IMODE(target.stat().st_mode)
    except OSError:
        return NEW_FILE_MODE
    return NEW_FILE_MODE


def replace_bytes(path: Path, data: bytes, *, host_config: bool = False) -> None:
    """Publish ``data`` as ``path``. The previous file stays until replace.

    A path inside the code checkout is refused. ``host_config`` is the
    exception for Cursor and Grok attach files written into the install.
    The published mode is the previous file's mode, or 0644 when the file
    is new. Secret files do not use this function.
    """
    target = Path(path)
    if not host_config:
        from essay_writer.known_paths import refuse_repo_write

        refuse_repo_write(target)
    if not target.parent.is_dir():
        raise FileNotFoundError(target.parent)
    mode = _publish_mode(target)
    descriptor, name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
    )
    temporary = Path(name)
    replaced = False
    try:
        _write_all(descriptor, data)
        os.fsync(descriptor)
        os.fchmod(descriptor, mode)
        fd = descriptor
        descriptor = -1
        os.close(fd)
        os.replace(temporary, target)
        replaced = True
        _fsync_dir(target.parent)
    except BaseException:
        if descriptor >= 0:
            os.close(descriptor)
        if not replaced:
            temporary.unlink(missing_ok=True)
        raise


def replace_text(
    path: Path,
    text: str,
    *,
    mkdir: bool = False,
    host_config: bool = False,
) -> None:
    """Publish UTF-8 text. ``mkdir`` creates the parent when the store is new."""
    target = Path(path)
    if mkdir:
        target.parent.mkdir(parents=True, exist_ok=True)
    replace_bytes(target, text.encode("utf-8"), host_config=host_config)
