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

BUILTIN_BLOCKS = {
    "parallel-dev": """\
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
not beat one 35-minute sequential job.""",
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

    (target / "CLAUDE.md").write_text(CLAUDE_MD)
    print(f"  wrote CLAUDE.md")

    (target / "AGENTS.md").write_text(AGENTS_MD)
    print(f"  wrote AGENTS.md")

    instructions_path = target / "instructions.md"
    if instructions_path.exists():
        content = instructions_path.read_text()
        for name in blocks:
            if f"<!-- block:{name} -->" not in content:
                content = content.rstrip() + "\n\n" + wrap_block(name, load_block(name)) + "\n"
        instructions_path.write_text(content)
    else:
        parts = [INSTRUCTIONS_HEADER]
        for name in blocks:
            parts.append(wrap_block(name, load_block(name)))
        instructions_path.write_text("\n\n".join(parts) + "\n")

    print(f"  wrote instructions.md [{', '.join(blocks)}]")
    update_global_gitignore()


def cmd_add(args):
    target = Path(args.target).resolve()
    path = target / "instructions.md"
    if not path.exists():
        print("error: instructions.md not found -- run init first", file=sys.stderr)
        sys.exit(1)

    ensure_blocks_dir()
    content = path.read_text()
    if f"<!-- block:{args.block} -->" in content:
        print(f"  block '{args.block}' already present")
        return

    content = content.rstrip() + "\n\n" + wrap_block(args.block, load_block(args.block)) + "\n"
    path.write_text(content)
    print(f"  added '{args.block}'")


def cmd_remove(args):
    target = Path(args.target).resolve()
    path = target / "instructions.md"
    if not path.exists():
        print("error: instructions.md not found", file=sys.stderr)
        sys.exit(1)

    content = path.read_text()
    pattern = (
        r"\n*<!-- block:"
        + re.escape(args.block)
        + r" -->.*?<!-- /block:"
        + re.escape(args.block)
        + r" -->\n?"
    )
    new_content = re.sub(pattern, "", content, flags=re.DOTALL)
    if new_content == content:
        print(f"  block '{args.block}' not found")
        return

    path.write_text(new_content.strip() + "\n")
    print(f"  removed '{args.block}'")


def cmd_list(args):
    target = Path(args.target).resolve()
    path = target / "instructions.md"
    all_blocks = available_blocks()

    active = {}
    if path.exists():
        active = parse_blocks(path.read_text())

    for name in all_blocks:
        mark = "x" if name in active else " "
        print(f"  [{mark}] {name}")


def main():
    p = argparse.ArgumentParser(prog="instrux", description="instrux: agent instruction scaffolding")
    sub = p.add_subparsers(dest="command")

    s_init = sub.add_parser("init", help="initialize agent files in target directory")
    s_init.add_argument("target", help="target project directory")
    s_init.add_argument(
        "--with",
        dest="extra_blocks",
        nargs="*",
        default=[],
        help="extra blocks to enable beyond defaults",
    )

    s_add = sub.add_parser("add", help="add a block to instructions.md")
    s_add.add_argument("block", help="block name")
    s_add.add_argument("target", help="target project directory")

    s_rm = sub.add_parser("remove", help="remove a block from instructions.md")
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
