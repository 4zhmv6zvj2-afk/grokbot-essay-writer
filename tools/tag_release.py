"""Create an annotated release tag only when a fresh full gate stamp matches HEAD.

The tool never runs the gate and never pushes. A missing or stale stamp is a
refusal. ``--dry-run`` prints the checks and creates nothing.

    python tools/tag_release.py v0.9.19 --dry-run
    python tools/tag_release.py v0.9.19
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path


def _load_gates():
    """Load ``run_gates.py`` from this directory without putting it on sys.path."""
    path = Path(__file__).resolve().parent / "run_gates.py"
    name = "_essay_writer_run_gates"
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


run_gates = _load_gates()

TAG_PATTERN = re.compile(r"^v\d+\.\d+\.\d+$")


def version_check(tag: str, root: Path) -> tuple[int, str]:
    """Run ``tools/check_release_version.py`` for this tag. Do not run the gate."""
    return run_gates.command(
        [sys.executable, "tools/check_release_version.py", "--tag", tag],
        cwd=root,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tag", help="annotated tag to create, for example v0.9.19")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the checks and do not create the tag",
    )
    args = parser.parse_args(argv)
    tag = args.tag
    if TAG_PATTERN.fullmatch(tag) is None:
        print(f"refusing {tag}: a release tag looks like v0.9.19", file=sys.stderr)
        return 1

    root, root_error = run_gates._repo_root()
    if root is None:
        print(root_error, file=sys.stderr)
        return 2
    status, porcelain = run_gates.command(["git", "status", "--porcelain"], cwd=root)
    if status != 0:
        print("could not read git status", file=sys.stderr)
        return 2
    head = run_gates._head(root)
    if head is None:
        print("could not read HEAD", file=sys.stderr)
        return 2
    if porcelain.strip():
        print("the tree is dirty", file=sys.stderr)
        return 1

    directory = run_gates._git_dir(root)
    if directory is None:
        print("could not find the git dir", file=sys.stderr)
        return 2
    stamp_path = directory / run_gates.STAMP_NAME
    if not stamp_path.is_file():
        print(
            "no gate stamp. A missing stamp is a refusal. "
            "Run python tools/run_gates.py --full, then tag within 60 minutes.",
            file=sys.stderr,
        )
        return 1
    try:
        stamp = json.loads(stamp_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"the gate stamp cannot be read: {exc}", file=sys.stderr)
        return 1
    try:
        versions = run_gates.current_versions()
    except RuntimeError as exc:
        print(f"could not read the current tool versions: {exc}", file=sys.stderr)
        return 2
    problems = run_gates.stamp_problems(
        stamp,
        head=head,
        dirty=False,
        now=run_gates.now(),
        versions=versions,
    )
    if problems:
        print("refusing to tag:", file=sys.stderr)
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1

    code, text = version_check(tag, root)
    if code != 0:
        print("check_release_version failed.", file=sys.stderr)
        if text.strip():
            print(text.rstrip(), file=sys.stderr)
        return 1

    local_code, _local = run_gates.command(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/tags/{tag}"]
    )
    if local_code == 0:
        print(f"refusing to tag: {tag} already exists locally", file=sys.stderr)
        return 1
    remote_code, remote = run_gates.command(
        ["git", "ls-remote", "--tags", "origin", f"refs/tags/{tag}"]
    )
    if remote_code != 0:
        print(f"refusing to tag: could not check origin for {tag}", file=sys.stderr)
        if remote.strip():
            print(remote.rstrip(), file=sys.stderr)
        return 1
    if remote.strip():
        print(f"refusing to tag: {tag} already exists on origin", file=sys.stderr)
        return 1

    when = stamp.get("when") if isinstance(stamp, dict) else ""
    print(f"clean tree at {head}")
    print(f"stamp full at {when} for {head}")
    print(f"check_release_version passed for {tag}")
    print(f"tag {tag} is absent locally and on origin")
    if args.dry_run:
        print("dry-run: no tag created")
        return 0

    message = f"full gate stamp at {when}"
    tag_code, tag_text = run_gates.command(["git", "tag", "-a", tag, "-m", message])
    if tag_code != 0:
        print(f"git tag failed; no tag created\n{tag_text.rstrip()}", file=sys.stderr)
        return 1
    print(f"created annotated tag {tag}")
    print("Next:")
    print(f"1. Push the tag: git push origin {tag}")
    print(f"2. Create a draft GitHub release for {tag}.")
    print(f"3. Dispatch the Release workflow with {tag}.")
    print("4. Publish the release after that workflow succeeds.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
