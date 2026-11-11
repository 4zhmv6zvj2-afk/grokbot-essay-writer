"""Adapter to the shared python-mcp-bootstrap core.

The core lives in ``essay_writer._vendor`` and is vendored byte-for-byte from
the public python-mcp-bootstrap repository at release v0.2.0 (tag ``v0.2.0``,
commit ``fd8e0b9``). ``VENDOR.json`` records the source, the release, and the
file SHA-256; the copy is unpatched. Keep this module importable before the
rest of the package is installed: it uses only the vendored, stdlib-only core.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from essay_writer._vendor import python_mcp_bootstrap as _core

# The package floor is 3.12, matching the vendored v0.2.0 core floor. Keep the
# floor explicit here so a future bootstrap vendoring cannot silently move this
# package's supported minimum.
REQUIRED = (3, 12, 0)
PIN = _core.PIN
VENV_DIR = _core.VENV_DIR
PYTHON_DIR = _core.PYTHON_DIR
PIN_FILE = _core.PIN_FILE
UV_INSTALL = _core.UV_INSTALL
CARD = _core.CARD

Runner = _core.Runner
Probe = _core.Probe
Exec = _core.Exec
Main = _core.Main


def _package_main(args: list[str]) -> int:
    from essay_writer.first_run import main

    return main(args)


REQUIREMENTS_FILE = "requirements-runtime.txt"

_SPEC = _core.BootstrapSpec(
    app="essay-writer",
    entrypoint="first_run.py",
    env_var="ESSAY_WRITER_INTERPRETER",
    package_main=_package_main,
    required=REQUIRED,
    pin=PIN,
    install_args=("-e", "."),
    requirements=(REQUIREMENTS_FILE,),
    verify_import="mcp.server.mcpserver",
    card=CARD,
)


def _spec_for(root: Path) -> _core.BootstrapSpec:
    """Hash-pinned runtime install for every copy.

    requirements-runtime.txt is the only dependency input: the core installs it
    with ``--require-hashes`` before the project and then uses ``--no-deps``. A
    copy without that file is refused by ``_guarded_run`` and ``provision``
    instead of falling back to an unpinned ``pip install -e .``.
    """
    return _SPEC


def _requirements_missing(root: Path) -> bool:
    return not (Path(root) / REQUIREMENTS_FILE).is_file()


def _missing_requirements_report(root: Path) -> dict[str, Any]:
    """Fail-closed report: no requirements file means no install at all."""
    return {
        "ok": False,
        "installed": False,
        "app": _SPEC.app,
        "reason": "requirements_missing",
        "detail": (
            f"{REQUIREMENTS_FILE} is missing from {Path(root)}, so no hash-pinned "
            "runtime install can run. The unpinned fallback is refused."
        ),
    }


def _guarded_run(run: Runner) -> Runner:
    """Refuse a ``--require-hashes`` install when the requirements file is gone.

    The guard keeps the core's own ordering (requirements before the project)
    and turns a missing file into a named failure instead of letting the run
    continue to an unpinned project install.
    """

    def guarded(command: list[str], cwd: Path, env: dict[str, str], timeout: int) -> dict[str, Any]:
        hash_install = "--require-hashes" in command or "--no-deps" in command
        if hash_install and _requirements_missing(cwd):
            return {
                "returncode": 1,
                "stdout": "",
                "stderr": (
                    f"{REQUIREMENTS_FILE} is missing; refusing to install the project "
                    "without hash-pinned dependencies"
                ),
            }
        return run(command, cwd, env, timeout)

    return guarded


def version_tuple(text: object) -> tuple[int, int, int] | None:
    return _core.version_tuple(text)


def run_command(command: list[str], cwd: Path, env: dict[str, str], timeout: int) -> dict[str, Any]:
    return _core.run_command(command, cwd, env, timeout)


def interpreter_version(exe: str | Path) -> tuple[int, int, int] | None:
    return _core.interpreter_version(exe)


def venv_python(root: Path) -> Path:
    return _core.venv_python(root)


def find_uv() -> str | None:
    return _core.find_uv()


def provision(
    root: Path,
    *,
    uv: str | None = None,
    run: Runner = run_command,
    probe: Probe = interpreter_version,
) -> dict[str, Any]:
    """Provision the pinned interpreter. Refuses a copy without the requirements file."""
    root = Path(root)
    if _requirements_missing(root):
        return _missing_requirements_report(root)
    return _core.provision(root, _spec_for(root), uv=uv, run=_guarded_run(run), probe=probe)


def bootstrap(
    args: list[str],
    root: Path,
    *,
    exec_fn: Exec | None = None,
    run: Runner = run_command,
    uv: str | None = None,
    probe: Probe = interpreter_version,
    current: tuple[int, int, int] | None = None,
    main_fn: Main | None = None,
) -> int:
    """Choose or provision the essay-writer interpreter, then continue."""
    root = Path(root)
    spec = replace(_spec_for(root), package_main=main_fn or _package_main)
    return _core.bootstrap(
        args,
        root,
        spec,
        exec_fn=exec_fn,
        run=_guarded_run(run),
        uv=uv,
        probe=probe,
        current=current,
    )
