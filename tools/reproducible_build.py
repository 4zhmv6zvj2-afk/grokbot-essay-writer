"""Build the sdist and wheel twice and prove the results are byte-identical.

Reproducible-release entry point used by CI and the release workflow:

    export SOURCE_DATE_EPOCH="$(git log -1 --format=%ct)"
    python tools/reproducible_build.py --outdir dist

It installs nothing. ``python -m build --no-isolation`` uses the interpreter's
pinned setuptools/wheel (see ``requirements-build.txt``), builds the pair twice
in isolated temp output dirs, normalizes each sdist to SOURCE_DATE_EPOCH with
``tools/normalize_sdist.py``, compares the SHA256 of every artifact name, and
only then copies the first build into ``--outdir`` (default ``dist``). Any hash
mismatch exits non-zero, so a drifting build can never be uploaded.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from normalize_sdist import epoch_from_env_or_git, normalize_path  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
ARTIFACT_GLOBS = ("*.tar.gz", "*.whl")


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _clean_build_tree() -> None:
    """Drop byproducts so build two starts from the same source state as build one."""
    for path in (REPO / "build", REPO / "src" / "essay_writer.egg-info"):
        shutil.rmtree(path, ignore_errors=True)


def _build(outdir: Path, epoch: int) -> dict[str, str]:
    outdir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, SOURCE_DATE_EPOCH=str(epoch))
    subprocess.run(
        [sys.executable, "-m", "build", "--no-isolation", "--outdir", str(outdir)],
        cwd=REPO,
        env=env,
        check=True,
    )
    for pattern in ("*.tar.gz",):
        for sdist in sorted(outdir.glob(pattern)):
            normalize_path(sdist, epoch)
    artifacts = {path.name: _hash(path) for path in _iter_artifacts(outdir)}
    if not artifacts:
        raise SystemExit(f"build produced no artifacts in {outdir}")
    return artifacts


def _iter_artifacts(directory: Path) -> list[Path]:
    paths: list[Path] = []
    for pattern in ARTIFACT_GLOBS:
        paths.extend(sorted(directory.glob(pattern)))
    return paths


def _print_table(first: dict[str, str], second: dict[str, str]) -> None:
    names = sorted(set(first) | set(second))
    width = max(len(name) for name in names)
    for name in names:
        left = first.get(name, "MISSING")
        right = second.get(name, "MISSING")
        marker = "=" if left == right else "!"
        print(f"{marker} {name:<{width}}  {left}\n    {'':<{width}}  {right}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--outdir",
        type=Path,
        default=REPO / "dist",
        help="where the verified artifacts are copied (default: dist/)",
    )
    parser.add_argument(
        "--epoch",
        type=int,
        default=None,
        help="override SOURCE_DATE_EPOCH (defaults to the env or last commit time)",
    )
    args = parser.parse_args(argv)
    epoch = args.epoch if args.epoch is not None else epoch_from_env_or_git(REPO)
    print(f"SOURCE_DATE_EPOCH={epoch}")

    with tempfile.TemporaryDirectory(prefix="essay-writer-build-") as tmp:
        root = Path(tmp)
        builds: list[dict[str, str]] = []
        for index in (1, 2):
            _clean_build_tree()
            print(f"\nbuild {index}:")
            builds.append(_build(root / f"build{index}", epoch))
        _clean_build_tree()

        first, second = builds
        print("\nSHA256, build 1 vs build 2:")
        _print_table(first, second)
        if first != second:
            print("\nFAIL: two builds of the same source produced different artifacts.")
            return 1

        outdir: Path = args.outdir
        outdir.mkdir(parents=True, exist_ok=True)
        for path in _iter_artifacts(root / "build1"):
            destination = outdir / path.name
            shutil.copy2(path, destination)
            print(f"copied {destination}")

    print("\nOK: both builds are byte-identical.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
