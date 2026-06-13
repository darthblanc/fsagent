# read — file contents, progressively

[← tool index](index.md) · `tools/read.py`

| group | targets | composed? | policy | git | paginated | friction |
|---|---|---|---|---|---|---|
| read | file | primitive | read | — | ✓ | — |

> Read a file's contents. Returns line-numbered text. Large files are
> returned in pages; the truncation notice tells you how to continue. Prefer
> inspect first and grep to locate, so you read only what you need.

## Args

| Arg | Type | Default | Notes |
|---|---|---|---|
| `path` | str | required | file only |
| `offset` | int | 1 | first line to return (1-indexed) |
| `limit` | int | 500 | max lines per call; a hard character cap (~30k chars) also applies |
| `selector` | str/obj | none | handler-specific slice (below) |

## Returns

`cat -n`-style numbered lines. If truncated, the final line is a
continuation instruction, not a flag:

```
lines 1–500 of 2,381 — next: offset=501
```

The hard cap can end a page early with the same notice — tier-3 files are
fully readable, just never all at once; no operation ever requires unbounded
bytes to cross the membrane.

## Handler selectors

Selected by extension; generic text is the fallback (a selector on plain
text fails with guidance to use offset/limit).

| Format | Selector | Example |
|---|---|---|
| CSV | object | `{"columns": ["date","revenue"], "rows": "head:50"}` · rows: `head:N`, `tail:N`, `start:end` (1-indexed inclusive) |
| JSON | dotted path | `config.database.host` |
| Markdown | heading name | `Setup` — returns the section **with original file line numbers**, so it feeds [edit](edit.md) |

Line numbers exist so the model references locations instead of re-quoting.

## Failure shaping

```
'/sb/sales2024.csv' not found — similar paths: /sb/sales_2024.csv
'/sb/data' is a folder — read targets files only (use list_dir)
```

The JSON-array caveats (each failure teaches the syntax):

```
selector="x.y"    →  x is an array[3], not an object — index it: x.0.y
selector="x.5.y"  →  index 5 out of range — x has 3 elements (0–2)
selector="x.0.z"  →  no key 'z' at x.0 — available keys: y, name, id
```

CSV / Markdown misses list what exists:

```
no column 'scores' — available columns: name, team, score
no heading 'Install' — available headings: Title, Setup, Usage
```
