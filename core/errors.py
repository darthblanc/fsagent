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
    """Destructive parameter needs confirmation; retry is an informed action."""
