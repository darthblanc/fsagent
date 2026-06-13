from pathlib import Path

import pytest

from core.policy import YamlPolicy
from core.tool_definition import ToolGroup

ROOT = Path("/sb")

SPEC = """
default: allow                     # within the sandbox
rules:
  - path: "sandbox/originals/**"
    deny: [mutate-content, mutate-structure]   # read-only archive
  - path: "sandbox/.index.json"
    deny: [delete, move]                        # agent maintains it, can't destroy it
  - path: "sandbox/inbox/**"
    allow: [read, search, move]                 # may file things away, not edit them
"""


@pytest.fixture
def policy():
    return YamlPolicy(SPEC, ROOT)


class TestDefaults:
    def test_default_allow_outside_all_rules(self, policy):
        decision = policy.check(ROOT / "notes.txt", ToolGroup.MUTATE_CONTENT, tool="write")
        assert decision.allowed

    def test_default_deny(self):
        engine = YamlPolicy("default: deny\nrules: []", ROOT)
        decision = engine.check(ROOT / "a.txt", ToolGroup.READ, tool="read")
        assert not decision.allowed
        assert "default" in decision.reason


class TestReadOnlyArchive:
    def test_mutation_denied_with_reason(self, policy):
        decision = policy.check(
            ROOT / "originals" / "a.csv", ToolGroup.MUTATE_CONTENT, tool="write"
        )
        assert not decision.allowed
        assert "sandbox/originals/**" in decision.reason
        assert "mutate-content" in decision.reason

    def test_denial_suggests_the_copy_out_recovery(self, policy):
        decision = policy.check(
            ROOT / "originals" / "a.csv", ToolGroup.MUTATE_CONTENT, tool="edit"
        )
        assert "copy" in decision.alternative

    def test_read_and_search_still_allowed(self, policy):
        target = ROOT / "originals" / "a.csv"
        assert policy.check(target, ToolGroup.READ, tool="read").allowed
        assert policy.check(target, ToolGroup.SEARCH, tool="grep").allowed

    def test_the_archive_folder_itself_is_protected(self, policy):
        decision = policy.check(
            ROOT / "originals", ToolGroup.MUTATE_STRUCTURE, tool="delete"
        )
        assert not decision.allowed


class TestToolLevelRules:
    def test_delete_and_move_denied_by_tool_name(self, policy):
        target = ROOT / ".index.json"
        assert not policy.check(target, ToolGroup.MUTATE_STRUCTURE, tool="delete").allowed
        assert not policy.check(target, ToolGroup.MUTATE_STRUCTURE, tool="move").allowed

    def test_maintenance_still_allowed(self, policy):
        target = ROOT / ".index.json"
        assert policy.check(target, ToolGroup.MUTATE_CONTENT, tool="edit").allowed
        assert policy.check(target, ToolGroup.MUTATE_CONTENT, tool="write").allowed
        assert policy.check(target, ToolGroup.READ, tool="read").allowed


class TestWhitelist:
    def test_listed_groups_allowed(self, policy):
        target = ROOT / "inbox" / "memo.txt"
        assert policy.check(target, ToolGroup.READ, tool="read").allowed
        assert policy.check(target, ToolGroup.SEARCH, tool="grep").allowed

    def test_listed_tool_allowed_despite_unlisted_group(self, policy):
        decision = policy.check(
            ROOT / "inbox" / "memo.txt", ToolGroup.MUTATE_STRUCTURE, tool="move"
        )
        assert decision.allowed

    def test_everything_else_denied_with_the_whitelist_as_reason(self, policy):
        decision = policy.check(
            ROOT / "inbox" / "memo.txt", ToolGroup.MUTATE_CONTENT, tool="edit"
        )
        assert not decision.allowed
        assert "allows only" in decision.reason
        assert "read, search" in decision.reason

    def test_delete_in_inbox_denied(self, policy):
        decision = policy.check(
            ROOT / "inbox" / "memo.txt", ToolGroup.MUTATE_STRUCTURE, tool="delete"
        )
        assert not decision.allowed


class TestPrecedence:
    def test_specific_path_beats_general(self):
        engine = YamlPolicy(
            """
default: allow
rules:
  - path: "sandbox/**"
    deny: [mutate-content]
  - path: "sandbox/drafts/**"
    allow: [read, search, mutate-content]
""",
            ROOT,
        )
        assert engine.check(ROOT / "drafts" / "d.txt", ToolGroup.MUTATE_CONTENT, tool="write").allowed
        assert not engine.check(ROOT / "other.txt", ToolGroup.MUTATE_CONTENT, tool="write").allowed

    def test_deny_wins_at_equal_specificity(self):
        engine = YamlPolicy(
            """
default: allow
rules:
  - path: "sandbox/data/**"
    allow: [read]
  - path: "sandbox/data/**"
    deny: [read]
""",
            ROOT,
        )
        assert not engine.check(ROOT / "data" / "a.txt", ToolGroup.READ, tool="read").allowed


class TestCustomShaping:
    def test_rule_reason_and_alternative_surface(self):
        engine = YamlPolicy(
            """
default: allow
rules:
  - path: "sandbox/reports/**"
    deny: [mutate-content]
    reason: "reports are finalized each quarter"
    alternative: "copy it into drafts/ first"
""",
            ROOT,
        )
        decision = engine.check(ROOT / "reports" / "q1.csv", ToolGroup.MUTATE_CONTENT, tool="edit")
        assert decision.reason == "reports are finalized each quarter"
        assert decision.alternative == "copy it into drafts/ first"


class TestValidation:
    def test_bad_default_rejected(self):
        with pytest.raises(ValueError, match="default"):
            YamlPolicy("default: maybe\nrules: []", ROOT)

    def test_rule_without_path_rejected(self):
        with pytest.raises(ValueError, match="path"):
            YamlPolicy("default: allow\nrules:\n  - deny: [read]", ROOT)

    def test_rule_without_lists_rejected(self):
        with pytest.raises(ValueError, match="allow or deny"):
            YamlPolicy('default: allow\nrules:\n  - path: "sandbox/x"', ROOT)


class TestFromFile:
    def test_loads_policy_file(self, tmp_path):
        config = tmp_path / "policy.yaml"
        config.write_text(SPEC)
        engine = YamlPolicy.from_file(config, ROOT)
        assert not engine.check(
            ROOT / "originals" / "a.csv", ToolGroup.MUTATE_CONTENT, tool="write"
        ).allowed
