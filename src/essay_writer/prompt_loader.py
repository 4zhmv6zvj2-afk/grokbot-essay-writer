"""Read prompt content from the package bundle."""

from __future__ import annotations

import json
import re
from functools import cache
from importlib.resources import files
from typing import Any

_ROOT = files("essay_writer.prompts")


@cache
def _text(relative: str) -> str:
    return (_ROOT / relative).read_text(encoding="utf-8")


def raw(relative: str) -> str:
    return _text(relative)


@cache
def sections(relative: str) -> dict[str, str]:
    blocks: dict[str, str] = {}
    key: str | None = None
    body: list[str] = []
    for line in _text(relative).splitlines():
        if line.startswith("## "):
            if key is not None:
                blocks[key] = "\n".join(body).strip()
            key = line[3:].strip()
            body = []
        elif key is not None:
            body.append(line)
    if key is not None:
        blocks[key] = "\n".join(body).strip()
    return blocks


def text(relative: str, key: str) -> str:
    return sections(relative)[key]


def bullets(relative: str, key: str) -> tuple[str, ...]:
    body = sections(relative)[key]
    return tuple(line[2:] for line in body.splitlines() if line.startswith("- "))


@cache
def json_data(relative: str) -> Any:
    return json.loads(_text(relative))


_TOKEN = re.compile(r"\{\{(confirm|status):([a-z0-9_]+)\}\}")


def render_tokens(value: str) -> str:
    def replace(match: re.Match[str]) -> str:
        kind, key = match.group(1), match.group(2)
        relative = "front_office/confirm.md" if kind == "confirm" else "status/mid.md"
        return text(relative, key)

    return _TOKEN.sub(replace, value)
