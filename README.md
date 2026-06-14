# fsagent

A policy-aware filesystem agent harness. An LLM agent gets twelve tools to read,
search, and mutate files inside a sandbox — and every call passes through a
six-stage pipeline that enforces containment, policy, and informed consent,
versions every mutation, and logs every outcome.

The design premise is a **membrane** between the model and the filesystem: tool
boundaries match *intent* categories ("relocate this thing"), never
implementation categories (BFS vs DFS); no operation ever requires unbounded
bytes to cross into context; every failure is shaped to tell the model what to
do next; and every guarantee the harness states is one it actually keeps — it
never silently pretends reversibility where there is none.

## Quick start

```sh
uv venv && uv pip install -e ".[dev]"
uv run pytest        # 303 tests
```

## Running the agent

```sh
uv run fsagent
```

This starts an interactive REPL backed by the agent in [agent/](agent/), acting
on files under [sandbox/](sandbox/). On startup you'll be prompted to pick a
model from [configs/models.yaml](configs/models.yaml) (press enter for the
default), or skip the picker with `--model`:

```sh
uv run fsagent --model anthropic:claude-sonnet-4-6
uv run fsagent --model openai:gpt-5.5
uv run fsagent --model ollama:qwen3:8b
```

Any `anthropic:...`, `openai:...`, or `ollama:...` model works as long as the
corresponding package is installed (`langchain-anthropic` /
`langchain-openai` / `langchain-ollama`, all included by default) and:

- **anthropic** — `ANTHROPIC_API_KEY` is set
- **openai** — `OPENAI_API_KEY` is set
- **ollama** — a local Ollama server is running and the model has been pulled
  (`ollama pull <model>`)

Edit `configs/models.yaml` to change the picker's choices or default.

### Configuration via `.env`

Copy [`.env.example`](.env.example) to `.env` and fill in the keys you need —
it's loaded automatically on startup (`cli/repl.py:load_env`) and never
overrides variables already set in your shell.

To enable [LangSmith](https://smith.langchain.com) tracing, set
`LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY` in `.env`. Each session is
tagged with its model and session ID, and traces are grouped under the
`LANGSMITH_PROJECT` project (defaults to `fsagent`).

## The pipeline

Every tool call passes through, in order:

```
        ┌─────────┐  ┌────────┐  ┌──────────┐  ┌─────────┐  ┌─────┐  ┌────────────┐
 call ─▶│ Sandbox │─▶│ Policy │─▶│ Friction │─▶│ Execute │─▶│ Git │─▶│ Trajectory │─▶ result
        └─────────┘  └────────┘  └──────────┘  └─────────┘  └─────┘  └────────────┘
         paths must   YAML rules  destructive    the         auto-     JSONL log of
         resolve in   ∩ scope;    params need    primitive   commit    every call,
         sandbox/     deny wins   confirmation   runs        (gated)   incl. denials
```

A failure at any stage is still recorded in the trajectory. See
[docs/pipeline.md](docs/pipeline.md).

## The tools

| Tool | Group | Targets | Composed? | Policy checks | Git | Paginated | Friction |
|---|---|---|---|---|---|---|---|
| [read](docs/tools/read.md) | read | file | primitive | read | — | ✓ | — |
| [inspect](docs/tools/inspect.md) | read | both | primitive | read | — | — | — |
| [list_dir](docs/tools/list_dir.md) | read | folder | primitive | read | — | ✓ | — |
| [glob](docs/tools/glob.md) | search | both | primitive | search | — | ✓ | — |
| [grep](docs/tools/grep.md) | search | file | primitive | search (+ read in content mode) | — | ✓ | — |
| [write](docs/tools/write.md) | mutate-content | file | primitive | mutate-content | ✓ | — | overwrite |
| [edit](docs/tools/edit.md) | mutate-content | file | primitive | mutate-content | ✓ | — | unique-match |
| [append](docs/tools/append.md) | mutate-content | file | primitive | mutate-content | ✓ | — | — |
| [create_dir](docs/tools/create_dir.md) | mutate-structure | folder | primitive | mutate-structure | ✓ (.gitkeep) | — | — |
| [move](docs/tools/move.md) | mutate-structure | both | primitive | mutate-structure | ✓ | — | overwrite |
| [copy](docs/tools/copy.md) | mutate-structure | both | read ∘ write | read(src) ∧ mutate-structure(dest) | ✓ | — | overwrite |
| [delete](docs/tools/delete.md) | mutate-structure | both | primitive | mutate-structure | ✓ | — | recursive |

A fifth group, **transform**, is reserved; [copy](docs/tools/copy.md) is the
worked example for how it will enter the registry.

## Documentation

The wiki lives in [docs/](docs/index.md):

- [Architecture](docs/architecture.md) — layers, the membrane, directory map, design principles
- [Tool declarations](docs/tool-declarations.md) — the `ToolDefinition` schema and its validation
- [Functions](docs/functions.md) — the byte-level primitive layer
- [Pipeline](docs/pipeline.md) — the six stages in depth
- [Policy](docs/policy.md) — the YAML rule engine
- [Friction](docs/friction.md) — destructive-parameter confirmations as informed consent
- [Tiers & recovery](docs/tiers-and-recovery.md) — versioning guarantees, git stage, `_trash/` staging
- [Trajectory](docs/trajectory.md) — the session JSONL log
- [Failure shaping](docs/failure-shaping.md) — errors as navigation aids
- [Testing](docs/testing.md) — the TDD conventions
- [Roadmap](docs/roadmap.md) — what's open and what's next
- [Tool reference](docs/tools/index.md) — one page per tool

Open design debts are tracked in [FLAGS.md](FLAGS.md).

## Layout

```
core/          schema, pipeline, policy, friction, git, tiers, trajectory
functions/     byte-level primitives — raw work only
tools/         the 12 tool definitions + execute handlers
configs/       policy.yaml (standing rules)
tests/         303 tests, written test-first
sandbox/       where the world ends — the agent acts only in here
trajectories/  session JSONL logs
agent/ cli/ prompts/   future layers (see docs/roadmap.md)
```
