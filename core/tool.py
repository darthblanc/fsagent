"""A tool: its declaration, model-facing description, and handler.

The handler receives sandbox-resolved Paths and implements only the
execute stage; everything else is the pipeline's job.
"""

from dataclasses import dataclass
from typing import Callable, Optional

from core.tool_definition import ToolDefinition


@dataclass(frozen=True)
class Tool:
    definition: ToolDefinition
    description: str
    handler: Callable[..., str]
    # Args-dependent policy requirements beyond policy_union, e.g. grep's
    # content mode additionally requiring read. Returns groups to check
    # against the call's effective paths.
    conditional_groups: Optional[Callable[[dict], tuple]] = None
