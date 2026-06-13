# Policy — the YAML rule engine

[← wiki home](index.md)

`core/policy.py:YamlPolicy`, loaded from
[`configs/policy.yaml`](../configs/policy.yaml). The policy stage asks
`check(path, group, tool)` for every (path, permission) pair a call
exercises; denials return a **reason and an alternative**.

## Rule format

```yaml
default: allow                     # within the sandbox
rules:
  - path: "sandbox/originals/**"
    deny: [mutate-content, mutate-structure]   # read-only archive
  - path: "sandbox/.index.json"
    deny: [delete, move]                        # agent maintains it, can't destroy it
  - path: "sandbox/inbox/**"
    allow: [read, search, move]                 # may file things away, not edit them
```

### Patterns

Sandbox-relative, spelled with the canonical `sandbox/` prefix regardless of
the actual root directory name. A pattern ending `/**` also matches the base
folder itself — so the read-only archive cannot be deleted whole.

### Vocabulary: groups *and* tools

List entries name **groups** (`read`, `search`, `mutate-content`,
`mutate-structure`) or **tools** (`delete`, `move`, …). The `.index.json`
rule shows why this matters: the agent must *maintain* the file (write, edit,
append — all mutate-content — stay allowed) but must not *destroy* it
(`delete` and `move` are denied by name).

### Allow lists are whitelists

A rule with `allow:` denies everything not listed, for its path. In
`inbox/`, read, search, and move pass — `move` by tool name, even though its
group isn't listed — and edit/write/delete are denied with the whitelist as
the reason: `rule 'sandbox/inbox/**' allows only move, read, search`.

### Optional shaping keys

Rules may carry `reason:` and `alternative:`; otherwise both are generated.
When a rule denies mutation but not read, the generated alternative is the
standard recovery: *"read is still allowed — copy it out and work on the
copy"* — which [copy's policy map](tools/copy.md) is designed to permit.

## Precedence

1. **Specific path beats general** — specificity is the literal (non-wildcard)
   length of the pattern; a `sandbox/drafts/**` allow overrides a
   `sandbox/**` deny.
2. **Deny wins** at equal specificity.
3. **`default`** (`allow` or `deny`) decides when no rule has an opinion.

## Mode-conditional requirements

Search-allowed-but-read-denied is an *intended* policy state: a user may want
the model to **find files but not read them**. Grep's content mode returns
file content (matched lines + context), so it additionally requires
`read(scope)` via the `conditional_groups` hook on its `Tool` — while files
mode stays search-only. Under a deny-read policy, `grep "x"` answers with
paths and counts; `grep "x" mode=content` is denied.

## What consumes decisions

- The [pipeline's policy stage](pipeline.md#stage-2--policy) — every call.
- [inspect](tools/inspect.md) — surfaces the four groups' effective
  permissions per path, so the agent discovers constraints *before* colliding
  with them.

## Pending

Intersection with a session `--scope` (a narrowing wrapper around
`YamlPolicy`) arrives with the CLI — flag 1 in [FLAGS.md](../FLAGS.md).
