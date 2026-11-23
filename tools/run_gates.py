"""Run the checkout gate and stamp a clean full pass.

The fast gate is the checkout half of CI. ``--full`` adds the Python 3.12
coverage run and the sdist job from ``.github/workflows/ci.yml``: it calls
``tools/reproducible_build.py`` (which normalizes the tarball through
``tools/normalize_sdist.py``), then extracts that sdist and runs pytest there.

A stamp is written only after a clean tree passes. ``--allow-dirty`` is for
local iteration and never writes one. The stamp lives in the git directory,
not the worktree:

    python tools/run_gates.py
    python tools/run_gates.py --full
    python tools/run_gates.py --json

Exit 1 when a step fails. Exit 2 when the environment cannot run the gate
(not a git repo, Python older than 3.12, or ``--full`` without uv / Python 3.12).
A failing step deletes a previous stamp for the same HEAD. A missing or stale
stamp is not a reason to keep going; ``tools/tag_release.py`` reads the file
and refuses on its own.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

STAMP_NAME = "gate-stamp.json"
STAMP_MAX_AGE = timedelta(minutes=60)
TAIL_LINES = 40
FAST_STEPS = ("docs", "snapshot", "ruff", "format", "mypy", "pytest")
FULL_STEPS = FAST_STEPS + ("coverage312", "sdist")
SDIST_REQUIRED = (
    "tests/conftest.py",
    "tests/helpers.py",
    "tests/pty_support.py",
    "tests/fixtures",
    "tests/snapshots/prompts.json",
    ".gitignore",
)


def command(
    args: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> tuple[int, str]:
    """Run a fixed argv. Return the exit code and the combined output."""
    try:
        completed = subprocess.run(
            args,
            cwd=cwd,
            env=env,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except FileNotFoundError as exc:
        return 127, f"{exc}\n"
    return completed.returncode, completed.stdout or ""


def now() -> datetime:
    """Local time with its UTC offset, which is the stamp's ``when`` field."""
    return datetime.now().astimezone()


def current_versions() -> dict[str, str]:
    """Python, ruff, and mypy versions recorded in a stamp."""
    return {
        "python": ".".join(str(part) for part in sys.version_info[:3]),
        "ruff": _version_token([sys.executable, "-m", "ruff", "--version"]),
        "mypy": _version_token([sys.executable, "-m", "mypy", "--version"]),
    }


def stamp_problems(
    stamp: object,
    *,
    head: str,
    dirty: bool,
    now: datetime,
    versions: dict[str, str],
) -> list[str]:
    """Reasons this stamp cannot authorize a tag. Empty means it can."""
    if not isinstance(stamp, dict):
        return ["the stamp is not a JSON object"]
    problems: list[str] = []
    if stamp.get("head_sha") != head:
        problems.append("the stamp is for a different commit")
    if dirty:
        problems.append("the tree is dirty")
    if stamp.get("clean") is not True:
        problems.append("the stamp does not record a clean tree")
    if stamp.get("mode") != "full":
        problems.append("the stamp mode is not full")
    steps = stamp.get("steps")
    if not isinstance(steps, dict):
        problems.append("the stamp has no step map")
    else:
        for name in FULL_STEPS:
            if steps.get(name) != "pass":
                problems.append(f"step {name} is not pass")
    parsed = _parse_when(stamp.get("when"))
    if parsed is None:
        problems.append("the stamp time is missing or not ISO-8601")
    elif now - parsed > STAMP_MAX_AGE:
        problems.append("the stamp is older than 60 minutes")
    for key in ("python", "ruff", "mypy"):
        if stamp.get(key) != versions.get(key):
            problems.append(
                f"recorded {key} {stamp.get(key)!r} does not match current {versions.get(key)!r}"
            )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--full", action="store_true", help="add coverage and the sdist job")
    parser.add_argument("--json", action="store_true", help="print the machine-readable result")
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="run on a dirty tree and do not write a stamp",
    )
    args = parser.parse_args(argv)
    started = time.perf_counter()
    mode = "full" if args.full else "fast"

    # The package targets 3.12, and an older interpreter still has to refuse
    # before it tries to import a syntax or stdlib feature it does not have.
    if sys.version_info < (3, 12):  # noqa: UP036
        return _finish(2, ["run_gates needs Python 3.12 or newer"], args.json, mode, {}, started)

    root, root_error = _repo_root()
    if root is None:
        return _finish(2, [root_error], args.json, mode, {}, started)

    if args.full and shutil.which("uv") is None:
        return _finish(2, ["run_gates --full needs uv on PATH"], args.json, mode, {}, started)
    if args.full and not _python_312_available():
        return _finish(
            2,
            ["run_gates --full needs a Python 3.12 interpreter (uv python find 3.12)"],
            args.json,
            mode,
            {},
            started,
        )

    status, porcelain = command(["git", "status", "--porcelain"], cwd=root)
    if status != 0:
        return _finish(
            2, ["could not read git status", porcelain.rstrip()], args.json, mode, {}, started
        )
    dirty = bool(porcelain.strip())
    if dirty and not args.allow_dirty:
        _delete_stamp_for_head(root)
        return _finish(
            1,
            ["clean fail 0.0s", "git status --porcelain is not empty", porcelain.rstrip()],
            args.json,
            mode,
            {"clean": "fail"},
            started,
            failed="clean",
        )

    results: dict[str, str] = {}
    names = FULL_STEPS if args.full else FAST_STEPS
    for name in names:
        step_started = time.perf_counter()
        code, output = _run_step(name, root)
        elapsed = time.perf_counter() - step_started
        state = "pass" if code == 0 else "fail"
        results[name] = state
        _say(f"{name} {state} {elapsed:.1f}s", args.json)
        if code != 0:
            _delete_stamp_for_head(root)
            tail = _tail(output)
            lines = [tail] if tail else []
            lines.append(f"gate failed at {name} after {time.perf_counter() - started:.1f}s")
            return _finish(1, lines, args.json, mode, results, started, failed=name, tail=tail)

    if dirty:
        line = f"gate {mode} passed in {time.perf_counter() - started:.1f}s; stamp skipped"
        return _finish(0, [line], args.json, mode, results, started)

    stamp_path, error = _write_stamp(root, mode=mode, steps=results)
    if error is not None:
        return _finish(1, [error], args.json, mode, results, started, failed="stamp")
    line = f"gate {mode} passed in {time.perf_counter() - started:.1f}s"
    return _finish(0, [line, f"stamp {stamp_path}"], args.json, mode, results, started)


def _run_step(name: str, root: Path) -> tuple[int, str]:
    if name == "coverage312":
        return _run_coverage(root)
    if name == "sdist":
        return _run_sdist(root)
    flags: dict[str, list[str]] = {
        "docs": ["tools/generate_docs.py", "--check"],
        "snapshot": ["tools/update_prompt_snapshot.py", "--check"],
        "ruff": ["-m", "ruff", "check", "src", "tests", "tools"],
        "format": ["-m", "ruff", "format", "--check", "--force-exclude", "src", "tests", "tools"],
        "mypy": ["-m", "mypy", "src"],
        "pytest": ["-m", "pytest", "-q"],
    }
    return command([sys.executable, *flags[name]], cwd=root, env=_child_env())


def _run_coverage(root: Path) -> tuple[int, str]:
    """Run the 3.12 coverage command without replacing the project environment.

    ``uv run --python 3.12`` otherwise recreates ``.venv`` and drops the dev
    extra, which removes pytest-cov and the build tools the sdist step needs.
    """
    env = _child_env()
    env["UV_PROJECT_ENVIRONMENT"] = str(Path(tempfile.gettempdir()) / "essay-writer-gate-py312")
    code, text = command(
        ["uv", "sync", "--python", "3.12", "--extra", "dev", "--frozen"],
        cwd=root,
        env=env,
    )
    if code != 0:
        return code, text
    return command(
        [
            "uv",
            "run",
            "--python",
            "3.12",
            "pytest",
            "-q",
            "--cov=essay_writer",
            "--cov-report=term",
            "--cov-fail-under=85",
        ],
        cwd=root,
        env=env,
    )


def _run_sdist(root: Path) -> tuple[int, str]:
    """Build, extract, and test the sdist the way the CI artifacts job does."""
    code, epoch_text = command(["git", "log", "-1", "--format=%ct"], cwd=root)
    epoch = epoch_text.strip()
    if code != 0 or not epoch.isdigit():
        return 1, epoch_text or "could not read the commit time for SOURCE_DATE_EPOCH"
    env = _child_env(epoch)
    with tempfile.TemporaryDirectory(prefix="essay-writer-gate-") as tmp:
        tmp_path = Path(tmp)
        outdir = tmp_path / "dist"
        code, text = command(
            [sys.executable, "tools/reproducible_build.py", "--outdir", str(outdir)],
            cwd=root,
            env=env,
        )
        if code != 0:
            return 1, text
        tarballs = sorted(outdir.glob("*.tar.gz"))
        wheels = sorted(outdir.glob("*.whl"))
        if len(tarballs) != 1 or len(wheels) != 1:
            return 1, (
                f"expected one sdist and one wheel, found {len(tarballs)} sdists "
                f"and {len(wheels)} wheels\n{text}"
            )
        extract = tmp_path / "sdist"
        extract.mkdir()
        code, extract_text = command(
            ["tar", "xzf", str(tarballs[0]), "-C", str(extract), "--strip-components=1"],
            cwd=root,
        )
        if code != 0:
            return 1, extract_text
        code, listing = command(["git", "ls-files", "-z"], cwd=root)
        if code != 0:
            return 1, listing or "git ls-files failed"
        tracked = [path for path in listing.split("\0") if path]
        missing = [path for path in tracked if not (extract / path).exists()]
        if missing:
            lines = [f"the sdist is missing tracked file {path}" for path in missing]
            lines.append(f"the sdist is missing {len(missing)} tracked files")
            return 1, "\n".join(lines)
        from_sdist = tmp_path / "from-sdist"
        code, wheel_text = command(
            [
                sys.executable,
                "-m",
                "build",
                "--no-isolation",
                "--wheel",
                "--outdir",
                str(from_sdist),
            ],
            cwd=extract,
            env=env,
        )
        if code != 0:
            return 1, wheel_text
        rebuilt = sorted(from_sdist.glob("*.whl"))
        if len(rebuilt) != 1:
            return 1, f"the extracted sdist produced {len(rebuilt)} wheels"
        checkout_hash = _sha256(wheels[0])
        sdist_hash = _sha256(rebuilt[0])
        if checkout_hash != sdist_hash:
            return 1, (
                "the wheel built from the sdist is not identical to the checkout wheel\n"
                f"checkout {checkout_hash}\n"
                f"sdist    {sdist_hash}"
            )
        for required in SDIST_REQUIRED:
            if not (extract / required).exists():
                return 1, f"the sdist is missing {required}"
        for git_args in (
            ["git", "init", "-q", "."],
            ["git", "add", "-A"],
            [
                "git",
                "-c",
                "user.name=ci",
                "-c",
                "user.email=ci@example.invalid",
                "commit",
                "-qm",
                "extracted sdist",
            ],
        ):
            code, git_text = command(git_args, cwd=extract)
            if code != 0:
                return 1, git_text
        code, pytest_text = command([sys.executable, "-m", "pytest", "-q"], cwd=extract, env=env)
        if code != 0:
            return 1, pytest_text
        summary = (
            f"the sdist carries all {len(tracked)} tracked files\n"
            "the sdist->wheel build is byte-identical to the checkout wheel\n"
            f"{pytest_text}"
        )
        return 0, summary


def _write_stamp(root: Path, *, mode: str, steps: dict[str, str]) -> tuple[Path | None, str | None]:
    head = _head(root)
    directory = _git_dir(root)
    if head is None or directory is None:
        return None, "could not record the stamp because HEAD or the git dir is unavailable"
    try:
        versions = current_versions()
    except RuntimeError as exc:
        return None, f"could not record tool versions: {exc}"
    code, branch = command(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=root)
    payload = {
        "head_sha": head,
        "branch": branch.strip() if code == 0 and branch.strip() else "HEAD",
        "mode": mode,
        "clean": True,
        "when": now().isoformat(timespec="seconds"),
        "python": versions["python"],
        "ruff": versions["ruff"],
        "mypy": versions["mypy"],
        "steps": {name: steps[name] for name in (FULL_STEPS if mode == "full" else FAST_STEPS)},
    }
    path = directory / STAMP_NAME
    temporary = path.with_name(f"{STAMP_NAME}.tmp")
    try:
        temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    except OSError as exc:
        return None, f"could not write the stamp: {exc}"
    return path, None


def _delete_stamp_for_head(root: Path) -> None:
    head = _head(root)
    directory = _git_dir(root)
    if head is None or directory is None:
        return
    path = directory / STAMP_NAME
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if isinstance(data, dict) and data.get("head_sha") == head:
        try:
            path.unlink()
        except OSError:
            return


def _repo_root() -> tuple[Path | None, str]:
    code, text = command(["git", "rev-parse", "--show-toplevel"])
    if code != 0:
        return None, "run_gates must be run inside the essay-writer repository"
    return Path(text.strip()), ""


def _git_dir(root: Path) -> Path | None:
    code, text = command(["git", "rev-parse", "--git-dir"], cwd=root)
    if code != 0 or not text.strip():
        return None
    path = Path(text.strip())
    if not path.is_absolute():
        path = root / path
    return path


def _head(root: Path) -> str | None:
    code, text = command(["git", "rev-parse", "HEAD"], cwd=root)
    if code != 0 or not text.strip():
        return None
    return text.strip()


def _python_312_available() -> bool:
    code, text = command(["uv", "python", "find", "3.12"])
    return code == 0 and bool(text.strip())


def _child_env(epoch: str | None = None) -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("UV_LINK_MODE", "copy")
    if epoch is not None:
        env["SOURCE_DATE_EPOCH"] = epoch
    return env


def _version_token(args: list[str]) -> str:
    code, text = command(args)
    if code != 0:
        raise RuntimeError(text.strip() or "version command failed")
    for token in text.split():
        if token[:1].isdigit() and token.count(".") >= 1:
            return token
    raise RuntimeError(text.strip() or "version command printed no version")


def _parse_when(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tail(text: str) -> str:
    lines = text.splitlines()
    return "\n".join(lines[-TAIL_LINES:])


def _say(line: str, as_json: bool) -> None:
    print(line, file=sys.stderr if as_json else sys.stdout, flush=True)


def _finish(
    code: int,
    lines: list[str],
    as_json: bool,
    mode: str,
    steps: dict[str, str],
    started: float,
    *,
    failed: str | None = None,
    tail: str = "",
) -> int:
    for line in lines:
        if line:
            _say(line, as_json)
    if as_json:
        payload: dict[str, object] = {
            "ok": code == 0,
            "exit": code,
            "mode": mode,
            "failed": failed,
            "elapsed_s": round(time.perf_counter() - started, 3),
            "steps": steps,
        }
        if tail:
            payload["tail"] = tail
        print(json.dumps(payload, indent=2), flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
