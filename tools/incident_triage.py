from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import pilot_schema as schema
from pilot_schema import (
    BUILD_RE,
    CODE_RE,
    EXC_RE,
    INCIDENT_FIELDS,
    NONE_KEY,
    SECTION_TITLES,
    VERSION,
    CountBucket,
    FaultResult,
    IncidentRow,
    PersonaName,
    PersonaRun,
    PilotReport,
    contains_forbidden,
    disclaimer_for,
    parse_disposition,
    parse_fault_kind,
    parse_observed,
    parse_origin,
    parse_persona,
    parse_severity,
    parse_step,
    stage_ok,
    tool_ok,
)


def _text_field(raw: dict[str, object], key: str) -> str | None:
    if key not in raw:
        return ""
    value = raw[key]
    if not isinstance(value, str):
        return None
    return value


def parse_incident(raw: object, persona: PersonaName) -> IncidentRow | None:
    if not isinstance(raw, dict) or contains_forbidden(raw):
        return None
    fields: dict[str, str] = {}
    for key in INCIDENT_FIELDS:
        value = _text_field(raw, key)
        if value is None:
            return None
        fields[key] = value
    severity = parse_severity(fields["severity"])
    disposition = parse_disposition(fields["disposition"])
    if severity is None or disposition is None:
        return None
    if CODE_RE.fullmatch(fields["code"]) is None:
        return None
    if not tool_ok(fields["tool"]) or not stage_ok(fields["stage"]):
        return None
    if fields["exc"] and EXC_RE.fullmatch(fields["exc"]) is None:
        return None
    if fields["build"] and BUILD_RE.fullmatch(fields["build"]) is None:
        return None
    return {
        "build": fields["build"],
        "code": fields["code"],
        "disposition": disposition,
        "exc": fields["exc"],
        "severity": severity,
        "stage": fields["stage"],
        "tool": fields["tool"],
        "persona": persona,
    }


def parse_fault(raw: object, persona: PersonaName) -> FaultResult | None:
    if not isinstance(raw, dict) or contains_forbidden(raw):
        return None
    named = raw.get("persona")
    if named is not None and parse_persona(named) != persona:
        return None
    fault = parse_fault_kind(raw.get("fault"))
    observed = parse_observed(raw.get("observed"))
    origin = parse_origin(raw.get("origin"))
    if fault is None or observed is None or origin is None:
        return None
    if schema.FAULT_ORIGIN[fault] != origin:
        return None
    return {
        "persona": persona,
        "fault": fault,
        "origin": origin,
        "observed": observed,
    }


def parse_run(raw: object, persona: PersonaName, version: str = VERSION) -> PersonaRun | None:
    if not isinstance(raw, dict) or contains_forbidden(raw):
        return None
    if parse_persona(raw.get("persona")) != persona or raw.get("version") != version:
        return None
    steps_raw = raw.get("steps")
    faults_raw = raw.get("faults")
    if not isinstance(steps_raw, list) or not isinstance(faults_raw, list):
        return None
    count = raw.get("incident_count")
    stopped = raw.get("stopped")
    stop_code = raw.get("stop_code")
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        return None
    if not isinstance(stopped, bool) or not isinstance(stop_code, str):
        return None
    if stop_code and CODE_RE.fullmatch(stop_code) is None:
        return None
    if stopped and stop_code == "":
        return None
    if not stopped and stop_code != "":
        return None
    steps = [step for item in steps_raw if (step := parse_step(item)) is not None]
    faults = [fault for item in faults_raw if (fault := parse_fault_kind(item)) is not None]
    return {
        "persona": persona,
        "version": version,
        "steps": steps,
        "faults": faults,
        "incident_count": count,
        "stopped": stopped,
        "stop_code": stop_code,
    }


def _placeholder(persona: PersonaName, version: str = VERSION) -> PersonaRun:
    return {
        "persona": persona,
        "version": version,
        "steps": [],
        "faults": [],
        "incident_count": 0,
        "stopped": False,
        "stop_code": "",
    }


def _load_json(path: Path) -> object | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None


def _iter_lines(path: Path) -> list[object] | None:
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    values: list[object] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            values.append(json.loads(line))
        except json.JSONDecodeError:
            values.append(None)
    return values


def _bucket(keys: list[str], required: tuple[str, ...] = ()) -> list[CountBucket]:
    tally = {name: 0 for name in required}
    for key in keys:
        tally[key] = tally.get(key, 0) + 1
    if not required:
        tally = {key: count for key, count in tally.items() if count > 0}
    return [{"key": key, "count": tally[key]} for key in sorted(tally)]


def aggregate(runs_dir: Path, version: str = VERSION) -> PilotReport:
    dropped_rows = 0
    dropped_runs = 0
    present: dict[str, Path] = {}
    if runs_dir.is_dir():
        for child in runs_dir.iterdir():
            if not child.is_dir():
                continue
            if child.name not in schema.PERSONA_NAMES:
                dropped_runs += 1
                continue
            present[child.name] = child

    runs: list[PersonaRun] = []
    incidents: list[IncidentRow] = []
    faults: list[FaultResult] = []
    for spec in schema.PERSONAS:
        persona = spec["persona"]
        folder = present.get(persona)
        if folder is None:
            continue
        run_path = folder / "run.json"
        if not run_path.is_file():
            dropped_runs += 1
            runs.append(_placeholder(persona, version))
            continue
        parsed = parse_run(_load_json(run_path), persona, version)
        if parsed is None:
            dropped_runs += 1
            runs.append(_placeholder(persona, version))
            continue
        runs.append(parsed)
        for name in ("incident.jsonl", "incident.jsonl.1"):
            lines = _iter_lines(folder / name)
            if lines is None:
                dropped_rows += 1
                continue
            for item in lines:
                row = parse_incident(item, persona)
                if row is None:
                    dropped_rows += 1
                else:
                    incidents.append(row)
        fault_lines = _iter_lines(folder / "faults.jsonl")
        if fault_lines is None:
            dropped_rows += 1
            continue
        for item in fault_lines:
            fault = parse_fault(item, persona)
            if fault is None:
                dropped_rows += 1
            else:
                faults.append(fault)

    persona_names = tuple(run["persona"] for run in runs)
    product = [
        f"{item['fault']}={item['observed']}" for item in faults if item["origin"] == "product"
    ]
    harness = [
        f"{item['fault']}={item['observed']}" for item in faults if item["origin"] == "harness"
    ]
    return {
        "simulation": True,
        "version": version,
        "disclaimer": disclaimer_for(version),
        "runs": runs,
        "by_code": _bucket([row["code"] for row in incidents]),
        "by_severity": _bucket(
            [row["severity"] for row in incidents],
            schema.SEVERITIES,
        ),
        "by_disposition": _bucket(
            [row["disposition"] for row in incidents],
            schema.DISPOSITIONS,
        ),
        "by_tool": _bucket([row["tool"] or NONE_KEY for row in incidents]),
        "by_stage": _bucket([row["stage"] or NONE_KEY for row in incidents]),
        "by_persona": _bucket([row["persona"] for row in incidents], persona_names),
        "by_fault_product": _bucket(product),
        "by_fault_harness": _bucket(harness),
        "dropped_rows": dropped_rows,
        "dropped_runs": dropped_runs,
    }


def _persona_line(run: PersonaRun) -> str:
    line = (
        f"{run['persona']}  incidents={run['incident_count']}  "
        f"stopped={str(run['stopped']).lower()}"
    )
    if run["stopped"]:
        return f"{line}  stop_code={run['stop_code']}"
    return line


def render(report: PilotReport) -> str:
    lines = [report["disclaimer"], ""]
    for run in report["runs"]:
        lines.append(_persona_line(run))
    if report["runs"]:
        lines.append("")
    sections = (
        report["by_code"],
        report["by_severity"],
        report["by_disposition"],
        report["by_tool"],
        report["by_stage"],
        report["by_persona"],
        report["by_fault_product"],
        report["by_fault_harness"],
    )
    for title, buckets in zip(SECTION_TITLES, sections, strict=True):
        lines.append(title)
        for bucket in buckets:
            lines.append(f"{bucket['key']}  {bucket['count']}")
        lines.append("")
    lines.append(f"dropped_rows  {report['dropped_rows']}")
    lines.append(f"dropped_runs  {report['dropped_runs']}")
    return "\n".join(lines) + "\n"


def guard(text: str) -> bool:
    return not any(item in text for item in schema.FORBIDDEN)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize pilot incident metadata.")
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--version", default=VERSION)
    args = parser.parse_args(argv)
    if not args.runs.is_dir():
        print("FAIL runs", file=sys.stderr)
        return 2
    text = render(aggregate(args.runs, args.version))
    if not guard(text):
        print("FAIL privacy")
        if args.out is not None and args.out.exists():
            args.out.unlink()
        return 1
    if args.out is not None:
        _atomic_write(args.out, text)
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
