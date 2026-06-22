# Agent & sub-agents

[← wiki home](index.md)

How `core/`'s pipeline gets wired to an LLM. Two layers: the main agent's
tool wrapping (`agent/tools.py`, `agent/schema.py`), and a read-only
sub-agent (`agent/subagent.py`) exposed to the main agent as a single tool.

## Wiring tools to a model

`agent/schema.py`'s `args_schema_for(tool)` builds a Pydantic model from
each handler's signature, since `agent/tools.py` wraps every handler in an
opaque `**kwargs` function that `StructuredTool` can't introspect on its
own. Params injected by the pipeline (`policy`, `tier_threshold`,
`sandbox_root` — see [Pipeline](pipeline.md#stage-4--execute)) are excluded;
they're never model-settable. A couple of params need explicit type/Field
overrides the handler signature alone doesn't carry — `read`'s `selector`,
`grep`'s `mode`.

`agent/tools.py`'s `build_tools(pipeline, approvals, tools=None)` wraps each
[`Tool`](tool-declarations.md) into a `StructuredTool`, defaulting to every
tool in the registry (`tools=None` → `ALL_TOOLS.values()`) but accepting an
explicit subset — this is what lets the sub-agent below build a restricted
tool list against the *same* pipeline.

**The friction/interrupt gate.** Every `FrictionRequired`
([Friction](friction.md)) carries a `kwarg` naming the parameter a human's
approval should force to `True` on retry — `overwrite` (write/move/copy),
`recursive` (delete), or `replace_all` (edit, when `old_str` matches more
than once) — or `None` when there's nothing to force (edit, zero matches),
in which case it passes straight through as a `ToolException` and the model
corrects itself with no human gate. Gated kwargs pause the run via
LangGraph's `interrupt()`, surfaced to the CLI as a
`{"tool", "args", "message"}` payload; the human answers "yes" (once),
"always" (rest of session, tracked by `Approvals` — except `replace_all`,
which always re-asks since each ambiguous edit is a fresh decision), or
"no". None of these three kwargs are in the model's own tool schema
(`agent/schema.py`'s `_EXCLUDED`) — the model cannot set any of them itself,
only the agent layer's approved retry can.

`agent/__init__.py` loads the two model-facing prompts —
`load_system_prompt()` (`prompts/system.md`) and
`load_subagent_system_prompt()` (`prompts/subagent_system.md`) — mirroring
the tool layer's rule that `DESCRIPTION`/the prompt file is the only
model-facing prose.

`cli/repl.py`'s `main()` assembles one `Pipeline` per session, one
`Approvals`, and `create_agent(...)` with `AnthropicPromptCachingMiddleware`
and (for models with a known context window) `SummarizationMiddleware` —
see the [README](../README.md#long-sessions) for the summarization/
scratchpad story. Responses stream token-by-token via `stream_response()`,
which consumes `agent.stream(..., stream_mode=["messages", "values"])`:
`"messages"`-mode chunks print assistant text as it's generated;
`"values"`-mode chunks carry the `"__interrupt__"` key when a friction gate
pauses the run, which `main()`'s loop resumes via `Command(resume=...)`
exactly as it did before streaming.

## The `explore` sub-agent

`agent/subagent.py` exposes a single `explore(task: str)` tool to the main
agent. `read_only_tools()` filters the registry to `ToolGroup.READ` and
`ToolGroup.SEARCH` — exactly `read`, `inspect`, `list_dir`, `glob`, `grep`.
`build_subagent_tool(model, pipeline, system_prompt)` builds one nested
`create_agent(..., name="explorer")` per session and wraps a single call to
it: give it a task description, get back a written synthesis — the
dispatching agent never sees the sub-agent's intermediate tool calls, only
its final answer.

**It shares the main agent's `Pipeline` instance** rather than building a
second one:

- `Sandbox` is an immutable root — safe to share.
- `YamlPolicy.check(path, group, tool)` is a pure function — safe to share.
- Sharing also means the sub-agent's tool calls land in the *same* session
  [trajectory](trajectory.md) file as the main agent's — full auditability,
  no separate log to lose track of.

**It can never trigger a friction gate.** `OVERWRITE`/`RECURSIVE`/
`UNIQUE_MATCH` are declared only on write/edit/move/copy/delete — none of
which `read_only_tools()` includes. This isn't just simpler, it's the
safety invariant that makes the design work: a nested agent dispatched
inside a tool call may run inside LangGraph's tool-call thread pool, where
there's no path back to the CLI's `Command(resume=...)` loop. Restricting
the sub-agent to read/search tools is what keeps that a non-issue.

**Parallel dispatch needs no extra code.** When the main model emits
several `explore` calls in one turn, LangGraph's `ToolNode` already
executes them concurrently (a thread pool for sync `.invoke()`/`.stream()`,
`asyncio.gather` for the async path) — exposing one tool the model can call
N times is sufficient. The tool's description tells the model this
explicitly, since the parallelism is otherwise invisible to it.

**Its tokens never reach the main agent's stream.** `explore()` calls
`subagent.invoke({"messages": [...]})` with no `config` argument at all, so
the nested run has no callback/stream-writer to attach to — by
construction, not by filtering, the sub-agent's own thinking is invisible
outside its final returned text.
