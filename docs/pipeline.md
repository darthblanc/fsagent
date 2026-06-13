# The pipeline

[← wiki home](index.md)

`core/pipeline.py`. Every tool call passes through six stages, in order. A
failure at any stage aborts the call **and is still recorded** in the
[trajectory](trajectory.md) with the stage that refused it.

```
Sandbox → Policy → Friction → Execute → Git → Trajectory
```

## Stage 1 — Sandbox (`core/sandbox.py`)

Every path argument (`path`, `src`, `dest`, `scope`) is resolved: relative
paths against the sandbox root, absolute paths verified to lie inside it.
Escapes (`../`, symlinks, outside absolutes) raise `SandboxViolation`:

```
'../secret.txt' resolves outside the sandbox — the world ends at /…/sandbox
```

Handlers only ever receive resolved `Path`s. This is where the world ends.

## Stage 2 — Policy (`core/policy.py`)

`check(path, group, tool)` against the standing YAML rules (see
[Policy](policy.md)). Three checking modes:

- **Per-arg policy map** (composed tools): exactly the declared
  `(arg → group)` pairs are checked — copy checks `read(src)` and
  `mutate-structure(dest)`, nothing more.
- **Cartesian fallback** (no map): every path arg × every group in
  `policy_union`. Fails closed.
- **Conditional groups**: args-dependent extras declared on the `Tool` —
  grep adds `read` when `mode="content"`.

**Effective scope:** when a scope-defaulting tool (glob, grep) is called with
no path args, the injected sandbox root is policy-checked as the effective
scope — defaulting the scope never bypasses policy.

Denials raise `PolicyDenial` with the rule's reason and alternative:

```
policy denied mutate-content on '…/originals/a.csv': rule 'sandbox/originals/**'
denies mutate-content — alternative: read is still allowed — copy it out and
work on the copy
```

## Stage 3 — Friction (`core/friction.py`)

`StandardFriction` (the default) checks the declaration's friction classes
against the call's arguments and raises `FrictionRequired` when a
confirmation is due. First attempt fails informatively; the retry is an
informed action. See [Friction](friction.md).

## Stage 4 — Execute

The tool's handler runs on the resolved arguments. **Handler-extras
injection**: the pipeline inspects the handler signature and supplies, by
parameter name:

| Parameter | Injected value | Used by |
|---|---|---|
| `policy` | the live policy | inspect (effective permissions) |
| `tier_threshold` | the pipeline's tier-3 threshold | inspect, write, edit, append, move, copy, delete |
| `sandbox_root` | resolved sandbox root | glob, grep (default scope), delete (`_trash/` staging) |

Handlers raise `ToolError` with [shaped messages](failure-shaping.md);
those record as `status: "error", stage: "execute"`.

## Stage 5 — Git (`core/gitstage.py`)

Tools declaring `git=True` trigger `GitCommit`: init-on-first-commit,
`git add -A`, message `{tool} [session={id} request={n}]`. Tier-3 files are
excluded by size policy via `.git/info/exclude`, rewritten before each
commit. Whole-tree staging makes moves appear as renames in history. See
[Tiers & recovery](tiers-and-recovery.md).

## Stage 6 — Trajectory (`core/trajectory.py`)

Every call — success, denial, or error — appends one JSONL entry with the
call, args, status, failing stage, tier, and token estimate. See
[Trajectory](trajectory.md).

## Statuses

| Exception | Status | Meaning |
|---|---|---|
| `SandboxViolation`, `PolicyDenial`, `FrictionRequired` | `denied` | the harness refused; nothing executed |
| any other `ToolError` | `error` | the tool ran into a shaped failure |
| (none) | `ok` | result returned |
