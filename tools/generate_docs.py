"""Generate the checklist blocks in docs/academic-writing-helpers.md.

The doc keeps its hand-written router prose. Each **Basics checklist**
block is replaced from the prompt bundle. On a stage that already renders
shared craft, or a shared stage line, the same block then lists those
rules under **Shared rules:**, with a blank line before that label and
after those bullets.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from essay_writer.prompt_content import CRAFT_BY_STAGE, SHARED_STAGE_LINES
from essay_writer.prompt_loader import text
from essay_writer.stage_llm import STAGE_KEYS, UNTRUSTED_FENCE, stage_settings
from essay_writer.writing_basics import CHECKLISTS

SHARED_RULES_MARK = "**Shared rules:**"

DOC = Path("docs/academic-writing-helpers.md")
BOT = Path("docs/templates/bot.md")
BOT_SHELL = Path("tools/doc_templates/bot.md")
WORKFLOW = Path("docs/workflow.md")
WORKFLOW_SHELL = Path("tools/doc_templates/workflow.md")
SEATS = Path("src/essay_writer/prompts/seats")
HARVARD = Path("docs/referencing-harvard.md")
BOT_BLOCKS = {
    "standing_heading": ("front_office/chat.md", "standing_heading"),
    "stage_confirm_each": ("front_office/confirm.md", "stage_confirm_each"),
    "stage7_after_answers": ("front_office/confirm.md", "stage7_after_answers"),
    "stage9_own_words": ("front_office/chat.md", "stage9_own_words"),
}
MARKER = re.compile(r"\*\*Basics checklist(?: \(([^)]+)\))?:\*\*")


def _stage(match: re.Match[str], text: str) -> str:
    explicit = match.group(1)
    if explicit:
        return explicit
    before = text[: match.start()]
    headings = [line for line in before.splitlines() if line.startswith("### ")]
    if not headings:
        raise SystemExit("checklist block has no stage heading")
    return headings[-1].split(".", 1)[0].removeprefix("### ").strip()


def _stage_block(stage: str) -> str:
    """Checklist bullets, then the shared rules that stage already renders.

    A blank line before the label ends the checklist list. A blank line
    after the shared bullets ends that list.
    """
    lines = [f"- {line}" for line in CHECKLISTS[stage]]
    shared = SHARED_STAGE_LINES.get(stage, ()) + CRAFT_BY_STAGE.get(stage, ())
    block = "\n".join(lines) + "\n"
    if not shared:
        return block
    shared_lines = "\n".join(f"- {line}" for line in shared)
    return block + "\n" + SHARED_RULES_MARK + "\n" + shared_lines + "\n\n"


def render(text: str) -> str:
    matches = list(MARKER.finditer(text))
    if not matches:
        raise SystemExit("no checklist blocks found")
    out: list[str] = []
    cursor = 0
    for index, match in enumerate(matches):
        next_marker = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        heading = re.search(r"(?m)^#{2,} ", text[match.end() :])
        next_heading = match.end() + heading.start() if heading else len(text)
        end = min(next_marker, next_heading)
        stage = _stage(match, text)
        if stage not in CHECKLISTS:
            raise SystemExit(f"unknown checklist stage {stage!r}")
        block = text[match.end() : end]
        lines = block.splitlines(keepends=True)
        start_line = next((i for i, line in enumerate(lines) if line.startswith("- ")), None)
        if start_line is None:
            raise SystemExit(f"no bullets for stage {stage!r}")
        last_line = max(i for i, line in enumerate(lines) if line.startswith("- "))
        start = match.end() + sum(len(line) for line in lines[:start_line])
        stop = match.end() + sum(len(line) for line in lines[: last_line + 1])
        bullets = _stage_block(stage)
        out.append(text[cursor:start])
        out.append(bullets)
        if bullets.endswith("\n\n") and stop < len(text) and text[stop] == "\n":
            stop += 1
        cursor = stop
    out.append(text[cursor:])
    return "".join(out)


def render_seats() -> dict[str, str]:
    harvard = HARVARD.read_text(encoding="utf-8")
    return {
        "write.md": (
            UNTRUSTED_FENCE
            + "\n\n"
            + "When the brief does not name a module-specific writing guide, "
            "use the stage rules and the genre section. The full helper remains at "
            "docs/academic-writing-helpers.md.\n\n"
            + harvard
        ),
    }


def render_workflow() -> str:
    shell = WORKFLOW_SHELL.read_text(encoding="utf-8")
    lines = [
        "Each Academic skills stage and the reviewer has a model, a reasoning effort, fast off, a context window, and the stage prompt we already use.",
        "",
        "| Stage | Model | Reasoning | Fast | Context |",
        "| --- | --- | --- | --- | --- |",
    ]
    for stage in STAGE_KEYS:
        item = stage_settings(stage)
        lines.append(
            f"| {stage} | {item['model']} | {item['reasoning']} | off | {item['context_window']} |"
        )
    lines.extend([
        "",
        "Fast is off on every stage. Context is 256000 on every stage, including stage 4b, the first draft, and EQR.",
        "",
        "Grok Build loads this table from `essay_writer.stage_llm.stage_settings` through `essay_writer.build_office.stage_launch` (`grok --model` and `--effort`). Cursor loads that same function through `essay_writer.cursor_office.cursor_stage_launch` (`agent --model` with the reasoning in the model id). The agent CLI has no context-window flag. `grok-4.7-<reasoning>[context=N]` is rejected. The window is not written into the agent prompt to stand in for a flag.",
    ])
    return shell.replace("<!-- generated:stage_llm -->", "\n".join(lines))


def render_bot() -> str:
    shell = BOT_SHELL.read_text(encoding="utf-8")
    for key, (relative, section) in BOT_BLOCKS.items():
        shell = shell.replace(f"<!-- generated:{key} -->", text(relative, section))
    return shell


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if not args.check and not args.write:
        parser.error("use --check or --write")
    bot_current = BOT.read_text(encoding="utf-8")
    bot_generated = render_bot()
    if args.write:
        if bot_generated != bot_current:
            BOT.write_text(bot_generated, encoding="utf-8")
    elif bot_generated != bot_current:
        print("docs/templates/bot.md is stale; run with --write", file=sys.stderr)
        return 1
    workflow_current = WORKFLOW.read_text(encoding="utf-8")
    workflow_generated = render_workflow()
    if args.write:
        if workflow_generated != workflow_current:
            WORKFLOW.write_text(workflow_generated, encoding="utf-8")
    elif workflow_generated != workflow_current:
        print("docs/workflow.md is stale; run with --write", file=sys.stderr)
        return 1
    seats = render_seats()
    for name, value in seats.items():
        path = SEATS / name
        if args.write:
            if path.read_text(encoding="utf-8") != value:
                path.write_text(value, encoding="utf-8")
        elif path.read_text(encoding="utf-8") != value:
            print(f"{path} is stale; run with --write", file=sys.stderr)
            return 1
    current = DOC.read_text(encoding="utf-8")
    generated = render(current)
    if args.write:
        DOC.write_text(generated, encoding="utf-8")
        print(f"wrote {DOC}")
        return 0
    if generated != current:
        print("docs/academic-writing-helpers.md is stale; run with --write", file=sys.stderr)
        return 1
    print("docs/academic-writing-helpers.md is current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
