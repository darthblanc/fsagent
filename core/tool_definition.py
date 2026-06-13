"""Declaration schema for fsagent tools.

Every tool in tools/ is an instance of ToolDefinition. The declaration
captures what a tool may touch (targets), what permission classes its
execution exercises (policy_union), which destructive parameters require
confirmation (friction), and whether it is a primitive or a composition
of functions from functions/.
"""

import warnings
from enum import Enum
from typing import Literal, Union

from pydantic import BaseModel, field_validator, model_validator


class ComposedPolicyWarning(UserWarning):
    """A composed tool was declared without a per-arg policy map."""


class ToolGroup(str, Enum):
    READ = "read"
    SEARCH = "search"
    MUTATE_CONTENT = "mutate-content"
    MUTATE_STRUCTURE = "mutate-structure"
    TRANSFORM = "transform"  # reserved


class Friction(str, Enum):
    """Destructive parameters whose use requires confirmation."""

    RECURSIVE = "recursive"
    OVERWRITE = "overwrite"
    UNIQUE_MATCH = "unique-match"


class Targets(str, Enum):
    FILES = "files"
    FOLDERS = "folders"
    BOTH = "both"


PRIMITIVE = "primitive"


def _validate_snake_case(value: str, what: str) -> str:
    if not value.isidentifier() or value != value.lower():
        raise ValueError(f"{what} must be a snake_case identifier, got {value!r}")
    return value


class ToolDefinition(BaseModel, frozen=True):
    name: str
    group: ToolGroup
    friction: frozenset[Friction] = frozenset()
    composition: Union[Literal["primitive"], tuple[str, ...]]
    policy_union: frozenset[ToolGroup]
    policy_map: Union[dict[str, ToolGroup], None] = None
    targets: Targets
    pagination: bool
    git: bool

    @field_validator("name")
    @classmethod
    def _name_is_snake_case(cls, value: str) -> str:
        return _validate_snake_case(value, "name")

    @field_validator("group")
    @classmethod
    def _group_is_not_reserved(cls, value: ToolGroup) -> ToolGroup:
        if value is ToolGroup.TRANSFORM:
            raise ValueError("group 'transform' is reserved and cannot be declared")
        return value

    @field_validator("policy_union")
    @classmethod
    def _policy_union_is_valid(
        cls, value: frozenset[ToolGroup]
    ) -> frozenset[ToolGroup]:
        if not value:
            raise ValueError("policy_union must not be empty")
        if ToolGroup.TRANSFORM in value:
            raise ValueError("policy_union cannot contain the reserved 'transform' group")
        return value

    @field_validator("composition")
    @classmethod
    def _composition_is_valid(cls, value):
        if value == PRIMITIVE:
            return value
        if not value:
            raise ValueError("composition must list at least one function")
        for function_name in value:
            _validate_snake_case(function_name, "composed function name")
        if len(set(value)) != len(value):
            raise ValueError("composition must not contain duplicate function names")
        return value

    @model_validator(mode="after")
    def _policy_union_is_consistent_with_group(self) -> "ToolDefinition":
        if self.composition == PRIMITIVE:
            if self.policy_map is not None:
                raise ValueError(
                    "policy_map is only for composed tools — a primitive is "
                    "exactly its own policy"
                )
            if self.policy_union != {self.group}:
                raise ValueError(
                    "a primitive tool's policy_union must equal its own group"
                )
        else:
            if self.group not in self.policy_union:
                raise ValueError("a composed tool's policy_union must contain its group")
            if self.policy_map is None:
                warnings.warn(
                    f"composed tool '{self.name}' has no per-arg policy map — the "
                    "pipeline falls back to the cartesian check (every path × every "
                    "group in policy_union), which fails closed: it can over-deny "
                    "(e.g. demanding mutate rights on a path the tool only reads) "
                    "but never under-deny. Declare policy_map={arg: group} to check "
                    "exactly what each path experiences.",
                    ComposedPolicyWarning,
                    stacklevel=2,
                )
            elif set(self.policy_map.values()) != self.policy_union:
                raise ValueError(
                    "policy_map groups must union to exactly policy_union"
                )
        return self
