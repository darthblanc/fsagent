# inspect — cheap structural probe (the agent's eyes)

[← tool index](index.md) · `tools/inspect.py`

| group | targets | composed? | policy | git | paginated | friction |
|---|---|---|---|---|---|---|
| read | both | primitive | read | — | — | — |

> Describe a file or folder without reading its contents: type, size,
> structure, versioning tier, and what you are permitted to do to it. Call
> this before expensive reads and before any mutation.

Expected to be the most-called tool in healthy trajectories. The ~100-token
JSON budget makes this schema the most load-bearing in the system.

## Args

`path` (str, required) — file or folder.

## Returns

```json
// file
{ "type": "file", "format": "csv", "size_bytes": 48211, "tier": 1,
  "permissions": ["read", "search", "mutate-content", "mutate-structure"],
  "structure": { "headers": ["date","region","revenue"], "rows": 421 },
  "mtime": "2026-04-02T11:30:00Z" }

// folder
{ "type": "folder", "entries": {"files": 34, "dirs": 5},
  "subtree_size_bytes": 18112304, "max_depth": 3, "tier_3_files": 1,
  "permissions": ["read", "search"],
  "by_extension": {"csv": 19, "pdf": 8, "txt": 7} }
```

- **`permissions`** are the *effective* policy per group — the pipeline
  injects the live [policy](../policy.md), so a read-only zone is visible up
  front, before the agent collides with it.
- **`tier`** surfaces the [versioning guarantee](../tiers-and-recovery.md)
  before acting; folders report `tier_3_files` in the subtree.
- **`structure`** is handler-provided per format: CSV headers + row count,
  JSON top-level keys (or array length), Markdown heading outline, plain-text
  line count. Lists are capped at 20 entries for the token budget.

## Cheapness guarantees

Structure is parsed only for tier-1 files: binaries get no structure, and
tier-3 files are **never content-parsed** (their tier is decided by size
alone) — the probe stays cheap even on a 50 MB file. Folder summaries
exclude harness plumbing (`_trash/`, `.git`) and the model's own
`.fsagent/` scratchpad (kept out to avoid clutter, not secrecy).

## Failure shaping

```
'/sb/sales2024.csv' not found — similar paths: /sb/sales_2024.csv
```
