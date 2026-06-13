# list_dir — folder contents

[← tool index](index.md) · `tools/list_dir.py`

| group | targets | composed? | policy | git | paginated | friction |
|---|---|---|---|---|---|---|
| read | folder | primitive | read | — | ✓ | — |

> List a folder's entries with name, type, and size. depth > 1 returns an
> indented tree (max 3). For "what's in here structurally" prefer inspect;
> for "find by name" prefer glob.

## Args

| Arg | Default | Notes |
|---|---|---|
| `path` | required | folder |
| `offset` | 0 | entries to skip (0-based — a skip count, unlike read's 1-indexed line offset) |
| `limit` | 200 | max entries per call |
| `depth` | 1 | 1 = flat; 2–3 = indented tree (hard max 3) |

## Returns

One entry per line, sorted:

```
a.txt · file · 5
b.csv · file · 10
sub · folder · -
```

Folder sizes show `-` deliberately — subtree size is
[inspect](inspect.md)'s job; statting subtrees here would break the cheap
listing contract. Trees indent two spaces per level and paginate as
flattened lines. Truncation:

```
entries 1–200 of 431 — next: offset=200
```

## Filtered from display

- `.gitkeep` — [create_dir](create_dir.md)'s git-stage artifact, not content
  the model should reason about.
- `_trash/` and `.git/` — harness plumbing
  ([Tiers & recovery](../tiers-and-recovery.md)).

## Failure shaping

```
'/sb/notes.txt' is a file — list_dir targets folders only (use read)
'/sb/subb' not found — similar paths: /sb/sub
depth must be between 1 and 3, got 4
(empty folder)
```
