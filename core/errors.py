"""Model-facing failures.

Every message is shaped to tell the model what to do next — a denial
or error is a navigation aid, not a dead end.
"""


class ToolError(Exception):
    """Base failure raised by tools and pipeline stages."""


class SandboxViolation(ToolError):
    """Path resolves outside sandbox/ — where the world ends."""


class PolicyDenial(ToolError):
    """Standing rules or session scope deny the operation."""


class FrictionRequired(ToolError):
    """Destructive parameter needs confirmation; retry is an informed action.

    `kwarg` names the parameter the agent layer should force to True on a
    human-approved retry (e.g. "overwrite"), or None when there's nothing to
    force and the model must self-correct instead (e.g. a zero-match edit).
    """

    def __init__(self, message: str, kwarg: str | None = None):
        super().__init__(message)
        self.kwarg = kwarg
