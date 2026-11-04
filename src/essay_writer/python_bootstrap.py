"""Adapter to the shared python-mcp-bootstrap core.

The core lives in ``essay_writer._vendor`` and is copied from the private
python-mcp-bootstrap repository. Keep this module importable before the rest of
the package is installed: it uses only the vendored, stdlib-only core.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from essay_writer._vendor import python_mcp_bootstrap as _core

# The package floor is 3.12. The vendored core defaults to its own floor
# (3.14); keep the vendored file byte-identical to its upstream release and
# pass the project floor in here instead.
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


_SPEC = _core.BootstrapSpec(
    app="essay-writer",
    entrypoint="first_run.py",
    env_var="ESSAY_WRITER_INTERPRETER",
    package_main=_package_main,
    required=REQUIRED,
    pin=PIN,
    install_args=("-e", "."),
    verify_import="mcp.server.mcpserver",
    card=CARD,
)


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
    return _core.provision(root, _SPEC, uv=uv, run=run, probe=probe)


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

    spec = replace(_SPEC, package_main=main_fn or _package_main)
    return _core.bootstrap(
        args,
        root,
        spec,
        exec_fn=exec_fn,
        run=run,
        uv=uv,
        probe=probe,
        current=current,
    )
