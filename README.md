# instrux

**instruct + ux** — streamlined instructions for AI coding agents.

Manage shared, toggleable prompt blocks across `CLAUDE.md` (Claude Code), `AGENTS.md` (OpenAI Codex), and a common `instructions.md`. Write your guidance once, apply it to any project, swap blocks in and out as needed.

## Why

AI coding agents read markdown files for project context — `CLAUDE.md` for Claude Code, `AGENTS.md` for Codex. You end up copy-pasting the same instructions across repos, or forgetting to update one when you refine your prompts. instrux gives you a single set of reusable, toggleable blocks that get injected into a shared `instructions.md`, with agent-specific files pointing to it.

## Install

```bash
git clone https://github.com/ammarbinfaisal/agent-setup.git instrux
cd instrux
```

No dependencies beyond Python 3.

## Usage

```bash
# scaffold agent files in your project (writes CLAUDE.md, AGENTS.md, instructions.md, updates .gitignore)
./run.sh init /path/to/project

# include extra blocks during init
./run.sh init /path/to/project --with my-custom-block

# toggle blocks on an existing project
./run.sh add my-block /path/to/project
./run.sh remove my-block /path/to/project

# see what's active
./run.sh list /path/to/project
```

## Blocks

Reusable prompt fragments that get wrapped in `<!-- block:name -->` tags inside `instructions.md` — easy to parse, easy to toggle.

Blocks live in `./blocks/` (gitignored, never committed). Defaults are seeded on first run:

| Block | Default | Description |
|---|---|---|
| `parallel-dev` | on | Guide agents to use parallel sub-agents, git worktrees, and pre-planned API contracts when tasks span independent modules |
| `smart-reuse` | on | Teach agents to split and abstract code only when there is a concrete reuse payoff, not for tidiness |

### Custom blocks

Drop any `.txt` file into `blocks/` and it becomes available to all commands. The filename (minus `.txt`) is the block name.

```bash
echo "your prompt here" > blocks/my-rule.txt
./run.sh add my-rule /path/to/project
```

## How it works

- `CLAUDE.md` and `AGENTS.md` both just say: read `instructions.md`.
- `instructions.md` holds your project-specific notes at the top, with toggled blocks appended below.
- Agent instruction files are added to `.gitignore` automatically — they stay local to the developer.
