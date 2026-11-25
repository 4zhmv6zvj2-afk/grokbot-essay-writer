"""Release acceptance for a published essay-writer tag.

Dev-only. The outer path uses the standard library only: it downloads the
release assets, checks them against SHA256SUMS, installs the wheel into one
clean venv and the sdist into another, then runs ``essay-writer --health``
and a probe in each. The ``--probe`` path imports the installed package (and
its python-docx dependency) and is not part of the product runtime.

From the repository root. Pass a tag, or omit ``--tag`` to use the version in
``pyproject.toml``:

    python tools/release_acceptance.py --tag v1.2.3

Exit 0 when every check passes. Exit 1 when a check fails. Exit 2 when the
environment cannot run the harness.
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
import tomllib
import urllib.error
import urllib.request
import venv
import zipfile
from dataclasses import dataclass
from pathlib import Path

DEFAULT_REPO = "4zhmv6zvj2-afk/grokbot-essay-writer"
LOOK_STAGE6 = "The draft is saved in Word."
ESSAY_SENTINEL = "The fisheries opening stayed on the page."
PATH_SENTINEL = "/Users/student/essay.txt"
OLD_STATE = b'{"kept": 1}\n'
NEW_STATE = b'{"kept": 2}\n'


def fail(message: str, code: int = 1) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(code)


def ok(message: str) -> None:
    print(f"PASS: {message}")


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def version_of(tag: str) -> str:
    return tag[1:] if tag.startswith("v") else tag


def asset_names(version: str) -> tuple[str, str, str]:
    return (
        f"essay_writer-{version}-py3-none-any.whl",
        f"essay_writer-{version}.tar.gz",
        "SHA256SUMS",
    )


def project_version(root: Path | None = None) -> str:
    base = repo_root() if root is None else root
    text = (base / "pyproject.toml").read_text(encoding="utf-8")
    return str(tomllib.loads(text)["project"]["version"])


def project_tag(root: Path | None = None) -> str:
    return f"v{project_version(root)}"


@dataclass(frozen=True)
class ReleasePin:
    tag: str
    version: str
    wheel_name: str

    def __init__(self, tag: str) -> None:
        version = version_of(tag)
        object.__setattr__(self, "tag", tag)
        object.__setattr__(self, "version", version)
        object.__setattr__(self, "wheel_name", asset_names(version)[0])


def _download_one(url: str, target: Path) -> None:
    """Fetch one release asset. Prefer curl, then urllib."""
    curl = shutil.which("curl")
    if curl is not None:
        subprocess.run(
            [curl, "-fsSL", "-o", str(target), url],
            check=True,
        )
        return
    try:
        with urllib.request.urlopen(url) as response:  # noqa: S310 — fixed GitHub release URL
            target.write_bytes(response.read())
    except urllib.error.URLError as exc:
        fail(f"could not download {target.name}: {exc}", code=2)


def download_assets(tag: str, repo: str, folder: Path) -> tuple[Path, Path, Path]:
    version = version_of(tag)
    wheel_name, sdist_name, sums_name = asset_names(version)
    folder.mkdir(parents=True, exist_ok=True)
    names = (wheel_name, sdist_name, sums_name)
    # gh is the usual maintainer path; curl/urllib cover a machine without it.
    gh = shutil.which("gh")
    if gh is not None:
        print(f"gh release download {tag} --repo {repo}")
        subprocess.run(
            [
                gh,
                "release",
                "download",
                tag,
                "--repo",
                repo,
                "--dir",
                str(folder),
                "--clobber",
                *[item for name in names for item in ("--pattern", name)],
            ],
            check=True,
        )
    else:
        base = f"https://github.com/{repo}/releases/download/{tag}"
        for name in names:
            url = f"{base}/{name}"
            print(f"download {url}")
            _download_one(url, folder / name)
    paths: dict[str, Path] = {}
    for name in names:
        target = folder / name
        if not target.is_file():
            fail(f"download left {name} missing", code=2)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        print(f"  got {name} sha256={digest}")
        paths[name] = target
    return paths[wheel_name], paths[sdist_name], paths[sums_name]


def verify_sha256sums(folder: Path, sums_path: Path) -> dict[str, str]:
    checked: dict[str, str] = {}
    for raw in sums_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            fail(f"bad SHA256SUMS line: {raw!r}")
        expected, name = parts[0], parts[-1]
        name = name.lstrip("*")
        path = folder / name
        if not path.is_file():
            fail(f"SHA256SUMS names {name}, but that file is missing")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            fail(f"{name}: expected {expected}, got {actual}")
        checked[name] = actual
        ok(f"hash {name} = {actual}")
    if not checked:
        fail("SHA256SUMS listed no files")
    return checked


def make_venv(path: Path) -> Path:
    if path.exists():
        shutil.rmtree(path)
    builder = venv.EnvBuilder(with_pip=True, clear=True)
    builder.create(path)
    python = path / ("Scripts" if os.name == "nt" else "bin") / "python"
    if not python.is_file():
        fail(f"venv python missing at {python}", code=2)
    return python


def pip_install(python: Path, artifact: Path) -> None:
    print(f"pip install {artifact.name}")
    subprocess.run(
        [str(python), "-m", "pip", "install", "--upgrade", "pip"],
        check=True,
    )
    subprocess.run(
        [str(python), "-m", "pip", "install", str(artifact)],
        check=True,
    )


def health_version(python: Path, expected: str) -> str:
    env = os.environ.copy()
    env["ESSAY_WRITER_RESOLVERS"] = "off"
    completed = subprocess.run(
        [str(python), "-m", "essay_writer", "--health"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        fail(f"--health was not JSON: {exc}\n{completed.stdout}")
    version = payload.get("version")
    if version != expected:
        fail(f"--health version {version!r} != {expected!r}")
    ok(f"--health version {version}")
    return str(version)


def run_probe(python: Path, *, version: str, fixtures: Path, work: Path) -> None:
    script = Path(__file__).resolve()
    cmd = [
        str(python),
        str(script),
        "--probe",
        "--version",
        version,
        "--fixtures",
        str(fixtures),
        "--workspace",
        str(work),
    ]
    print(f"probe {' '.join(cmd)}")
    completed = subprocess.run(cmd, check=False)
    if completed.returncode != 0:
        fail(f"probe failed with exit {completed.returncode}")


def plant_fixture(seq: str, fixtures: Path) -> None:
    from essay_writer.paths import work_dir

    dest = work_dir(seq)
    dest.mkdir(parents=True, exist_ok=True)
    state = json.loads((fixtures / "state.json").read_text(encoding="utf-8"))
    # The shipped fixture names MOD1004AA-1. A second open_sequence in the
    # same workspace gets -2, so rewrite the id to the live sequence.
    state["essay_id"] = seq
    pack = state.get("saved_pack")
    if isinstance(pack, dict):
        pack["essay_id"] = seq
    (dest / "state.json").write_text(
        json.dumps(state, indent=2) + "\n",
        encoding="utf-8",
    )
    tracking = dest / "tracking"
    tracking.mkdir(parents=True, exist_ok=True)
    journal = tracking / ".stage.commit"
    if journal.is_file():
        journal.unlink()
    for path in (fixtures / "tracking").iterdir():
        if path.is_file():
            shutil.copyfile(path, tracking / path.name)


def open_sequence() -> str:
    from essay_writer.projects import essay_sequence_new

    draft = essay_sequence_new("MOD1004AA", "draft")
    if draft.get("ok") is not True:
        fail(f"sequence draft failed: {draft}")
    opened = essay_sequence_new("MOD1004AA", "confirm")
    if opened.get("ok") is not True:
        fail(f"sequence confirm failed: {opened}")
    return str(opened["sequence_id"])


def advance(seq: str, stage: str, look: str) -> dict:
    from essay_writer.stage_track import essay_stage

    draft = essay_stage(seq, stage, "draft", look)
    if draft.get("ok") is not True:
        fail(f"stage {stage} draft failed: {draft}")
    saved = essay_stage(
        seq,
        stage,
        "confirm",
        cardAction="confirm",
        cardDigest=draft.get("digest"),
    )
    if saved.get("stored") is True:
        return saved
    pressed = essay_stage(seq, stage, "confirm", look=look)
    saved = essay_stage(
        seq,
        stage,
        "confirm",
        cardAction=pressed.get("cardAction"),
        cardDigest=pressed.get("cardDigest"),
    )
    if saved.get("stored") is not True:
        fail(f"stage {stage} confirm did not store: {saved}")
    return saved


def check_word(seq: str, expected_paragraph: str) -> Path:
    from docx import Document

    from essay_writer.paths import work_dir
    from essay_writer.word import write_first_draft_word

    written = write_first_draft_word(seq)
    if written.get("wrote") is not True:
        fail(f"Word write failed: {written}")
    path = work_dir(seq) / "output" / f"{seq}.docx"
    if not path.is_file():
        fail(f"Word file missing at {path}")
    document = Document(str(path))
    title = document.core_properties.title or ""
    if title != seq:
        fail(f"Word title {title!r} != {seq!r}")
    paragraphs = [p.text.strip() for p in document.paragraphs if p.text.strip()]
    if expected_paragraph not in paragraphs:
        fail(f"Word paragraphs {paragraphs!r} missing {expected_paragraph!r}")
    ok(f"Word title={title!r} paragraphs include {expected_paragraph!r}")
    return path


def check_crash(workspace: Path) -> None:
    from essay_writer.durable import replace_bytes

    path = workspace / "crash-state.json"
    path.write_bytes(OLD_STATE)
    ready = workspace / "crash-ready"
    if ready.exists():
        ready.unlink()
    script = (
        "import os, sys, time\n"
        "from pathlib import Path\n"
        "path = Path(sys.argv[1])\n"
        "ready = Path(sys.argv[2])\n"
        "real = os.replace\n"
        "def pause(src, dst):\n"
        "    ready.write_text('ready', encoding='utf-8')\n"
        "    time.sleep(30)\n"
        "    real(src, dst)\n"
        "os.replace = pause\n"
        "from essay_writer.durable import replace_bytes\n"
        "replace_bytes(path, b'{\\\"kept\\\": 2}\\n')\n"
    )
    env = os.environ.copy()
    proc = subprocess.Popen(
        [sys.executable, "-c", script, str(path), str(ready)],
        env=env,
    )
    deadline = time.monotonic() + 10
    while not ready.exists():
        if proc.poll() is not None or time.monotonic() > deadline:
            proc.kill()
            fail(f"crash writer exited {proc.returncode} before replace")
        time.sleep(0.05)
    proc.kill()
    proc.wait(timeout=5)
    if path.read_bytes() != OLD_STATE:
        fail("crash mid-save did not leave the previous state")
    # A normal save after the kill must still load and publish.
    replace_bytes(path, NEW_STATE)
    if path.read_bytes() != NEW_STATE:
        fail("post-crash save did not publish")
    ok("crash mid-save left previous state; next save published")


def check_bundle_and_wipe(workspace: Path) -> None:
    from essay_writer.debug_log import essay_debug_wipe, support_bundle
    from essay_writer.incident import FILENAME, ROTATED_NAME, incident_path, note, rotated_path

    note(
        "read-bad-json",
        severity="warn",
        disposition="fallback",
        tool="read",
        step="json",
    )
    # Force a rotated file the way the product does after a line cap.
    from essay_writer import incident as incident_mod

    incident_mod.MAX_LINES = 1
    note(
        "page-cursor-repeat",
        severity="warn",
        disposition="fallback",
        tool="read",
        step="page",
    )
    if not incident_path().is_file() or not rotated_path().is_file():
        fail("incident.jsonl and incident.jsonl.1 were not both present before wipe")

    (workspace / "debug.log").write_text(f"debug {ESSAY_SENTINEL}\n", encoding="utf-8")
    (workspace / "ml-events.jsonl").write_text(
        f'{{"look":"{ESSAY_SENTINEL}","path":"{PATH_SENTINEL}"}}\n',
        encoding="utf-8",
    )
    state = workspace / "Essay-writer" / "MOD1004AA" / "sequences" / "1" / "state.json"
    if state.is_file():
        # Already planted by the Word path; keep it for files.json.
        pass

    exported = support_bundle()
    if exported.get("ok") is not True:
        fail(f"support bundle failed: {exported}")
    archive = workspace / "support.zip"
    if not archive.is_file():
        fail("support.zip was not written")
    with zipfile.ZipFile(archive) as zip_file:
        names = set(zip_file.namelist())
        blob = b"\n".join(zip_file.read(name) for name in zip_file.namelist())
        text = blob.decode("utf-8", errors="replace")
        manifest = json.loads(zip_file.read("manifest.json"))
        health = json.loads(zip_file.read("health.json"))
    required = {"incident.jsonl", "health.json", "files.json", "manifest.json"}
    if not required <= names:
        fail(f"support.zip missing {required - names}")
    if "debug.log" in names or "ml-events.jsonl" in names:
        fail("support.zip must not include debug logs")
    if ESSAY_SENTINEL in text:
        fail("support.zip leaked essay text")
    if PATH_SENTINEL in text or "/Users/" in text or str(workspace) in text:
        fail("support.zip leaked a path")
    if "soft" not in manifest and "error" not in manifest:
        fail(f"manifest.json missing counts: {manifest}")
    if "version" not in health:
        fail(f"health.json missing version: {health}")
    ok("support bundle has manifest/incident; no debug logs, essay text, or paths")

    wiped = essay_debug_wipe("delete the logs")
    if wiped.get("ok") is not True or wiped.get("cleared_incident") is not True:
        fail(f"wipe failed: {wiped}")
    if incident_path().is_file() or rotated_path().is_file():
        fail(f"{FILENAME} or {ROTATED_NAME} still present after wipe")
    ok("wipe removed incident.jsonl and incident.jsonl.1")


def check_upgrade(fixtures: Path) -> None:
    from essay_writer.stage_note import _note_look
    from essay_writer.stage_state import load_pointer
    from essay_writer.state import load_state

    seq = open_sequence()
    plant_fixture(seq, fixtures)
    state = load_state(seq)
    if state.get("essay_id") != seq:
        fail(f"upgrade load essay_id {state.get('essay_id')!r} != {seq!r}")
    if load_pointer(seq).get("current") != "6":
        fail(f"upgrade pointer current {load_pointer(seq).get('current')!r} != '6'")
    look = _note_look(seq, "5")
    if look != "The corridor depends on a narrow strait.":
        fail(f"upgrade stage-5 look {look!r}")
    saved = advance(seq, "6", LOOK_STAGE6)
    if saved.get("stored") is not True:
        fail(f"upgrade advance failed: {saved}")
    if load_pointer(seq).get("current") != "7":
        fail(f"upgrade did not advance to 7: {load_pointer(seq)}")
    ok("0.9.19 fixture loaded and advanced under this install")


def probe_main(version: str, fixtures: Path, workspace: Path) -> int:
    # Probe imports are deferred so the outer stdlib path never needs them.
    from essay_writer.build_status import reset_status
    from essay_writer.paths import workspace_root_lock
    from essay_writer.stage_note import _note_look
    from essay_writer.stage_state import load_pointer
    from essay_writer.state import load_state

    if not fixtures.is_dir():
        fail(f"fixtures missing: {fixtures}", code=2)
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)
    (workspace / "uploads").mkdir()
    (workspace / "Essay-writer").mkdir()

    with workspace_root_lock():
        os.environ["ESSAY_WRITER_ROOT"] = str(workspace)
        os.environ["ESSAY_WRITER_RESOLVERS"] = "off"
        reset_status()

    print(f"probe workspace={workspace}")
    print(f"probe fixtures={fixtures}")
    print(f"probe expected version={version}")

    seq = open_sequence()
    plant_fixture(seq, fixtures)
    state = load_state(seq)
    if state.get("essay_id") != seq:
        fail(f"planted essay_id {state.get('essay_id')!r} != {seq!r}")
    if load_pointer(seq).get("current") != "6":
        fail(f"planted current {load_pointer(seq).get('current')!r} != '6'")
    look = _note_look(seq, "5")
    if not isinstance(look, str) or not look.strip():
        fail(f"stage-5 look missing: {look!r}")
    check_word(seq, look)
    saved = advance(seq, "6", LOOK_STAGE6)
    if load_pointer(seq).get("current") != "7":
        fail(f"after Word, current {load_pointer(seq).get('current')!r} != '7'")
    ok(f"synthetic workflow reached Word and advanced ({saved.get('stored')})")

    check_crash(workspace)
    check_bundle_and_wipe(workspace)
    check_upgrade(fixtures)
    ok(f"probe complete for {version}")
    return 0


def load_local_assets(folder: Path, version: str) -> tuple[Path, Path, Path]:
    wheel_name, sdist_name, sums_name = asset_names(version)
    wheel, sdist, sums = folder / wheel_name, folder / sdist_name, folder / sums_name
    for path in (wheel, sdist, sums):
        if not path.is_file():
            fail(f"local assets missing {path.name} under {folder}", code=2)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        print(f"  local {path.name} sha256={digest}")
    return wheel, sdist, sums


def accept_main(
    tag: str,
    repo: str,
    workdir: Path | None,
    keep: bool,
    assets_dir: Path | None = None,
) -> int:
    version = version_of(tag)
    fixtures = repo_root() / "tests" / "fixtures" / "state" / "0.9.19"
    if not fixtures.is_dir():
        fail(f"0.9.19 fixtures missing at {fixtures}", code=2)

    if workdir is None:
        root = Path(tempfile.mkdtemp(prefix=f"essay-writer-accept-{version}-"))
    else:
        root = workdir
        root.mkdir(parents=True, exist_ok=True)
    print(f"work dir {root}")

    try:
        if assets_dir is not None:
            print(f"local assets {assets_dir}")
            wheel, sdist, sums = load_local_assets(assets_dir, version)
            assets = assets_dir
        else:
            assets = root / "assets"
            wheel, sdist, sums = download_assets(tag, repo, assets)
        hashes = verify_sha256sums(assets, sums)
        print("verified hashes:")
        for name, digest in sorted(hashes.items()):
            print(f"  {name}  {digest}")

        for label, artifact in (("wheel", wheel), ("sdist", sdist)):
            print(f"\n=== {label}: {artifact.name} ===")
            venv_path = root / f"venv-{label}"
            python = make_venv(venv_path)
            pip_install(python, artifact)
            health_version(python, version)
            probe_work = root / f"probe-{label}"
            run_probe(python, version=version, fixtures=fixtures, work=probe_work)
            ok(f"{label} install accepted")

        print("\nALL PASS")
        print(f"tag={tag} version={version} repo={repo}")
        print(f"work={root}")
        return 0
    finally:
        if not keep and workdir is None and root.exists():
            shutil.rmtree(root, ignore_errors=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--tag",
        default=None,
        help="published release tag; omit to use the v-prefixed version from pyproject.toml",
    )
    parser.add_argument(
        "--repo",
        default=DEFAULT_REPO,
        help=f"GitHub owner/name (default {DEFAULT_REPO})",
    )
    parser.add_argument(
        "--workdir",
        type=Path,
        default=None,
        help="keep downloads and venvs here instead of a temp directory",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="keep the temp work directory after a pass",
    )
    parser.add_argument(
        "--assets-dir",
        type=Path,
        default=None,
        help="use a local folder of wheel+sdist+SHA256SUMS instead of downloading",
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help="run the in-venv probe (invoked by the outer harness)",
    )
    parser.add_argument("--version", default=None, help="expected version for --probe")
    parser.add_argument("--fixtures", type=Path, default=None, help="0.9.19 fixture dir")
    parser.add_argument("--workspace", type=Path, default=None, help="probe workspace")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.probe:
        if args.version is None or args.fixtures is None or args.workspace is None:
            fail("--probe needs --version, --fixtures, and --workspace", code=2)
        return probe_main(args.version, args.fixtures, args.workspace)
    tag = args.tag if args.tag is not None else project_tag()
    return accept_main(tag, args.repo, args.workdir, args.keep, args.assets_dir)


if __name__ == "__main__":
    raise SystemExit(main())
