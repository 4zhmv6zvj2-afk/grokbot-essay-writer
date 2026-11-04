"""Human clarify_context for full research.

objective, background, issues, and guidance must each be answered or
explicitly left open. Missing keys are not treated as leave_open.
"""

from __future__ import annotations

KEYS = ("objective", "background", "issues", "guidance")


def parse_clarify(value: object) -> tuple[dict[str, object] | None, list[str]]:
    if not isinstance(value, dict):
        return None, [
            "clarify_context is required. Give objective, background, issues, and "
            "guidance. Each one is a non-empty answer or {\"leave_open\": true}. "
            "leave_open is the human's choice and is not filled in by the door."
        ]
    unknown = sorted(set(value) - set(KEYS))
    errors: list[str] = []
    if unknown:
        errors.append("unknown clarify_context keys: " + ", ".join(unknown))
    parsed: dict[str, object] = {}
    for key in KEYS:
        if key not in value:
            errors.append(
                f"{key} is missing. leave_open is not assumed; a person must answer "
                f"or set {key} to {{\"leave_open\": true}}."
            )
            continue
        item = value[key]
        if isinstance(item, str) and item.strip():
            parsed[key] = {"answer": item.strip()}
            continue
        if isinstance(item, dict) and set(item) == {"leave_open"} and item.get("leave_open") is True:
            parsed[key] = {"leave_open": True}
            continue
        if (
            isinstance(item, dict)
            and set(item) == {"answer"}
            and isinstance(item.get("answer"), str)
            and item["answer"].strip()
        ):
            parsed[key] = {"answer": item["answer"].strip()}
            continue
        errors.append(
            f"{key} needs a non-empty answer or {{\"leave_open\": true}}. "
            "A false or blank leave_open is not an answer."
        )
    if errors:
        return None, errors
    return parsed, []
