# Functions — the primitive layer

[← wiki home](index.md)

`functions/` contains the byte-level implementations. They do the raw work;
**every** add-on — friction confirmations, pagination, git, policy, tiers,
failure shaping — comes from the tool layer and pipeline above.

## The contract

- Bytes in, bytes out: `read` returns `bytes`, `write`/`append` take `bytes`,
  `grep` matches a bytes regex.
- Errors are native `OSError`s (`FileNotFoundError`, `NotADirectoryError`,
  `FileExistsError`, …) — no wrapping, so the tool layer shapes them however
  it wants.
- No safety logic. `write` overwrites unconditionally; `move` is `os.replace`
  (atomic on one filesystem, silently replacing files); `create_dir` is a bare
  `mkdir` with no parents.
- Destructive *parameters* live here when they are raw work — `delete` takes
  `recursive` because rmtree-vs-rmdir is mechanics; the *confirmation* lives
  in the [friction gate](friction.md).
- Rich returns where the layer above needs them: `edit` returns the
  replacement count so uniqueness can be enforced upstream.

## The eleven primitives

| Module | Function | Raw work |
|---|---|---|
| `read_ops.py` | `read(path)` | whole file as bytes |
| | `inspect(path)` | `stat` → frozen `EntryInfo` (path, kind, size, mtime, mode) |
| | `list_dir(path)` | sorted entry names |
| `search_ops.py` | `glob(root, pattern)` | sorted matching paths, files and folders |
| | `grep(path, pattern)` | `(line_number, line)` pairs for a bytes regex |
| `mutate_content_ops.py` | `write(path, data)` | create or overwrite |
| | `edit(path, old, new)` | replace occurrences, return count |
| | `append(path, data)` | append, creating if absent |
| `mutate_structure_ops.py` | `create_dir(path)` | bare `mkdir` |
| | `move(src, dest)` | `os.replace` |
| | `delete(path, recursive=False)` | unlink / rmdir / rmtree |

## Why there is no copy function

Copy is the canonical *composed* tool: `write_bytes(dest, read_bytes(src))`.
Giving it its own primitive would duplicate raw work that already exists and
erase the demonstration that compositions of primitives are how every future
transform enters the registry. See [copy](tools/copy.md).
