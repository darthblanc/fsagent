# Trajectory — the session log

[← wiki home](index.md)

`core/trajectory.py`. Every tool call appends one JSON line to the session's
JSONL file — successes, denials, and errors alike. The trajectory is the
audit record that ties together policy decisions, friction denials, tier
warnings, and git commits (whose messages carry the same session and request
IDs).

## Entry schema

```json
{
  "ts": "2026-06-12T13:31:07.412809+00:00",
  "session": "s-9f2c",
  "request_id": 7,
  "tool": "write",
  "args": {"path": "reports/q1.csv", "content": "…", "overwrite": true},
  "status": "ok",
  "stage": null,
  "error": null,
  "tier": 1,
  "token_estimate": 38
}
```

| Field | Notes |
|---|---|
| `ts` | UTC ISO 8601 |
| `session` | set when the trajectory is constructed; matches git commit tags |
| `request_id` | per-pipeline counter; matches git commit tags |
| `tool`, `args` | the call as made (pre-resolution) |
| `status` | `ok` · `denied` (sandbox/policy/friction refused) · `error` (shaped execute failure) |
| `stage` | where a non-ok call stopped: `lookup`, `sandbox`, `policy`, `friction`, `execute`, `git` |
| `error` | the shaped message, verbatim |
| `tier` | tier of the first file path touched — for creations, classified *after* execute so new files carry their real tier |
| `token_estimate` | `len(result) // 4`, success only — the cost of what crossed the membrane |

## What it's for

- **Denial analysis**: every policy and friction refusal is in the log with
  its reason — "healthy trajectories" can be measured (the inspect spec
  expects inspect to be the most-called tool in them).
- **Audit**: `request_id` + `session` link an entry to the exact git commit
  that captured its mutation.
- **Tier accounting**: tier warnings appear here even when the tool output
  didn't flag them (reads of tier-3 files, for instance).

Session summaries (aggregating per-session token totals, tier warnings, and
denials) belong to the future agent/cli layers — see [Roadmap](roadmap.md).
