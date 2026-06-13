import pytest

from core.errors import ToolError
from core.tool_definition import PRIMITIVE, Friction, Targets, ToolGroup
from tools import ALL_TOOLS
from tools.write import DEFINITION, run


class TestDefinition:
    def test_matches_spec_table(self):
        assert DEFINITION.name == "write"
        assert DEFINITION.group is ToolGroup.MUTATE_CONTENT
        assert DEFINITION.composition == PRIMITIVE
        assert DEFINITION.policy_union == frozenset({ToolGroup.MUTATE_CONTENT})
        assert DEFINITION.targets is Targets.FILES
        assert DEFINITION.pagination is False
        assert DEFINITION.git is True
        assert DEFINITION.friction == frozenset({Friction.OVERWRITE})

    def test_registered(self):
        assert "write" in ALL_TOOLS


class TestDiff:
    def test_new_file_returns_full_file_diff(self, tmp_path):
        path = tmp_path / "report.txt"
        result = run(path, content="hello\nworld\n")
        assert path.read_text() == "hello\nworld\n"
        assert "--- /dev/null" in result
        assert "+++ b/report.txt" in result
        assert "+hello" in result
        assert "+world" in result

    def test_replacement_diff_is_the_verification_loop(self, tmp_path):
        path = tmp_path / "r.txt"
        path.write_text("old line\nshared\n")
        result = run(path, content="new line\nshared\n", overwrite=True)
        assert "--- a/r.txt" in result
        assert "-old line" in result
        assert "+new line" in result

    def test_identical_content_reports_no_change(self, tmp_path):
        path = tmp_path / "r.txt"
        path.write_text("same\n")
        assert run(path, content="same\n", overwrite=True) == "(no change)"


class TestTierFlag:
    def test_tier_3_change_is_flagged_as_not_reversible(self, tmp_path):
        result = run(tmp_path / "big.txt", content="x" * 100 + "\n", tier_threshold=50)
        assert "tier 3 — this change is NOT reversible" in result


class TestGuards:
    def test_existing_file_without_overwrite_is_refused(self, tmp_path):
        path = tmp_path / "r.txt"
        path.write_text("old\n")
        with pytest.raises(ToolError, match="overwrite=true"):
            run(path, content="new\n")
        assert path.read_text() == "old\n"

    def test_folder_target_is_shaped_failure(self, tmp_path):
        with pytest.raises(ToolError, match="folder"):
            run(tmp_path, content="x")

    def test_missing_parent_suggests_create_dir(self, tmp_path):
        with pytest.raises(ToolError, match="create_dir"):
            run(tmp_path / "missing" / "r.txt", content="x")
