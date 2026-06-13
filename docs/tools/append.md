# append — add to the end of a file

[← tool index](index.md) · `tools/append.py`

| group | targets | composed? | policy | git | paginated | friction |
|---|---|---|---|---|---|---|
| mutate-content | file | primitive | mutate-content | ✓ | — | — |

> Append content as new line(s) at the end of a file.

## Args

`path` (required) · `content` (required).

## Returns

Unified diff (the appended lines as pure additions) + tier flag.

## Behavior

- Appended content always starts on a fresh line (a missing trailing newline
  in the file is bridged) and always ends with one — repeated appends can't
  glue rows together.
- **No friction parameter**: append is non-destructive to existing content,
  and [git](../tiers-and-recovery.md) covers the rest.

## Handler-aware validation

Appending to a `.csv` checks every row's column count against the header
*before any byte is written*; a batch with one bad row fails whole, file
untouched:

```
file has 3 columns (date,region,revenue); got 2
```

## Failure shaping

```
'/sb/nope.txt' not found — use write to create it
'/sb/data' is a folder — append targets files only
content must not be empty
```
