# grep — find files by content

[← tool index](index.md) · `tools/grep.py`

| group | targets | composed? | policy | git | paginated | friction |
|---|---|---|---|---|---|---|
| search | file | primitive | search (+ read in content mode) | — | ✓ | — |

> Search file contents for a pattern (substring or regex). Default returns
> matching file paths only (cheap). Use mode="content" to see the matching
> lines with context. Use when you know roughly what's inside the file.

## Args

| Arg | Type | Default | Notes |
|---|---|---|---|
| `pattern` | str | required | substring or regex (invalid regex falls back to literal substring) |
| `scope` | str | sandbox root | folder to search within |
| `mode` | `"files"` \| `"content"` | `"files"` | files = paths only |
| `context_lines` | int | 2 | content mode only |
| `offset` / `limit` | int | 0 / 50 | result paging (0-based skip count) |

## Returns

**Files mode** — paths with per-file match counts:

```
data/sales_2024.csv · 1
data/sales_2025.csv · 2
```

**Content mode** — `path:line` blocks whose output feeds
[read](read.md)`(offset=…)` and [edit](edit.md) directly (`:` marks the
match, `-` marks context, blocks separated by `--`):

```
notes.txt:1- alpha
notes.txt:2: beta
notes.txt:3- gamma
```

## The budget decision

Files-only default is deliberate: unbounded content-mode results are the
read-side equivalent of copying through context. The hard result cap (200)
truncates honestly and **refuses continuation** — narrowing is the answer:

```
200+ matches, showing 1–50 — narrow the pattern or scope
```

Uncapped truncation still offers it:

```
73 matches, showing 1–50 — narrow the pattern or scope, or continue with offset=50
```

## Policy

Content mode returns file content, so it additionally requires
`read(scope)` via the `conditional_groups` hook — find-but-not-read zones
stay sealed while files mode keeps working. See
[Policy](../policy.md#mode-conditional-requirements). Binary files,
`_trash/`, `.git/`, and `.fsagent/` (the model's own scratchpad) are
skipped.

## Deferred

Handler-aware match modes (e.g. CSV column-scoped search) — flag 3 in
[FLAGS.md](../../FLAGS.md).
