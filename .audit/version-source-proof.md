# Release pin counts

The count is matches of `v?0\.9\.\d+` in utf-8 files under `tests/` and `tools/`. `__pycache__` directories are skipped. One line with two matches counts as two. `tests/test_essay_author.py` has one such line, `0.9.20` and `0.9.2`. No file failed to decode.

This scan does not read `src/`, `docs/`, or `.audit/`.

## Before

Measured on this worktree before the edit, with the command below.

- `tests/test_essay_author.py`: 5
- `tests/test_first_run.py`: 16
- `tests/test_gate_tools.py`: 16
- `tests/test_license_metadata.py`: 4
- `tests/test_pilot_privacy.py`: 2
- `tests/test_pilot_release_pin.py`: 2
- `tests/test_setup_ask_and_health_read.py`: 3
- `tests/test_state_fixtures.py`: 11
- `tests/test_update.py`: 14
- `tools/pilot_schema.py`: 1
- `tools/release_acceptance.py`: 6
- `tools/tag_release.py`: 5

tests 73. tools 12.

## After

Measured on this worktree after the edit, with the same command. Zero files skipped.

- `tests/test_essay_author.py`: 5
- `tests/test_license_metadata.py`: 4
- `tests/test_state_fixtures.py`: 11
- `tools/release_acceptance.py`: 4
- `tools/tag_release.py`: 5

tests 20. tools 9.

`tests/test_no_release_pin_literals.py` reports no violations on this tree. The four matches in `tools/release_acceptance.py` and the five in `tools/tag_release.py` are `0.9.19` only. The 11 matches in `tests/test_state_fixtures.py` are `0.9.14`, `0.9.18`, and `0.9.19` only. The other two test files are the changelog history allowlist, so every `0.9` match in them is allowed.

## Regenerate the count

Run this from the repository root.

```bash
python3 - <<'PY'
import re
from pathlib import Path
root = Path.cwd()
pat = re.compile(r"v?0\.9\.\d+")
for base in ("tests", "tools"):
    total = 0
    for path in sorted((root / base).rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        found = pat.findall(text)
        if found:
            print(f"{len(found):4} {path.relative_to(root).as_posix()}")
            total += len(found)
    print(f"== {base} {total}")
PY
```

## Seeded failure

```bash
uv run --extra dev pytest tests/test_no_release_pin_literals.py::test_a_seeded_tip_pin_fails_the_scan
```

`test_a_seeded_tip_pin_fails_the_scan` writes `0.9.21` into a temporary `tests/test_seed.py` and expects `forbidden_release_pins` to report that line. The pin is not left in the tree. `test_release_tools_allow_only_the_fixture_version` checks that `0.9.19` is allowed in `tools/release_acceptance.py` and `tools/tag_release.py`, and that `v0.9.21` in those files is not.
