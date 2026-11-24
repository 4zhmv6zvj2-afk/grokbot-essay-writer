"""Replace one file from a temp file in the same directory.

A crash before ``os.replace`` leaves the previous file. Callers encode JSON
or text and pass the bytes. Append-only logs and directory renames stay
outside this function.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


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


def replace_bytes(path: Path, data: bytes) -> None:
    """Publish ``data`` as ``path``. The previous file stays until replace.

    This does not decide whether the path is a student save. Doors that save
    student work call ``refuse_repo_write`` themselves. Host config inside
    the install is not a student save.
    """
    target = Path(path)
    if not target.parent.is_dir():
        raise FileNotFoundError(target.parent)
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


def replace_text(path: Path, text: str, *, mkdir: bool = False) -> None:
    """Publish UTF-8 text. ``mkdir`` creates the parent when the store is new."""
    target = Path(path)
    if mkdir:
        target.parent.mkdir(parents=True, exist_ok=True)
    replace_bytes(target, text.encode("utf-8"))
