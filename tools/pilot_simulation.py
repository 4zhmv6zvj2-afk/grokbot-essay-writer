from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any, cast

import pilot_schema as schema
from pilot_schema import (
    CODE_RE,
    REPO,
    UNEXPECTED,
    FaultKind,
    FaultResult,
    PersonaName,
    PersonaSpec,
    StepId,
    make_fault,
    make_run,
)
from release_acceptance import ReleasePin, project_tag


def release_pin(tag: str) -> ReleasePin:
    return ReleasePin(tag)


API_KEYS = (
    "CONSENSUS_API_KEY",
    "OPENALEX_API_KEY",
    "ESSAY_WRITER_UNPAYWALL_EMAIL",
    "ESSAY_WRITER_CONSENSUS",
    "ESSAY_WRITER_CONSENSUS_PAID",
)
INCIDENT_NAMES = ("incident.jsonl", "incident.jsonl.1")
OLD_STATE = b'{"kept": 1}\n'
NEW_STATE = b'{"kept": 2}\n'
NORMAL_STEPS = frozenset(
    {"gather", "draft", "review", "final", "walk_2", "walk_4b", "stages_short"}
)


class Stop:
    def __init__(self, code: str) -> None:
        self.code = code if CODE_RE.fullmatch(code) else UNEXPECTED


def _publish(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def _load_acceptance() -> Any:
    path = Path(__file__).resolve().parent / "release_acceptance.py"
    spec = importlib.util.spec_from_file_location("essay_pilot_acceptance", path)
    if spec is None or spec.loader is None:
        print("FAIL install", file=sys.stderr)
        raise SystemExit(2)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fail_code(exc: SystemExit) -> int:
    code = exc.code
    if isinstance(code, int) and code != 0:
        return code
    return 2


def _package_digest(package_dir: Path) -> str:
    hasher = hashlib.sha256()
    for path in sorted(package_dir.rglob("*.py")):
        hasher.update(path.relative_to(package_dir).as_posix().encode())
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
        hasher.update(b"\0")
    return hasher.hexdigest()


def _under_site_packages(file_path: Path, venv: Path, repo: Path) -> bool:
    resolved = file_path.resolve()
    if not resolved.is_relative_to(venv.resolve()):
        return False
    if resolved.is_relative_to((repo / "src").resolve()):
        return False
    return "site-packages" in resolved.parts


def _read_install(python: Path, expected: str) -> tuple[str, Path] | None:
    script = (
        "import json\n"
        "import essay_writer\n"
        "print(json.dumps({'version': essay_writer.__version__, 'file': essay_writer.__file__}))\n"
    )
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["ESSAY_WRITER_RESOLVERS"] = "off"
    for name in API_KEYS:
        env.pop(name, None)
    completed = subprocess.run(
        [str(python), "-c", script],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if completed.returncode != 0:
        return None
    line = ""
    for item in reversed(completed.stdout.splitlines()):
        if item.strip():
            line = item.strip()
            break
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return None
    version = payload.get("version")
    file_name = payload.get("file")
    if version != expected or not isinstance(file_name, str):
        return None
    return version, Path(file_name)


def _resolve_wheel(
    acceptance: Any, assets_dir: Path | None, dest: Path, tag: str, wheel_name: str
) -> Path:
    if assets_dir is not None:
        candidate = assets_dir / wheel_name
        if candidate.is_file():
            return candidate
    dest.mkdir(parents=True, exist_ok=True)
    print(f"downloading {wheel_name}", file=sys.stderr)
    acceptance.download_assets(tag, REPO, dest)
    wheel = dest / wheel_name
    if not wheel.is_file():
        print("FAIL wheel", file=sys.stderr)
        raise SystemExit(2)
    return wheel


def _health(acceptance: Any, python: Path, root: Path, expected: str) -> bool:
    saved = {key: os.environ.get(key) for key in ("PYTHONPATH", "ESSAY_WRITER_ROOT", *API_KEYS)}
    os.environ.pop("PYTHONPATH", None)
    os.environ["ESSAY_WRITER_RESOLVERS"] = "off"
    os.environ["ESSAY_WRITER_ROOT"] = str(root)
    for name in API_KEYS:
        os.environ.pop(name, None)
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            acceptance.health_version(python, expected)
    except (SystemExit, subprocess.CalledProcessError, OSError):
        return False
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    return True


def _probe_env(tests: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(tests)
    env["ESSAY_WRITER_RESOLVERS"] = "off"
    for name in API_KEYS:
        env.pop(name, None)
    env.pop("ESSAY_WRITER_ROOT", None)
    return env


def _run_triage(runs: Path, report: Path, version: str) -> int:
    triage = Path(__file__).resolve().parent / "incident_triage.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(triage),
            "--runs",
            str(runs),
            "--out",
            str(report),
            "--version",
            version,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 0:
        sys.stdout.write(completed.stdout)
        return 0
    if completed.stdout.strip() == "FAIL privacy":
        sys.stdout.write(
            completed.stdout if completed.stdout.endswith("\n") else completed.stdout + "\n"
        )
        return 1
    print("FAIL triage", file=sys.stderr)
    return 2


def outer_main(args: argparse.Namespace) -> int:
    pin = release_pin(args.tag)
    repo = Path(__file__).resolve().parents[1]
    created = args.workdir is None
    workdir = (
        args.workdir if args.workdir is not None else Path(tempfile.mkdtemp(prefix="essay-pilot-"))
    )
    report = args.out if args.out is not None else Path.cwd() / "pilot-report.txt"
    try:
        return _outer(args, repo, workdir, report, pin.version, pin.wheel_name)
    finally:
        if created and not args.keep:
            shutil.rmtree(workdir, ignore_errors=True)


def _outer(
    args: argparse.Namespace,
    repo: Path,
    workdir: Path,
    report: Path,
    version: str,
    wheel_name: str,
) -> int:
    workdir.mkdir(parents=True, exist_ok=True)
    try:
        acceptance = _load_acceptance()
        wheel = _resolve_wheel(
            acceptance, args.assets_dir, workdir / "assets", args.tag, wheel_name
        )
        python = acceptance.make_venv(workdir / "venv")
        acceptance.pip_install(python, wheel)
    except SystemExit as exc:
        print("FAIL install", file=sys.stderr)
        return _fail_code(exc)
    except (subprocess.CalledProcessError, OSError):
        print("FAIL install", file=sys.stderr)
        return 2

    installed = _read_install(python, version)
    if installed is None or not _under_site_packages(installed[1], workdir / "venv", repo):
        print("FAIL installed package", file=sys.stderr)
        return 2
    version_root = workdir / "version-check"
    version_root.mkdir(parents=True, exist_ok=True)
    if not _health(acceptance, python, version_root, version):
        print("FAIL installed package", file=sys.stderr)
        return 2

    package_dir = installed[1].resolve().parent
    before = _package_digest(package_dir)
    runs = workdir / "runs"
    workspace = workdir / "workspace"
    runs.mkdir(parents=True, exist_ok=True)
    stderr_path = workdir / "probe.stderr"
    script = Path(__file__).resolve()
    with stderr_path.open("w", encoding="utf-8") as stderr:
        probe = subprocess.run(
            [
                str(python),
                str(script),
                "--probe",
                "--version",
                version,
                "--workspace",
                str(workspace),
                "--out",
                str(runs),
                "--tests",
                str(repo / "tests"),
            ],
            env=_probe_env(repo / "tests"),
            stderr=stderr,
            check=False,
        )
    drift = _package_digest(package_dir) != before
    triage_code = _run_triage(runs, report, version)
    if triage_code == 1:
        return 1
    if triage_code != 0:
        return triage_code
    if drift:
        print("FAIL package drift", file=sys.stderr)
        return 2
    if probe.returncode == 3:
        return 3
    if probe.returncode != 0:
        print("FAIL probe", file=sys.stderr)
        return 2
    return 0


def _fresh_root(root: Path) -> None:
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    (root / "uploads").mkdir()
    (root / "Essay-writer").mkdir()
    os.environ["ESSAY_WRITER_ROOT"] = str(root)
    os.environ["ESSAY_WRITER_RESOLVERS"] = "off"
    for name in API_KEYS:
        os.environ.pop(name, None)
    from essay_writer.build_status import reset_status

    reset_status()


def _incident_codes(root: Path) -> list[str]:
    found: list[str] = []
    for name in INCIDENT_NAMES:
        path = root / name
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            code = obj.get("code") if isinstance(obj, dict) else None
            if isinstance(code, str):
                found.append(code)
    return found


def _line_count(root: Path) -> int:
    total = 0
    for name in INCIDENT_NAMES:
        path = root / name
        if not path.is_file():
            continue
        total += sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    return total


def _added(before: list[str], after: list[str]) -> list[str]:
    leftover = list(before)
    added: list[str] = []
    for code in after:
        if code in leftover:
            leftover.remove(code)
        else:
            added.append(code)
    return added


def _copy_incidents(root: Path, dest: Path) -> int:
    count = 0
    for name in INCIDENT_NAMES:
        source = root / name
        if not source.is_file():
            continue
        text = source.read_text(encoding="utf-8")
        _publish(dest / name, text if text.endswith("\n") or text == "" else text + "\n")
        count += sum(1 for line in text.splitlines() if line.strip())
    return count


def _normal_outcome(result: object) -> Stop | None:
    if isinstance(result, dict) and result.get("stored") is True:
        return None
    if isinstance(result, dict):
        refused = result.get("refused")
        if isinstance(refused, str) and CODE_RE.fullmatch(refused):
            return Stop(refused)
    return Stop(UNEXPECTED)


def _stages_short(shell: Any, seq: str) -> dict[str, Any]:
    from conversations.fixtures import SHORT, STAGE_LOOK

    last: dict[str, Any] = {}
    for stage in ("1", "2", "3", "4a", "4b"):
        look = f"{STAGE_LOOK} Stage {stage} I write short."
        draft = shell.call(
            "essay.stage",
            essay_id=seq,
            stage=stage,
            confirmPhase="draft",
            look=look,
        )
        if draft.get("ok") is not True:
            return draft
        last = shell.call(
            "essay.stage",
            essay_id=seq,
            stage=stage,
            confirmPhase="confirm",
            look=look,
            cardAction="confirm",
            cardDigest=draft.get("digest"),
        )
        if last.get("stored") is not True:
            return last
    look5 = (
        "This essay says ports shape coastal trade when a narrow passage sets the route. "
        f"I write short. The gathered note supports that claim {SHORT}."
    )
    return shell.call(
        "essay.stage",
        essay_id=seq,
        stage="5",
        confirmPhase="draft",
        look=look5,
    )


def _current_stage(seq: str) -> str | None:
    from essay_writer.stage_state import load_pointer

    pointer = load_pointer(seq)
    if not isinstance(pointer, dict):
        return None
    stage = pointer.get("current")
    if isinstance(stage, str) and stage:
        return stage
    return None


def _fault_malformed(shell: Any, seq: str, root: Path, persona: PersonaName) -> FaultResult | Stop:
    from essay_writer.paths import work_dir

    stage = _current_stage(seq)
    if stage is None:
        return Stop(UNEXPECTED)
    before = _incident_codes(root)
    (work_dir(seq) / "state.json").write_bytes(b"not-json")
    result = shell.call(
        "essay.stage",
        essay_id=seq,
        stage=stage,
        confirmPhase="draft",
        look="",
    )
    if "state-damaged" in _added(before, _incident_codes(root)):
        return make_fault(persona, "malformed_payload", "noted")
    if isinstance(result, dict) and result.get("refused") == "state":
        return make_fault(persona, "malformed_payload", "refused")
    return _normal_outcome(result) or Stop(UNEXPECTED)


def _fault_refused_save(
    shell: Any, seq: str, root: Path, persona: PersonaName
) -> FaultResult | Stop:
    from conversations.fixtures import STAGE_LOOK

    stage = _current_stage(seq) or "4b"
    look = f"{STAGE_LOOK} Stage 4b keeps this sentence."
    before = _incident_codes(root)
    result = shell.call(
        "essay.stage",
        essay_id=seq,
        stage=stage,
        confirmPhase="nope",
        look=look,
    )
    if isinstance(result, dict) and result.get("refused") == "confirm":
        return make_fault(persona, "refused_save", "refused")
    if "confirm" in _added(before, _incident_codes(root)):
        return make_fault(persona, "refused_save", "noted")
    return _normal_outcome(result) or Stop(UNEXPECTED)


def _stop_process(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            proc.kill()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def _fault_timeout(shell: Any, seq: str, root: Path, persona: PersonaName) -> FaultResult | Stop:
    del shell
    code = (
        "import os, sys\n"
        "os.environ['ESSAY_WRITER_RESOLVERS'] = 'off'\n"
        "from conversations.fixtures import QUESTION\n"
        "from essay_writer.server import HANDLERS\n"
        "HANDLERS['essay.dig'](essay_id=sys.argv[1], query=QUESTION, confirmPhase='draft')\n"
    )
    before = _line_count(root)
    proc = subprocess.Popen(
        [sys.executable, "-c", code, seq],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=str(root),
        start_new_session=True,
    )
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        _stop_process(proc)
        return make_fault(persona, "timeout", "killed")
    observed = "noted" if _line_count(root) > before else "not_observed"
    return make_fault(persona, "timeout", observed)


def _fault_crash(shell: Any, seq: str, root: Path, persona: PersonaName) -> FaultResult | Stop:
    del shell, seq
    from essay_writer.durable import replace_bytes

    path = root / "crash-state.json"
    replace_bytes(path, OLD_STATE)
    code = (
        "import sys\n"
        "from pathlib import Path\n"
        "from essay_writer.durable import replace_bytes\n"
        "replace_bytes(Path(sys.argv[1]), b'{\"kept\": 2}\\n')\n"
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", code, str(path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        cwd=str(root),
        start_new_session=True,
    )
    _stop_process(proc)
    err = b""
    if proc.stderr is not None:
        err = proc.stderr.read()
        proc.stderr.close()
    text = err.decode("utf-8", errors="replace")
    if (
        proc.returncode is not None
        and proc.returncode > 0
        and ("ImportError" in text or "ModuleNotFoundError" in text)
    ):
        return Stop(UNEXPECTED)
    current = path.read_bytes() if path.is_file() else b""
    if current == OLD_STATE:
        return make_fault(persona, "crash", "previous_bytes_kept")
    if current == NEW_STATE:
        return make_fault(persona, "crash", "replaced")
    return Stop(UNEXPECTED)


FAULTS: dict[FaultKind, Any] = {
    "malformed_payload": _fault_malformed,
    "timeout": _fault_timeout,
    "crash": _fault_crash,
    "refused_save": _fault_refused_save,
}


def _run_persona(spec: PersonaSpec, workspace: Path, runs: Path, version: str) -> str:
    from conversations.drive import (
        final_word,
        first_draft,
        gather_and_list,
        open_sequence,
        review_first_word,
        walk_through,
    )
    from conversations.shell import FakeShell

    persona = spec["persona"]
    root = workspace / persona
    _fresh_root(root)
    shell = FakeShell()
    seq = ""
    steps_ran: list[StepId] = []
    fault_rows: list[FaultResult] = []
    stopped = False
    stop_code = ""
    current: StepId = spec["steps"][0]

    def walk_2(active: FakeShell, sequence: str) -> dict[str, Any]:
        return walk_through(active, sequence, "2")

    def walk_4b(active: FakeShell, sequence: str) -> dict[str, Any]:
        return walk_through(active, sequence, "4b")

    normals = {
        "gather": gather_and_list,
        "draft": first_draft,
        "review": review_first_word,
        "final": final_word,
        "walk_2": walk_2,
        "walk_4b": walk_4b,
        "stages_short": _stages_short,
    }
    try:
        for step in spec["steps"]:
            current = step
            print(f"step {persona} {step}", file=sys.stderr)
            if step == "open":
                seq = open_sequence(shell)
                steps_ran.append(step)
                continue
            if step in FAULTS:
                outcome = FAULTS[cast(FaultKind, step)](shell, seq, root, persona)
            else:
                outcome = _normal_outcome(normals[step](shell, seq))
            if isinstance(outcome, Stop):
                stopped = True
                stop_code = outcome.code
                steps_ran.append(step)
                break
            if isinstance(outcome, dict):
                fault_rows.append(outcome)
            steps_ran.append(step)
    except Exception:
        traceback.print_exc()
        stopped = True
        stop_code = UNEXPECTED
        if not steps_ran or steps_ran[-1] != current:
            steps_ran.append(current)
    dest = runs / persona
    count = _copy_incidents(root, dest)
    record = make_run(
        persona,
        steps_ran,
        [item["fault"] for item in fault_rows],
        count,
        stopped,
        stop_code,
        version,
    )
    _publish(dest / "run.json", json.dumps(record, sort_keys=True) + "\n")
    body = "".join(json.dumps(item, sort_keys=True) + "\n" for item in fault_rows)
    _publish(dest / "faults.jsonl", body)
    if stopped:
        print(f"stopped persona={persona} step={current}", flush=True)
        return current
    return ""


def _assert_installed(expected: str, tests: Path) -> bool:
    try:
        import essay_writer
    except ImportError:
        print("FAIL installed package", file=sys.stderr)
        return False
    file_path = Path(essay_writer.__file__).resolve()
    repo_src = tests.resolve().parent / "src"
    if essay_writer.__version__ != expected or "site-packages" not in file_path.parts:
        print("FAIL installed package", file=sys.stderr)
        return False
    if file_path.is_relative_to(repo_src.resolve()):
        print("FAIL installed package", file=sys.stderr)
        return False
    return True


def probe_main(args: argparse.Namespace) -> int:
    if not args.version or args.workspace is None or args.out is None or args.tests is None:
        print("FAIL probe", file=sys.stderr)
        return 2
    tests = args.tests.resolve()
    if not tests.is_dir():
        print("FAIL probe", file=sys.stderr)
        return 2
    if str(tests) not in sys.path:
        sys.path.insert(0, str(tests))
    if not _assert_installed(args.version, tests):
        return 2
    for spec in schema.PERSONAS:
        for step in spec["steps"]:
            if step != "open" and step not in FAULTS and step not in NORMAL_STEPS:
                print("FAIL probe", file=sys.stderr)
                return 2
    runs = args.out
    if runs.exists():
        shutil.rmtree(runs)
    runs.mkdir(parents=True)
    args.workspace.mkdir(parents=True, exist_ok=True)
    try:
        for spec in schema.PERSONAS:
            if _run_persona(spec, args.workspace, runs, args.version):
                return 3
    except Exception:
        traceback.print_exc()
        print("FAIL probe", file=sys.stderr)
        return 2
    return 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Simulate four student personas on an installed essay-writer release."
    )
    parser.add_argument("--tag", default=None)
    parser.add_argument("--assets-dir", type=Path)
    parser.add_argument("--workdir", type=Path)
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--version")
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--tests", type=Path)
    args = parser.parse_args(argv)
    if args.tag is None:
        args.tag = project_tag()
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.probe:
        return probe_main(args)
    return outer_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
