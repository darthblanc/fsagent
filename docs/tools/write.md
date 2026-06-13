# write — create or replace a file

[← tool index](index.md) · `tools/write.py`

| group | targets | composed? | policy | git | paginated | friction |
|---|---|---|---|---|---|---|
| mutate-content | file | primitive | mutate-content | ✓ | — | overwrite |

> Write content to a file. Creating a new file needs no flag; replacing an
> existing file requires overwrite=true. For changing part of an existing
> file, use edit instead — it is cheaper and safer.

## Args

| Arg | Default | Notes |
|---|---|---|
| `path` | required | |
| `content` | required | |
| `overwrite` | false | required to replace an existing file |

## Returns

A unified diff — **the model's self-verification loop**. New files get a
full-file diff (`--- /dev/null`); replacements show old vs new; identical
content returns `(no change)`. Plus the tier flag when applicable:

```
tier 3 — this change is NOT reversible
```

## Friction on silent replacement

The first attempt on an existing file fails with what would be lost and the
cheaper alternative ([Friction](../friction.md)):

```
'/sb/report.txt' exists (421 lines) — pass overwrite=true, or use edit
```

The second call with `overwrite=true` is an informed action.

## Failure shaping

```
'/sb/data' is a folder — write targets files only
'/sb/missing' not found — create it first with create_dir
```

Gated, committed, logged — inherited from the group
([Pipeline](../pipeline.md)). Format-aware validation on write (e.g. CSV
column-count checks, which [append](append.md) already does) is a deferred
option — flag 2 in [FLAGS.md](../../FLAGS.md).
