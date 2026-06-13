# create_dir — make a folder

[← tool index](index.md) · `tools/create_dir.py`

| group | targets | composed? | policy | git | paginated | friction |
|---|---|---|---|---|---|---|
| mutate-structure | folder | primitive | mutate-structure | ✓ (.gitkeep) | — | — |

> Create a directory (parents created as needed).

## Args

`path` (required).

## Returns

Confirmation:

```
created '/sb/data/raw'
created '/sb/a/b/c' (including 2 parent folders)
```

## The .gitkeep drop

Git does not track empty directories, so create_dir silently drops a
`.gitkeep` inside the new folder — the empty directory is tracked and
rollback restores it ([Tiers & recovery](../tiers-and-recovery.md)). Only
the leaf gets the marker (parents contain their children).
[list_dir](list_dir.md) filters `.gitkeep` from display, and the
[recursive-friction census](../friction.md) excludes it from emptiness.

## Idempotent-shaped failure

"Already exists" is informative, not fatal — a normal result that leaves
contents untouched:

```
'/sb/data/raw' already exists
```

The only true failure is a file in the way:

```
'/sb/raw' is a file — cannot create a folder there
```
