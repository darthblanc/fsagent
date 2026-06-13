import pytest

from core.errors import FrictionRequired, ToolError
from core.tool_definition import PRIMITIVE, Friction, Targets, ToolGroup
from tools import ALL_TOOLS
from tools.edit import DEFINITION, run


class TestDefinition:
    def test_matches_spec_table(self):
        assert DEFINITION.name == "edit"
        assert DEFINITION.group is ToolGroup.MUTATE_CONTENT
        assert DEFINITION.composition == PRIMITIVE
        assert DEFINITION.policy_union == frozenset({ToolGroup.MUTATE_CONTENT})
        assert DEFINITION.targets is Targets.FILES
        assert DEFINITION.pagination is False
        assert DEFINITION.git is True
        assert DEFINITION.friction == frozenset({Friction.UNIQUE_MATCH})

    def test_registered(self):
        assert "edit" in ALL_TOOLS


class TestReplacement:
    def test_unique_match_returns_diff(self, tmp_path):
        path = tmp_path / "r.txt"
        path.write_text("alpha\nbeta\ngamma\n")
        result = run(path, old_str="beta", new_str="BETA")
        assert path.read_text() == "alpha\nBETA\ngamma\n"
        assert "--- a/r.txt" in result
        assert "-beta" in result
        assert "+BETA" in result

    def test_empty_new_str_deletes_the_text(self, tmp_path):
        path = tmp_path / "r.txt"
        path.write_text("keep DELETEME this\n")
        run(path, old_str="DELETEME ", new_str="")
        assert path.read_text() == "keep this\n"

    def test_multiline_old_str(self, tmp_path):
        path = tmp_path / "r.txt"
        path.write_text("one\ntwo\nthree\nfour\n")
        run(path, old_str="two\nthree", new_str="2\n3")
        assert path.read_text() == "one\n2\n3\nfour\n"

    def test_tier_3_change_is_flagged(self, tmp_path):
        path = tmp_path / "big.txt"
        path.write_text("target\n" + "x" * 100 + "\n")
        result = run(path, old_str="target", new_str="hit", tier_threshold=50)
        assert "tier 3 — this change is NOT reversible" in result


class TestFailureShaping:
    def test_zero_matches_points_at_nearest_occurrence(self, tmp_path):
        path = tmp_path / "r.txt"
        path.write_text("intro\nrevenue_2024 = 100\noutro\n")
        with pytest.raises(FrictionRequired) as exc:
            run(path, old_str="revenue_2025 = 100", new_str="x")
        assert str(exc.value) == (
            "no exact match — nearest occurrence at line 2: "
            "'revenue_2024 = 100' — re-read and retry with the current text"
        )
        assert path.read_text() == "intro\nrevenue_2024 = 100\noutro\n"

    def test_zero_matches_with_nothing_similar(self, tmp_path):
        path = tmp_path / "r.txt"
        path.write_text("aaa\n")
        with pytest.raises(FrictionRequired) as exc:
            run(path, old_str="zzzzqqqq", new_str="x")
        assert str(exc.value) == (
            "no exact match — re-read the file and retry with the current text"
        )

    def test_multiple_matches_list_lines_and_ask_for_context(self, tmp_path):
        path = tmp_path / "r.txt"
        path.write_text("foo\nbar\nfoo\nbaz\nfoo\n")
        with pytest.raises(FrictionRequired) as exc:
            run(path, old_str="foo", new_str="x")
        assert str(exc.value) == (
            "matched 3 locations (lines 1, 3, 5) — "
            "include more surrounding context to disambiguate"
        )
        assert path.read_text() == "foo\nbar\nfoo\nbaz\nfoo\n"

    def test_empty_old_str_is_refused(self, tmp_path):
        path = tmp_path / "r.txt"
        path.write_text("x\n")
        with pytest.raises(ToolError, match="old_str"):
            run(path, old_str="", new_str="y")

    def test_identical_strings_are_refused(self, tmp_path):
        path = tmp_path / "r.txt"
        path.write_text("x\n")
        with pytest.raises(ToolError, match="identical"):
            run(path, old_str="x", new_str="x")

    def test_missing_file_suggests_similar(self, tmp_path):
        (tmp_path / "report.txt").write_text("x\n")
        with pytest.raises(ToolError, match="not found"):
            run(tmp_path / "reprot.txt", old_str="x", new_str="y")

    def test_folder_target_is_shaped_failure(self, tmp_path):
        with pytest.raises(ToolError, match="folder"):
            run(tmp_path, old_str="x", new_str="y")
