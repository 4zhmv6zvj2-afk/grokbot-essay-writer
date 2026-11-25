# Run a simulated pilot

You run four synthetic students against the installed essay-writer 0.9.21 wheel, then read a plain-text report. These runs are simulations. They are not validation with real students. The tools do not change product behavior.

## Install and simulate

From the repository root:

```bash
python tools/pilot_simulation.py --keep --workdir /tmp/essay-pilot --out /tmp/essay-pilot/report.txt
```

The command downloads `essay_writer-0.9.21-py3-none-any.whl` for tag `v0.9.21` when `--assets-dir` does not already contain that file. It installs the wheel into a new virtualenv, checks that `essay_writer.__file__` is under that virtualenv's `site-packages`, and runs the four personas one after another. Each persona has its own `ESSAY_WRITER_ROOT`.

Pass `--assets-dir DIR` when that directory already holds the wheel. Pass `--keep` to leave the virtualenv and the `runs/` directory in the work directory. Without `--keep`, and without `--workdir`, the command deletes the temporary work directory after it writes the report.

The default report path is `pilot-report.txt` in the current directory.

There is no `--tag` flag. The wheel name and the version are fixed at 0.9.21.

## Read a saved run

```bash
python tools/incident_triage.py --runs /tmp/essay-pilot/runs --out /tmp/essay-pilot/report.txt
```

Triage reads `run.json`, `faults.jsonl`, `incident.jsonl`, and `incident.jsonl.1`. It prints counts for code, severity, disposition, tool, stage, and persona. Product faults and harness faults are separate sections. Omit `--out` to print the report only on stdout.

If the rendered report contains a privacy sentinel, the command prints `FAIL privacy`, writes no report file, and exits 1.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | All four personas finished, and the report passed the privacy scan. |
| 1 | The report failed the privacy scan. |
| 2 | The wheel, the virtualenv, or the version check could not run, or the installed package files changed during the run. |
| 3 | A persona stopped on an unplanned product failure. The report still prints. The product is not edited. |

On exit 3 the simulation prints `stopped persona=<name> step=<step>`. That line does not include door text.

Evidence for each persona is `runs/<persona>/` inside the work directory. That folder holds `run.json`, `faults.jsonl`, and the copied incident files.

## Personas

| Persona | Steps | Faults |
| --- | --- | --- |
| careful | open, gather, draft, review, final | none |
| rushed | open, gather, walk_2 | none |
| non-native | open, gather, stages_short, review, final | none |
| error-prone | open, gather, walk_4b, malformed_payload, timeout, crash, refused_save | all four |

`malformed_payload` and `refused_save` are product faults. The pilot passes a bad input, and the installed package answers. `timeout` and `crash` are harness faults. The pilot stops its own child process. A harness fault is not a product failure.

The student text is the synthetic fixtures in `tests/conversations/`. Resolvers stay off.

## A clean run

A clean run exits 0. The first line of the report is:

```text
These four runs are simulations on installed essay-writer 0.9.21. They are not validation with real students.
```

Each persona line shows an incident count and `stopped=false`. The report has no essay text, no prompt, no path, and no door sentence.

The recorded run used this command.

```bash
.venv/bin/python tools/pilot_simulation.py --assets-dir /tmp/essay-pilot-0.9.21/assets --keep --workdir /tmp/essay-pilot-0.9.21-final --out /tmp/essay-pilot-0.9.21-final/report.txt
```

The virtualenv's `essay_writer` version was 0.9.21, and the package file was under that virtualenv's `site-packages`. The process exited 0. These four runs are simulations on installed essay-writer 0.9.21. They are not validation with real students. The full report is `/tmp/essay-pilot-0.9.21-final/report.txt`. Counts below are from this single run.

| Persona | Incidents | Stopped | Stop code |
| --- | --- | --- | --- |
| careful | 1 | false | |
| rushed | 1 | false | |
| non-native | 1 | false | |
| error-prone | 5 | false | |

The top codes are `guidance-only` (4), `state-damaged` (2), `confirm` (1), and `state` (1).

Each persona recorded one `guidance-only` refusal and still finished. That refusal is the friction on every persona. `error-prone` also ran the four planned faults.

Product faults are `malformed_payload=noted` (1) and `refused_save=refused` (1). Harness faults are `crash=previous_bytes_kept` (1) and `timeout=noted` (1). The timeout child returned within 2 seconds and added an incident line, so the harness recorded `noted`.
