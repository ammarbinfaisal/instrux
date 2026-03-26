#!/usr/bin/env python3
"""instrux: generate and manage agent instruction files for projects."""

import argparse
import re
import sys
from pathlib import Path

BLOCKS_DIR = Path(__file__).parent / "blocks"

CLAUDE_MD = "Read and follow all instructions in `instructions.md` before starting any task.\n"

AGENTS_MD = "Read and follow all instructions in `instructions.md` before starting any task.\n"

INSTRUCTIONS_HEADER = "# Instructions"

IGNORE_ENTRIES = ["CLAUDE.md", "AGENTS.md", "instructions.md"]

DEFAULT_BLOCKS = ["parallel-dev", "smart-reuse"]

AGENT_FILES = {
    "claude": ("CLAUDE.md", CLAUDE_MD.strip()),
    "codex": ("AGENTS.md", AGENTS_MD.strip()),
}

BUILTIN_BLOCKS = {
    "parallel-dev": """\
[shared]
When a task spans multiple independent modules or features, prefer parallel \
development over sequential work. Use git worktrees or branches for each track.

Before splitting:
- Define shared interfaces, types, and API contracts upfront. Every track codes \
against these contracts so integration is mechanical, not exploratory.
- Identify internal packages/modules whose APIs will be consumed across tracks. \
Lock those signatures before any track diverges.

Orchestration: if sub-agents are available, the planning agent defines the split \
and contracts, then delegates each track. Sub-agents work in isolation on their \
worktree/branch; merge back on completion. A capable agent may orchestrate peers \
at its own level when the task demands it.

Only parallelize when the coordination cost is clearly less than the time saved. \
Two 30-minute tracks beat one 50-minute sequential job; two 30-minute tracks do \
not beat one 35-minute sequential job.

[codex]
For simple subtasks, prefer medium-reasoning sub-agents with direct, concrete \
ownership. Reserve higher reasoning for genuinely complex branches where the \
extra cost buys down real ambiguity.

[claude]
For simple subtasks, prefer Sonnet-level sub-agents with high effort and \
explicit ownership. Escalate to Opus only when the task is complex enough to \
justify the extra depth.""",
    "smart-reuse": """\
Continuously scan the codebase for reuse opportunities and worthwhile abstractions. \
The bar is practical value, not theoretical purity.

Reuse: if function/component Z can be split into X and Y such that X would serve \
future features (P, Q, ...), do the split when you recognise the concrete benefit. \
The trigger is "I can see the next consumer", not "this could hypothetically be reused."

Abstraction: only introduce one when it demonstrably reduces the edit surface for \
future work. The test: would we change less code to ship features we cannot yet \
predict? If yes, abstract. If it is just tidiness or symmetry with no measurable \
payoff, leave it concrete.

Never abstract preemptively, never for architectural beauty alone. Every abstraction \
must earn its place by making the next task cheaper.""",
}


def ensure_blocks_dir():
    BLOCKS_DIR.mkdir(exist_ok=True)
    for name, content in BUILTIN_BLOCKS.items():
        path = BLOCKS_DIR / f"{name}.txt"
        if not path.exists():
            path.write_text(content.strip() + "\n")


def load_block(name: str) -> str:
    path = BLOCKS_DIR / f"{name}.txt"
    if not path.exists():
        print(f"error: block '{name}' not found in {BLOCKS_DIR}/", file=sys.stderr)
        print(f"  available: {', '.join(available_blocks())}", file=sys.stderr)
        sys.exit(1)
    return path.read_text().strip()


def available_blocks() -> list[str]:
    ensure_blocks_dir()
    return sorted(p.stem for p in BLOCKS_DIR.glob("*.txt"))


def wrap_block(name: str, content: str) -> str:
    return f"<!-- block:{name} -->\n{content}\n<!-- /block:{name} -->"


def parse_blocks(text: str) -> dict[str, str]:
    blocks = {}
    for m in re.finditer(
        r"<!-- block:(\S+) -->\n(.*?)\n<!-- /block:\1 -->", text, re.DOTALL
    ):
        blocks[m.group(1)] = m.group(2)
    return blocks


def split_sectioned_block(text: str) -> dict[str, str]:
    matches = list(
        re.finditer(r"(?m)^\[(shared|claude|codex|agents)\][ \t]*\n?", text)
    )
    if not matches:
        return {"shared": text.strip()}

    sections = {}
    first = matches[0]
    prefix = text[: first.start()].strip()
    if prefix:
        sections["shared"] = prefix

    for index, match in enumerate(matches):
        section = match.group(1)
        if section == "agents":
            section = "codex"
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        if content:
            sections[section] = content

    return sections


def strip_blocks(text: str) -> str:
    stripped = re.sub(
        r"\n*<!-- block:\S+ -->.*?<!-- /block:\S+ -->\n?",
        "\n",
        text,
        flags=re.DOTALL,
    )
    return stripped.strip()


def render_blocks(base: str, blocks: list[tuple[str, str]]) -> str:
    parts = []
    if base.strip():
        parts.append(base.strip())
    parts.extend(wrap_block(name, content) for name, content in blocks)
    return "\n\n".join(parts).strip() + "\n"


def active_blocks_for_path(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return parse_blocks(path.read_text())


def write_agent_file(path: Path, default_base: str, blocks: list[tuple[str, str]]):
    base = default_base
    if path.exists():
        existing_base = strip_blocks(path.read_text())
        if existing_base:
            base = existing_base
    path.write_text(render_blocks(base, blocks))


def collect_active_blocks(target: Path) -> set[str]:
    instructions_path = target / "instructions.md"
    active = (
        set(parse_blocks(instructions_path.read_text()).keys())
        if instructions_path.exists()
        else set()
    )
    for filename, _ in AGENT_FILES.values():
        active.update(active_blocks_for_path(target / filename).keys())
    return active


def block_sections(name: str) -> dict[str, str]:
    return split_sectioned_block(load_block(name))


def update_global_gitignore():
    import os
    import subprocess

    result = subprocess.run(
        ["git", "config", "--global", "core.excludesfile"],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        excludes_file = Path.home() / ".gitignore_global"
        subprocess.run(
            ["git", "config", "--global", "core.excludesfile", str(excludes_file)],
            check=True,
        )
    else:
        raw = result.stdout.strip()
        excludes_file = Path(os.path.expanduser(raw))

    existing = excludes_file.read_text() if excludes_file.exists() else ""
    to_add = [e for e in IGNORE_ENTRIES if e not in existing.splitlines()]
    if to_add:
        with open(excludes_file, "a") as f:
            if existing and not existing.endswith("\n"):
                f.write("\n")
            if not existing.strip():
                f.write("# agent instructions\n")
            for entry in to_add:
                f.write(f"{entry}\n")
        print(f"  updated {excludes_file}")


def update_gitignore(target: Path):
    gitignore = target / ".gitignore"
    if gitignore.exists():
        existing = gitignore.read_text()
        to_add = [e for e in IGNORE_ENTRIES if e not in existing]
        if to_add:
            with open(gitignore, "a") as f:
                f.write("\n# agent instructions\n")
                for entry in to_add:
                    f.write(f"{entry}\n")
            print(f"  updated {gitignore}")
    else:
        with open(gitignore, "w") as f:
            f.write("# agent instructions\n")
            for entry in IGNORE_ENTRIES:
                f.write(f"{entry}\n")
        print(f"  wrote {gitignore}")


def cmd_init(args):
    target = Path(args.target).resolve()
    if not target.is_dir():
        print(f"error: {target} is not a directory", file=sys.stderr)
        sys.exit(1)

    ensure_blocks_dir()
    blocks = DEFAULT_BLOCKS + (args.extra_blocks or [])
    sections_by_block = {name: block_sections(name) for name in blocks}

    for agent, (filename, default_base) in AGENT_FILES.items():
        agent_path = target / filename
        existing = active_blocks_for_path(agent_path)
        for name, sections in sections_by_block.items():
            if agent in sections:
                existing.setdefault(name, sections[agent])
        write_agent_file(agent_path, default_base, list(existing.items()))
        print(f"  wrote {filename}")

    instructions_path = target / "instructions.md"
    shared_blocks = [
        (name, sections["shared"])
        for name, sections in sections_by_block.items()
        if "shared" in sections
    ]
    if instructions_path.exists():
        base = strip_blocks(instructions_path.read_text()) or INSTRUCTIONS_HEADER
        existing = active_blocks_for_path(instructions_path)
        for name, content in shared_blocks:
            existing.setdefault(name, content)
        instructions_path.write_text(render_blocks(base, list(existing.items())))
    else:
        instructions_path.write_text(render_blocks(INSTRUCTIONS_HEADER, shared_blocks))

    print(f"  wrote instructions.md [{', '.join(blocks)}]")
    update_global_gitignore()


def cmd_add(args):
    target = Path(args.target).resolve()
    path = target / "instructions.md"
    if not path.exists():
        print("error: instructions.md not found -- run init first", file=sys.stderr)
        sys.exit(1)

    ensure_blocks_dir()
    if args.block in collect_active_blocks(target):
        print(f"  block '{args.block}' already present")
        return

    sections = block_sections(args.block)

    if "shared" in sections:
        base = strip_blocks(path.read_text()) or INSTRUCTIONS_HEADER
        active = active_blocks_for_path(path)
        active[args.block] = sections["shared"]
        ordered = list(active.items())
        path.write_text(render_blocks(base, ordered))

    for agent, (filename, default_base) in AGENT_FILES.items():
        if agent not in sections:
            continue
        agent_path = target / filename
        active = active_blocks_for_path(agent_path)
        active[args.block] = sections[agent]
        write_agent_file(agent_path, default_base, list(active.items()))

    print(f"  added '{args.block}'")


def cmd_remove(args):
    target = Path(args.target).resolve()
    path = target / "instructions.md"
    if not path.exists():
        print("error: instructions.md not found", file=sys.stderr)
        sys.exit(1)

    found = False
    if path.exists():
        active = active_blocks_for_path(path)
        if args.block in active:
            found = True
            del active[args.block]
            base = strip_blocks(path.read_text()) or INSTRUCTIONS_HEADER
            path.write_text(render_blocks(base, list(active.items())))

    for _, (filename, default_base) in AGENT_FILES.items():
        agent_path = target / filename
        if not agent_path.exists():
            continue
        active = active_blocks_for_path(agent_path)
        if args.block not in active:
            continue
        found = True
        del active[args.block]
        write_agent_file(agent_path, default_base, list(active.items()))

    if not found:
        print(f"  block '{args.block}' not found")
        return

    print(f"  removed '{args.block}'")


def cmd_list(args):
    target = Path(args.target).resolve()
    path = target / "instructions.md"
    all_blocks = available_blocks()

    active = collect_active_blocks(target)

    for name in all_blocks:
        mark = "x" if name in active else " "
        print(f"  [{mark}] {name}")


def main():
    p = argparse.ArgumentParser(prog="instrux", description="instrux: agent instruction scaffolding")
    sub = p.add_subparsers(dest="command")

    s_init = sub.add_parser("init", help="initialize instruction files in target directory")
    s_init.add_argument("target", help="target project directory")
    s_init.add_argument(
        "--with",
        dest="extra_blocks",
        nargs="*",
        default=[],
        help="extra blocks to enable beyond defaults",
    )

    s_add = sub.add_parser("add", help="add a block across shared and agent-specific files")
    s_add.add_argument("block", help="block name")
    s_add.add_argument("target", help="target project directory")

    s_rm = sub.add_parser("remove", help="remove a block from shared and agent-specific files")
    s_rm.add_argument("block", help="block name")
    s_rm.add_argument("target", help="target project directory")

    s_ls = sub.add_parser("list", help="list blocks and their status")
    s_ls.add_argument("target", help="target project directory")

    args = p.parse_args()

    if args.command == "init":
        cmd_init(args)
    elif args.command == "add":
        cmd_add(args)
    elif args.command == "remove":
        cmd_remove(args)
    elif args.command == "list":
        cmd_list(args)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
