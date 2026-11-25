from __future__ import annotations

import re
from typing import Literal, TypedDict, cast

from release_acceptance import asset_names, version_of

PersonaName = Literal["careful", "rushed", "non-native", "error-prone"]
FaultKind = Literal["timeout", "malformed_payload", "crash", "refused_save"]
FaultOrigin = Literal["product", "harness"]
Severity = Literal["warn", "info", "error"]
Disposition = Literal["retry", "fallback", "refuse"]
Observed = Literal[
    "noted",
    "refused",
    "killed",
    "previous_bytes_kept",
    "replaced",
    "not_observed",
]
StepId = Literal[
    "open",
    "gather",
    "draft",
    "review",
    "final",
    "walk_2",
    "walk_4b",
    "stages_short",
    "malformed_payload",
    "timeout",
    "crash",
    "refused_save",
]

TAG = "v0.9.21"
VERSION = version_of(TAG)
WHEEL_NAME = asset_names(VERSION)[0]
REPO = "4zhmv6zvj2-afk/grokbot-essay-writer"
UNEXPECTED = "unexpected"


def disclaimer_for(version: str) -> str:
    return (
        f"These four runs are simulations on installed essay-writer {version}. "
        "They are not validation with real students."
    )


DISCLAIMER = disclaimer_for(VERSION)
NONE_KEY = "(none)"

ESSAY_SENTINEL = "The fisheries opening stayed on the page."
PATH_SENTINEL = "/Users/student/essay.txt"
FORBIDDEN: tuple[str, ...] = (
    ESSAY_SENTINEL,
    PATH_SENTINEL,
    "/Users/",
    "/Volumes/",
)

CODE_RE = re.compile(r"^[a-z][a-z0-9_]*(?:-[a-z0-9_]+)*$")
TOOL_RE = re.compile(r"^[a-z0-9._-]+$")
STAGE_NUM_RE = re.compile(r"^[0-9]{1,2}[a-z]?$")
STAGE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,31}$")
EXC_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
BUILD_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

SEVERITIES: tuple[Severity, ...] = ("error", "info", "warn")
DISPOSITIONS: tuple[Disposition, ...] = ("fallback", "refuse", "retry")
OBSERVED_VALUES: tuple[Observed, ...] = (
    "killed",
    "not_observed",
    "noted",
    "previous_bytes_kept",
    "refused",
    "replaced",
)
STEP_IDS: frozenset[StepId] = frozenset(
    {
        "open",
        "gather",
        "draft",
        "review",
        "final",
        "walk_2",
        "walk_4b",
        "stages_short",
        "malformed_payload",
        "timeout",
        "crash",
        "refused_save",
    }
)

FAULT_ORIGIN: dict[FaultKind, FaultOrigin] = {
    "timeout": "harness",
    "crash": "harness",
    "malformed_payload": "product",
    "refused_save": "product",
}

INCIDENT_FIELDS: tuple[str, ...] = (
    "build",
    "code",
    "disposition",
    "exc",
    "severity",
    "stage",
    "tool",
)
DROPPED_INCIDENT_KEYS: tuple[str, ...] = ("message", "prompt", "sequence", "time")

SECTION_TITLES: tuple[str, ...] = (
    "By code",
    "By severity",
    "By disposition",
    "By tool",
    "By stage",
    "By persona",
    "By fault product",
    "By fault harness",
)


class PersonaSpec(TypedDict):
    persona: PersonaName
    steps: tuple[StepId, ...]
    faults: tuple[FaultKind, ...]


class IncidentRow(TypedDict):
    build: str
    code: str
    disposition: Disposition
    exc: str
    severity: Severity
    stage: str
    tool: str
    persona: PersonaName


class FaultResult(TypedDict):
    persona: PersonaName
    fault: FaultKind
    origin: FaultOrigin
    observed: Observed


class PersonaRun(TypedDict):
    persona: PersonaName
    version: str
    steps: list[StepId]
    faults: list[FaultKind]
    incident_count: int
    stopped: bool
    stop_code: str


class CountBucket(TypedDict):
    key: str
    count: int


class PilotReport(TypedDict):
    simulation: Literal[True]
    version: str
    disclaimer: str
    runs: list[PersonaRun]
    by_code: list[CountBucket]
    by_severity: list[CountBucket]
    by_disposition: list[CountBucket]
    by_tool: list[CountBucket]
    by_stage: list[CountBucket]
    by_persona: list[CountBucket]
    by_fault_product: list[CountBucket]
    by_fault_harness: list[CountBucket]
    dropped_rows: int
    dropped_runs: int


PERSONAS: tuple[PersonaSpec, ...] = (
    {
        "persona": "careful",
        "steps": ("open", "gather", "draft", "review", "final"),
        "faults": (),
    },
    {
        "persona": "rushed",
        "steps": ("open", "gather", "walk_2"),
        "faults": (),
    },
    {
        "persona": "non-native",
        "steps": ("open", "gather", "stages_short", "review", "final"),
        "faults": (),
    },
    {
        "persona": "error-prone",
        "steps": (
            "open",
            "gather",
            "walk_4b",
            "malformed_payload",
            "timeout",
            "crash",
            "refused_save",
        ),
        "faults": ("malformed_payload", "timeout", "crash", "refused_save"),
    },
)

PERSONA_NAMES: frozenset[str] = frozenset(spec["persona"] for spec in PERSONAS)


def contains_forbidden(value: object) -> bool:
    if isinstance(value, str):
        return any(item in value for item in FORBIDDEN)
    if isinstance(value, dict):
        return any(
            contains_forbidden(key) or contains_forbidden(item) for key, item in value.items()
        )
    if isinstance(value, list):
        return any(contains_forbidden(item) for item in value)
    return False


def parse_persona(value: object) -> PersonaName | None:
    if isinstance(value, str) and value in PERSONA_NAMES:
        return cast(PersonaName, value)
    return None


def parse_step(value: object) -> StepId | None:
    if isinstance(value, str) and value in STEP_IDS:
        return cast(StepId, value)
    return None


def parse_fault_kind(value: object) -> FaultKind | None:
    if isinstance(value, str) and value in FAULT_ORIGIN:
        return cast(FaultKind, value)
    return None


def parse_origin(value: object) -> FaultOrigin | None:
    if value == "product" or value == "harness":
        return value
    return None


def parse_observed(value: object) -> Observed | None:
    if isinstance(value, str) and value in OBSERVED_VALUES:
        return cast(Observed, value)
    return None


def parse_severity(value: object) -> Severity | None:
    if isinstance(value, str) and value in SEVERITIES:
        return cast(Severity, value)
    return None


def parse_disposition(value: object) -> Disposition | None:
    if isinstance(value, str) and value in DISPOSITIONS:
        return cast(Disposition, value)
    return None


def stage_ok(value: str) -> bool:
    if value == "":
        return True
    if STAGE_NUM_RE.fullmatch(value):
        return True
    return STAGE_NAME_RE.fullmatch(value) is not None


def tool_ok(value: str) -> bool:
    return value == "" or TOOL_RE.fullmatch(value) is not None


def make_fault(persona: PersonaName, fault: FaultKind, observed: Observed) -> FaultResult:
    return {
        "persona": persona,
        "fault": fault,
        "origin": FAULT_ORIGIN[fault],
        "observed": observed,
    }


def make_run(
    persona: PersonaName,
    steps: list[StepId],
    faults: list[FaultKind],
    incident_count: int,
    stopped: bool,
    stop_code: str,
    version: str = VERSION,
) -> PersonaRun:
    if not stopped:
        code = ""
    elif CODE_RE.fullmatch(stop_code):
        code = stop_code
    else:
        code = UNEXPECTED
    return {
        "persona": persona,
        "version": version,
        "steps": steps,
        "faults": faults,
        "incident_count": incident_count,
        "stopped": stopped,
        "stop_code": code,
    }
