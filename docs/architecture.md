# Architecture

[← wiki home](index.md)

fsagent is built as three layers with one boundary — the **membrane** —
between the model and the filesystem.

## The three layers

```
 model ──▶ pipeline (core/) ──▶ tools (tools/) ──▶ functions (functions/) ──▶ bytes
            containment,         intent +            raw work only
            policy, friction,    presentation
            git, logging
```

### functions/ — raw work only

Eleven byte-level primitives (see [Functions](functions.md)). They do exactly
what their syscall does and nothing else: no validation beyond the OS's own
errors, no pagination, no confirmations, no git, no policy. `write` overwrites
unconditionally; `delete` takes a `recursive` parameter because the parameter
is raw work — the *confirmation* is not.

### tools/ — intent and presentation

The twelve tools (see [Tool reference](tools/index.md)) wrap primitives with
everything model-facing: pagination with continuation instructions, per-format
selectors and structure summaries, diffs as verification loops, and
[failure shaping](failure-shaping.md). Each tool module contains:

- `DEFINITION` — its [ToolDefinition](tool-declarations.md) declaration,
- `DESCRIPTION` — the **only** model-facing prose (module docstrings document
  implementation contract for humans and never duplicate it),
- `run(...)` — the execute-stage handler,
- `TOOL` — the registry entry.

### core/ — the pipeline

Every call passes through six stages (see [Pipeline](pipeline.md)). The
pipeline owns everything the model must not be able to influence: sandbox
containment, policy decisions, friction gates, auto-commit, and the
trajectory log.

## The membrane

The membrane is the budget-and-safety boundary between context and
filesystem. Its rules:

- **No unbounded bytes cross it.** Reads are paginated with a hard character
  cap; tier-3 files are fully readable, just never all at once.
- **Work that doesn't need the model doesn't involve the model.** Copy is
  `write_bytes(dest, read_bytes(src))` below the membrane — zero tokens
  regardless of size, perfect fidelity, no regeneration-corruption risk.
- **Tool boundaries match intent categories, not implementation categories.**
  The model says "find paths matching this pattern"; it never chooses a
  traversal algorithm. One `move` tool serves files and folders because
  "relocate this thing" is one intent.
- **Some machinery is invisible by design.** Deletion staging to `_trash/`
  and the git repository itself live below the membrane: read and search
  tools filter them (`HIDDEN_DIRS` in `tools/common.py`), and confirmations
  never mention them. See [Tiers & recovery](tiers-and-recovery.md).
- **The model's own scratchpad is hidden from browsing, not from the
  model.** `.fsagent/scratchpad.md` is also filtered via `HIDDEN_DIRS`, but
  for a different reason than `_trash`/`.git`: the model is told this exact
  path in `prompts/system.md` and addresses it directly with its normal
  tools — it's just kept out of `list_dir`/`glob`/`grep`/`inspect` so it
  doesn't clutter casual browsing of the sandbox.

## Design principles

1. **Declaration-time metadata the model cannot influence.** Policy maps,
   friction classes, and git gating are fixed when a tool is defined. A model
   cannot talk its way into weaker checks.
2. **Failures are navigation aids.** Every denial returns a reason and an
   alternative; every error tells the model the next move. See
   [Failure shaping](failure-shaping.md).
3. **Honest guarantees.** Tier flags appear before expensive reads, after
   mutations, in the trajectory — and the harness never claims reversibility
   it can't deliver. See [Tiers & recovery](tiers-and-recovery.md).
4. **Friction, not gates.** Destructive actions need an informed second
   attempt, not a human in the loop. See [Friction](friction.md).

## Directory map

```
core/
  tool_definition.py   ToolDefinition schema + validation + ComposedPolicyWarning
  tool.py              Tool dataclass (definition, description, handler, conditional_groups)
  pipeline.py          the six-stage orchestrator
  sandbox.py           stage 1 — containment
  policy.py            stage 2 — YamlPolicy engine + AllowAllPolicy
  friction.py          stage 3 — StandardFriction + shared shaping helpers
  gitstage.py          stage 5 — GitCommit / NoGit
  trajectory.py        stage 6 — JSONL logging
  tiers.py             tier classification + guarantees
  errors.py            ToolError and its denial subclasses
functions/             read_ops, search_ops, mutate_content_ops, mutate_structure_ops
tools/                 one module per tool + common.py (shared shaping/helpers)
configs/policy.yaml    standing policy rules
tests/                 the whole suite, written test-first
sandbox/               the agent's world
trajectories/          session logs
agent/                 schema.py (Pydantic args_schema), tools.py (StructuredTool +
                       Approvals/interrupt gate), subagent.py (the explore
                       sub-agent), __init__.py (prompt loaders)
cli/                   repl.py (the `fsagent` entry point), models.py (picker)
prompts/               system.md, subagent_system.md — the model-facing behavior contracts
```

See [Agent & sub-agents](agent.md) for how an LLM is wired to this pipeline.
