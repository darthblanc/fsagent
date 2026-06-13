# edit — surgical string replacement

[← tool index](index.md) · `tools/edit.py`

| group | targets | composed? | policy | git | paginated | friction |
|---|---|---|---|---|---|---|
| mutate-content | file | primitive | mutate-content | ✓ | — | unique-match |

> Replace one exact string in a file with another. old_str must match the
> current file content exactly and appear exactly once — read the file first
> to get the exact text. new_str empty deletes the text. This is the
> preferred way to modify files.

## Args

| Arg | Notes |
|---|---|
| `path` | required |
| `old_str` | required; must be unique in the file |
| `new_str` | required; empty = delete the text |

## Returns

Unified diff + tier flag, like [write](write.md).

## The uniqueness rule — the tool's core design

The rule forces read-before-edit and converts silent mis-edits into
explicit, recoverable failures — the membrane's biggest budget and safety
win in one mechanism: a one-line change costs ~40 output tokens instead of a
whole-file rewrite, and a stale or ambiguous match can never corrupt the
file.

**0 matches** — catches stale context by pointing at the nearest line:

```
no exact match — nearest occurrence at line 87: 'revenue_2024 = 100' — re-read and retry with the current text
```

(or, when nothing is similar: `no exact match — re-read the file and retry
with the current text`)

**N > 1 matches** — catches ambiguity:

```
matched 3 locations (lines 12, 87, 240) — include more surrounding context to disambiguate
```

Both leave the file untouched. Enforcement lives in the
[friction stage](../friction.md) (`unique_match_failure`, shared with the
handler as defense in depth), so the trajectory records these as friction
denials.

## Other failure shaping

```
old_str must not be empty — read the file and quote the exact text to replace
old_str and new_str are identical — nothing to change
'/sb/reprot.txt' not found — similar paths: /sb/report.txt
```

## Deferred

Structured handler selectors (edit a JSON path, a CSV cell) are the designed
extension; str-replace is the v2 baseline — flag 2 in
[FLAGS.md](../../FLAGS.md).
