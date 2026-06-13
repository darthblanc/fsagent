"""Stage 2 — Policy: check(path, group, tool) against standing YAML rules.

Rule patterns are sandbox-relative, spelled with the canonical
"sandbox/" prefix; a pattern ending in "/**" also protects the base
folder itself. Entries in allow/deny lists name groups OR tools (deny
[delete, move] guards a file the agent maintains but must not destroy);
an allow list is a whitelist for its path. Deny wins at equal
specificity; a more specific path beats a general one; `default`
decides when no rule has an opinion. Denials return a reason and an
alternative (rule-supplied, or generated). Intersection with session
--scope arrives with cli/.
"""

import fnmatch
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Union

import yaml

from core.tool_definition import ToolGroup

_MUTATING = {ToolGroup.MUTATE_CONTENT.value, ToolGroup.MUTATE_STRUCTURE.value}


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str | None = None
    alternative: str | None = None


class Policy(Protocol):
    def check(self, path: Path, group: ToolGroup, tool: str | None = None) -> PolicyDecision: ...


class AllowAllPolicy:
    def check(self, path: Path, group: ToolGroup, tool: str | None = None) -> PolicyDecision:
        return PolicyDecision(allowed=True)


@dataclass(frozen=True)
class _Rule:
    pattern: str
    deny: frozenset
    allow: frozenset
    reason: Union[str, None]
    alternative: Union[str, None]

    @property
    def specificity(self) -> int:
        return len(re.sub(r"[*?\[\]]", "", self.pattern))

    def matches(self, candidate: str) -> bool:
        if fnmatch.fnmatchcase(candidate, self.pattern):
            return True
        # "zone/**" also protects the zone folder itself
        return self.pattern.endswith("/**") and candidate == self.pattern[:-3]

    def judge(self, names: set) -> Union[str, None]:
        if self.deny & names:
            return "deny"
        if self.allow:
            return "allow" if self.allow & names else "deny"
        return None  # deny-list rule with no opinion on these names


class YamlPolicy:
    def __init__(self, config: Union[str, dict], sandbox_root):
        data = yaml.safe_load(config) if isinstance(config, str) else config
        if not isinstance(data, dict):
            raise ValueError("policy must be a YAML mapping")
        self.default = data.get("default", "allow")
        if self.default not in ("allow", "deny"):
            raise ValueError(f"default must be 'allow' or 'deny', got {self.default!r}")
        self.root = Path(sandbox_root).resolve()
        self.rules = [
            self._parse_rule(raw, index)
            for index, raw in enumerate(data.get("rules") or [])
        ]

    @classmethod
    def from_file(cls, path, sandbox_root) -> "YamlPolicy":
        return cls(Path(path).read_text(), sandbox_root)

    @staticmethod
    def _parse_rule(raw, index: int) -> _Rule:
        if not isinstance(raw, dict) or "path" not in raw:
            raise ValueError(f"rule {index}: must be a mapping with a 'path'")
        deny = raw.get("deny", [])
        allow = raw.get("allow", [])
        if not isinstance(deny, list) or not isinstance(allow, list):
            raise ValueError(f"rule {index}: 'allow' and 'deny' must be lists")
        if not deny and not allow:
            raise ValueError(f"rule {index}: needs an allow or deny list")
        return _Rule(
            pattern=str(raw["path"]),
            deny=frozenset(str(entry) for entry in deny),
            allow=frozenset(str(entry) for entry in allow),
            reason=raw.get("reason"),
            alternative=raw.get("alternative"),
        )

    def check(self, path: Path, group: ToolGroup, tool: str | None = None) -> PolicyDecision:
        candidate = self._candidate(Path(path))
        names = {group.value if isinstance(group, ToolGroup) else str(group)}
        if tool:
            names.add(str(tool))
        opinions = [
            (rule.specificity, verdict, rule)
            for rule in self.rules
            if rule.matches(candidate) and (verdict := rule.judge(names))
        ]
        if opinions:
            top = max(specificity for specificity, _, _ in opinions)
            denials = [rule for s, verdict, rule in opinions if s == top and verdict == "deny"]
            if denials:
                rule = denials[0]
                return PolicyDecision(
                    allowed=False,
                    reason=self._reason(rule, names),
                    alternative=self._alternative(rule),
                )
            return PolicyDecision(allowed=True)
        if self.default == "deny":
            return PolicyDecision(
                allowed=False, reason="default policy is deny — no rule allows this"
            )
        return PolicyDecision(allowed=True)

    def _candidate(self, path: Path) -> str:
        try:
            relative = path.resolve().relative_to(self.root)
        except ValueError:
            return path.as_posix()
        if not relative.parts:
            return "sandbox"
        return (Path("sandbox") / relative).as_posix()

    @staticmethod
    def _reason(rule: _Rule, names: set) -> str:
        if rule.reason:
            return rule.reason
        hits = sorted(rule.deny & names)
        if hits:
            return f"rule '{rule.pattern}' denies {', '.join(hits)}"
        return f"rule '{rule.pattern}' allows only {', '.join(sorted(rule.allow))}"

    @staticmethod
    def _alternative(rule: _Rule) -> Union[str, None]:
        if rule.alternative:
            return rule.alternative
        if rule.deny & _MUTATING and "read" not in rule.deny:
            return "read is still allowed — copy it out and work on the copy"
        return None
