"""The tool-call pipeline. Every call passes through, in order:

Sandbox → Policy → Friction → Execute → Git → Trajectory
"""

import inspect
from pathlib import Path

from core.errors import FrictionRequired, PolicyDenial, SandboxViolation, ToolError
from core.friction import StandardFriction
from core.gitstage import NoGit
from core.tiers import DEFAULT_SIZE_THRESHOLD, classify

PATH_ARGS = ("path", "src", "dest", "scope")
_DENIALS = (SandboxViolation, PolicyDenial, FrictionRequired)


class Pipeline:
    def __init__(
        self,
        sandbox,
        policy,
        trajectory,
        tools,
        friction=None,
        git=None,
        tier_threshold: int = DEFAULT_SIZE_THRESHOLD,
    ):
        self._sandbox = sandbox
        self._policy = policy
        self._friction = friction or StandardFriction()
        self._git = git or NoGit()
        self._trajectory = trajectory
        self._tools = dict(tools)
        self._tier_threshold = tier_threshold
        self._request_count = 0

    def call(self, name: str, **args) -> str:
        self._request_count += 1
        request_id = self._request_count
        stage = "lookup"
        tier = None
        try:
            tool = self._tools.get(name)
            if tool is None:
                raise ToolError(
                    f"unknown tool '{name}' — available: {', '.join(sorted(self._tools))}"
                )

            stage = "sandbox"
            resolved = dict(args)
            paths: list[Path] = []
            for key in PATH_ARGS:
                if key in resolved:
                    resolved[key] = self._sandbox.resolve(resolved[key])
                    paths.append(resolved[key])
            tier = self._classify(paths)
            extras = self._handler_extras(tool)
            # Scope-defaulting tools (glob/grep) with no path args still
            # act on the sandbox root — policy must see that path.
            policy_paths = paths or (
                [extras["sandbox_root"]] if "sandbox_root" in extras else []
            )

            stage = "policy"
            name_for_policy = tool.definition.name
            if tool.definition.policy_map:
                # Per-arg map: check exactly what each path experiences.
                for arg_name, group in tool.definition.policy_map.items():
                    target = resolved.get(arg_name)
                    if isinstance(target, Path):
                        self._check_policy(target, group, name_for_policy)
            else:
                # Cartesian fallback — fails closed (may over-deny).
                for target in policy_paths:
                    for group in sorted(tool.definition.policy_union):
                        self._check_policy(target, group, name_for_policy)
            if tool.conditional_groups:
                for group in tool.conditional_groups(resolved):
                    for target in policy_paths:
                        self._check_policy(target, group, name_for_policy)

            stage = "friction"
            self._friction.check(tool.definition, resolved)

            stage = "execute"
            result = tool.handler(**resolved, **extras)

            stage = "git"
            if tool.definition.git:
                self._git.commit(tool.definition, request_id)

            if tier is None:  # the call may have created the file
                tier = self._classify(paths)

            self._record(
                request_id, name, args,
                status="ok", stage=None, error=None,
                tier=tier, token_estimate=max(1, len(result) // 4),
            )
            return result
        except ToolError as error:
            self._record(
                request_id, name, args,
                status="denied" if isinstance(error, _DENIALS) else "error",
                stage=stage, error=str(error), tier=tier, token_estimate=None,
            )
            raise

    def _check_policy(self, target: Path, group, tool_name: str) -> None:
        decision = self._policy.check(target, group, tool=tool_name)
        if not decision.allowed:
            message = f"policy denied {group.value} on '{target}': {decision.reason}"
            if decision.alternative:
                message += f" — alternative: {decision.alternative}"
            raise PolicyDenial(message)

    def _handler_extras(self, tool) -> dict:
        # Handlers that surface pipeline state (e.g. inspect's effective
        # permissions and tier) declare these parameters by name.
        parameters = inspect.signature(tool.handler).parameters
        extras = {}
        if "policy" in parameters:
            extras["policy"] = self._policy
        if "tier_threshold" in parameters:
            extras["tier_threshold"] = self._tier_threshold
        if "sandbox_root" in parameters:
            extras["sandbox_root"] = Path(self._sandbox.root).resolve()
        return extras

    def _classify(self, paths: list[Path]):
        for path in paths:
            if path.is_file():
                return int(classify(path, self._tier_threshold))
        return None

    def _record(self, request_id: int, tool: str, args: dict, **fields) -> None:
        self._trajectory.record(request_id=request_id, tool=tool, args=args, **fields)
