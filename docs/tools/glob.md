# glob — find paths by name pattern

[← tool index](index.md) · `tools/glob.py`

| group | targets | composed? | policy | git | paginated | friction |
|---|---|---|---|---|---|---|
| search | both | primitive | search | — | ✓ | — |

> Find files and folders whose paths match a glob pattern, e.g. `**/*.csv`.
> Returns paths only — cheap. Use when you know roughly the name.

## Args

| Arg | Default | Notes |
|---|---|---|
| `pattern` | required | e.g. `**/*.csv` |
| `scope` | sandbox root | folder to search within |
| `offset` | 1 | 1-indexed first match |
| `limit` | 100 | max matches per call |

## Returns

Matched paths only, sorted, relative to the scope — no stat calls, no sizes.
Truncation suggests narrowing first, continuing second:

```
312 matches, showing 1–100 — narrow the pattern or continue with offset=101
```

No matches is information, not an error: `no matches for '*.rs'`.

## Design notes

- **The model never chooses a traversal algorithm** — BFS/DFS is
  implementation, not interface; only `pattern` and `scope` cross the
  membrane.
- An explicit `scope` is sandbox-resolved and policy-checked like any path;
  an *omitted* scope gets the injected sandbox root, which the pipeline
  policy-checks as the effective scope — defaulting never bypasses
  [policy](../policy.md).
- `_trash/` and `.git/` subtrees are invisible to matches
  ([Tiers & recovery](../tiers-and-recovery.md)).

## Failure shaping

```
invalid pattern '/etc/*': …
'/sb/missing' not found — similar paths: …
'/sb/notes.txt' is a file — scope must be a folder
```
