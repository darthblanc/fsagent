import pytest

from core.errors import ToolError
from core.tool_definition import PRIMITIVE, Targets, ToolGroup
from tools.glob import DEFINITION, run


@pytest.fixture
def root(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "sales_2024.csv").write_text("a,b\n")
    (data / "sales_2025.csv").write_text("a,b\n")
    (tmp_path / "notes.txt").write_text("x\n")
    return tmp_path


class TestDefinition:
    def test_matches_spec_table(self):
        assert DEFINITION.name == "glob"
        assert DEFINITION.group is ToolGroup.SEARCH
        assert DEFINITION.composition == PRIMITIVE
        assert DEFINITION.policy_union == frozenset({ToolGroup.SEARCH})
        assert DEFINITION.targets is Targets.BOTH
        assert DEFINITION.pagination is True
        assert DEFINITION.git is False
        assert DEFINITION.friction == frozenset()


class TestMatching:
    def test_paths_only_sorted_relative_to_scope(self, root):
        assert run("**/*.csv", scope=root) == (
            "data/sales_2024.csv\ndata/sales_2025.csv"
        )

    def test_matches_folders_too(self, root):
        assert run("d*", scope=root) == "data"

    def test_no_matches_is_informative_not_an_error(self, root):
        assert run("*.rs", scope=root) == "no matches for '*.rs'"

    def test_scope_falls_back_to_sandbox_root(self, root):
        assert run("*.txt", sandbox_root=root) == "notes.txt"

    def test_no_scope_at_all_raises(self):
        with pytest.raises(ToolError, match="scope"):
            run("*.txt")

    def test_trash_subtree_is_invisible(self, tmp_path):
        trash = tmp_path / "_trash"
        trash.mkdir()
        (trash / "old.csv").write_text("x\n")
        (tmp_path / "new.csv").write_text("x\n")
        assert run("**/*.csv", scope=tmp_path) == "new.csv"
        assert run("_t*", scope=tmp_path) == "no matches for '_t*'"


class TestPagination:
    @pytest.fixture
    def many(self, tmp_path):
        for i in range(5):
            (tmp_path / f"f{i}.txt").write_text("x")
        return tmp_path

    def test_truncation_notice_suggests_narrowing_or_offset(self, many):
        result = run("*.txt", scope=many, limit=2)
        assert result.startswith("f0.txt\nf1.txt\n")
        assert result.endswith(
            "5 matches, showing 1–2 — narrow the pattern or continue with offset=3"
        )

    def test_offset_resumes(self, many):
        result = run("*.txt", scope=many, offset=3, limit=2)
        assert result.startswith("f2.txt\nf3.txt\n")
        assert result.endswith(
            "5 matches, showing 3–4 — narrow the pattern or continue with offset=5"
        )

    def test_final_page_has_no_notice(self, many):
        assert run("*.txt", scope=many, offset=5, limit=2) == "f4.txt"

    def test_offset_beyond_end_raises(self, many):
        with pytest.raises(ToolError, match="beyond"):
            run("*.txt", scope=many, offset=10)

    def test_offset_must_be_positive(self, many):
        with pytest.raises(ToolError):
            run("*.txt", scope=many, offset=0)


class TestFailureShaping:
    def test_absolute_pattern_is_shaped_failure(self, root):
        with pytest.raises(ToolError, match="pattern"):
            run("/etc/*", scope=root)

    def test_missing_scope_folder(self, root):
        with pytest.raises(ToolError, match="not found"):
            run("*", scope=root / "missing")

    def test_file_scope_is_shaped_failure(self, root):
        with pytest.raises(ToolError, match="folder"):
            run("*", scope=root / "notes.txt")
