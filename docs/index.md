# fsagent wiki

Documentation for the fsagent harness. If you read in order, each page builds
on the previous one; every page links back here.

## Core concepts (read in order)

1. [Architecture](architecture.md) — the three layers, the membrane, the
   design principles everything else follows.
2. [Tool declarations](tool-declarations.md) — the `ToolDefinition` schema:
   what every tool must declare, and what the schema refuses to accept.
3. [Functions](functions.md) — the byte-level primitive layer underneath
   the tools.
4. [Pipeline](pipeline.md) — Sandbox → Policy → Friction → Execute → Git →
   Trajectory, in depth.

## The control stages

5. [Policy](policy.md) — the YAML rule engine: groups and tools in rules,
   whitelists, precedence, shaped denials.
6. [Friction](friction.md) — overwrite, unique-match, and recursive
   confirmations; first attempt fails informatively, the retry is an
   informed action.
7. [Tiers & recovery](tiers-and-recovery.md) — what the harness can honestly
   promise about reversibility, and the machinery behind it (git auto-commit,
   `_trash/` staging).
8. [Trajectory](trajectory.md) — the append-only session log.

## Design language

9. [Failure shaping](failure-shaping.md) — the catalog of errors that tell
   the model what to do next.
10. [Testing](testing.md) — TDD conventions and how the shaped messages are
    pinned by exact-string tests.
11. [Roadmap](roadmap.md) — open flags and unbuilt layers.

## Reference

12. [Agent & sub-agents](agent.md) — wiring tools to a model; the `explore`
    read-only sub-agent and how it shares enforcement.
13. [Tool reference](tools/index.md) — one page per tool, with args, returns,
    and verbatim failure examples.
