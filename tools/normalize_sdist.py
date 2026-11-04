"""Rewrite a source distribution so the same source always produces the same bytes.

setuptools stamps the sdist with wall-clock metadata: the gzip header carries
the build time and the tar members keep the checkout's mtimes, ownership and
permission bits. ``SOURCE_DATE_EPOCH`` only reaches the wheel writer, so two
sdist builds of one tree differ byte-for-byte even when their contents match.

This tool rewrites the tarball deterministically under ``SOURCE_DATE_EPOCH``:

* members are sorted by name;
* every member gets ``mtime = SOURCE_DATE_EPOCH``, ``uid = gid = 0`` and empty
  ``uname``/``gname``;
* regular files are mode 0644 (0755 when they were executable) and directories
  are 0755, so a checkout's umask/ownership cannot leak in;
* the gzip stream is written with a fixed level and header (no filename,
  ``mtime = SOURCE_DATE_EPOCH``).

It also drops local build junk that setuptools can re-add after manifest
processing: ``*.egg-info`` directories (setuptools appends
``egg_info/SOURCES.txt`` to every sdist unconditionally), VCS/cache dirs and
``*.pyc`` files.

The rewrite is idempotent: normalizing an already-normalized sdist is a no-op.

Usage:
    python tools/normalize_sdist.py dist/essay_writer-0.2.1.tar.gz
    python tools/normalize_sdist.py --check dist/essay_writer-0.2.1.tar.gz
"""

from __future__ import annotations

import argparse
import copy
import gzip
import io
import os
import sys
import tarfile
import tempfile
from pathlib import Path

GZIP_LEVEL = 9
DIR_MODE = 0o755
FILE_MODE = 0o644
EXEC_MODE = 0o755
EXCLUDED_DIRS = frozenset(
    {"__pycache__", ".git", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".venv"}
)


def _excluded(name: str) -> bool:
    """True for build/host junk that must not be part of the reproducible sdist."""
    parts = name.split("/")
    if any(part in EXCLUDED_DIRS or part.endswith(".egg-info") for part in parts):
        return True
    return name.endswith((".pyc", ".pyo", ".DS_Store"))


def epoch_from_env_or_git(root: Path | None = None) -> int:
    """SOURCE_DATE_EPOCH, or the last commit time when it is not exported."""
    raw = os.environ.get("SOURCE_DATE_EPOCH", "").strip()
    if raw:
        try:
            return int(raw)
        except ValueError:
            raise SystemExit(f"SOURCE_DATE_EPOCH is not an integer: {raw!r}") from None
    root = root or Path(__file__).resolve().parents[1]
    import subprocess

    try:
        out = subprocess.check_output(
            ["git", "-C", str(root), "log", "-1", "--format=%ct"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        out = ""
    if not out:
        raise SystemExit(
            "Set SOURCE_DATE_EPOCH (for example "
            "SOURCE_DATE_EPOCH=$(git log -1 --format=%ct)) or run inside a git checkout."
        )
    return int(out)


def _member_mode(info: tarfile.TarInfo, executable: bool) -> int:
    if info.isdir():
        return DIR_MODE
    if info.issym() or info.islnk():
        return 0o777
    return EXEC_MODE if executable else FILE_MODE


def normalize_bytes(raw: bytes, epoch: int) -> bytes:
    """Return a deterministic tar.gz for the content in ``raw``."""
    members: list[tuple[tarfile.TarInfo, bytes | None, bool]] = []
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as source:
        for info in source.getmembers():
            if _excluded(info.name):
                continue
            data: bytes | None = None
            executable = bool(info.mode & 0o111)
            if info.isfile():
                handle = source.extractfile(info)
                data = handle.read() if handle is not None else b""
            members.append((copy.copy(info), data, executable))
    members.sort(key=lambda item: item[0].name)

    buffer = io.BytesIO()
    with gzip.GzipFile(
        filename="",
        mode="wb",
        fileobj=buffer,
        mtime=epoch,
        compresslevel=GZIP_LEVEL,
    ) as compressed:
        with tarfile.open(
            fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT, encoding="utf-8"
        ) as target:
            for info, data, executable in members:
                info.mtime = epoch
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                info.pax_headers = {}
                info.mode = _member_mode(info, executable)
                if data is not None:
                    info.size = len(data)
                    target.addfile(info, io.BytesIO(data))
                else:
                    info.size = 0
                    target.addfile(info)
    return buffer.getvalue()


def normalize_path(path: Path, epoch: int) -> bool:
    """Normalize ``path`` in place. Return True when bytes changed."""
    raw = path.read_bytes()
    normalized = normalize_bytes(raw, epoch)
    if normalized == raw:
        return False
    mode = path.stat().st_mode & 0o777
    handle, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(handle, "wb") as out:
            out.write(normalized)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return True


def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("sdists", nargs="+", type=Path, help="sdist .tar.gz file(s)")
    parser.add_argument(
        "--check",
        action="store_true",
        help="do not write; exit 1 if a file is not already normalized",
    )
    parser.add_argument(
        "--epoch",
        type=int,
        default=None,
        help="override SOURCE_DATE_EPOCH (defaults to the env or last commit time)",
    )
    args = parser.parse_args(argv)
    epoch = args.epoch if args.epoch is not None else epoch_from_env_or_git()
    changed = 0
    for path in args.sdists:
        if not path.is_file():
            raise SystemExit(f"not a file: {path}")
        if args.check:
            if path.read_bytes() != normalize_bytes(path.read_bytes(), epoch):
                print(f"NOT NORMALIZED: {path}")
                changed += 1
            else:
                print(f"normalized: {path}")
        else:
            state = "rewritten" if normalize_path(path, epoch) else "unchanged"
            print(f"{state}: {path} (mtime -> {epoch})")
    return 1 if changed else 0


if __name__ == "__main__":
    sys.exit(_cli())
