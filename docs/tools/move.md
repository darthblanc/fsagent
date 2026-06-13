# move — relocate or rename

[← tool index](index.md) · `tools/move.py`

| group | targets | composed? | policy | git | paginated | friction |
|---|---|---|---|---|---|---|
| mutate-structure | both | primitive | mutate-structure | ✓ | — | overwrite |

> Move a file or folder to a new path. Renaming is moving within the same
> directory. Replacing an existing destination file requires overwrite=true.

One tool for both targets — one intent: "relocate this thing".

## Args

`src` (required) · `dest` (required) · `overwrite` (default false).

## Returns

Old → new confirmation + tier flag:

```
moved '/sb/draft.txt' → '/sb/final.txt'
```

## Friction on collision

An existing destination **file** is a [friction](../friction.md) denial:

```
destination '/sb/b.txt' exists — pass overwrite=true
```

An existing destination **folder** never offers `overwrite=true` — folder
clobbering isn't expressible. The failure routes the likely intent
(Unix-`mv`-style "move into") to the explicit form:

```
'/sb/archive' is an existing folder — pass the full destination path, e.g. '/sb/archive/a.txt'
```

## Renames in history

Whole-tree staging (`git add -A`) makes moves appear as **renames** in diffs
and history, so review reads naturally and revert restores the old path
([Tiers & recovery](../tiers-and-recovery.md)).

## Other failure shaping

```
'/sb/reprot.txt' not found — similar paths: /sb/report.txt
src and dest are identical — nothing to move
cannot move '/sb/src' into itself
'/sb/missing' not found — create it first with create_dir
```
