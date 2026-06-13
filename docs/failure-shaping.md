# Failure shaping

[← wiki home](index.md)

Every failure in fsagent is a navigation aid: it tells the model what is
true and what to do next, instead of leaving it to guess. A denial or error
is never a dead end — it is the cheapest possible course correction. The
exact strings are pinned by [exact-string tests](testing.md).

## Wrong path

Typos get suggestions (difflib over the parent directory):

```
'/sb/sales2024.csv' not found — similar paths: /sb/sales_2024.csv
```

Wrong target type gets routed to the right tool:

```
'/sb/data' is a folder — read targets files only (use list_dir)
'/sb/notes.txt' is a file — list_dir targets folders only (use read)
'/sb/nope.txt' not found — use write to create it          (append)
'/sb/missing' not found — create it first with create_dir   (write/move/copy dest parent)
```

## Truncation as continuation instruction

Notices are pasteable instructions, not flags:

```
lines 1–500 of 2,381 — next: offset=501                      (read)
entries 1–200 of 431 — next: offset=200                       (list_dir)
312 matches, showing 1–100 — narrow the pattern or continue with offset=101   (glob)
```

Grep's **hard cap** deliberately refuses continuation — paging deep into a
capped scan is the context-copying antipattern the files-first default
exists to prevent:

```
200+ matches, showing 1–50 — narrow the pattern or scope
```

## Structured-data navigation (read's JSON selector)

Arrays are where dotted paths go wrong, so each failure teaches the syntax:

```
selector="x.y"    →  x is an array[3], not an object — index it: x.0.y
selector="x.5.y"  →  index 5 out of range — x has 3 elements (0–2)
selector="x.0.z"  →  no key 'z' at x.0 — available keys: y, name, id
```

Same pattern for CSV and Markdown — unknown names list what exists:

```
no column 'scores' — available columns: name, team, score
no heading 'Install' — available headings: Title, Setup, Usage
```

## Validation with the expected shape

```
file has 3 columns (date,region,revenue); got 2               (append to CSV)
```

## Friction denials

First attempts on destructive actions fail with everything needed for an
informed retry — see [Friction](friction.md) for the full catalog
(overwrite, unique-match, recursive census).

## Policy denials

Reason plus alternative, rule-supplied or generated:

```
policy denied mutate-content on '…': rule 'sandbox/originals/**' denies
mutate-content — alternative: read is still allowed — copy it out and work on the copy
```

The "copy it out" recovery is not just prose — copy's
[policy map](tools/copy.md) guarantees the suggested workflow is actually
permitted in read-only zones.

## Empty results are information, not errors

```
no matches for '*.rs'        (glob)
no matches for 'zzz'         (grep)
(empty file)                 (read)
(empty folder)               (list_dir)
'/sb/raw' already exists     (create_dir — idempotent-shaped)
```
