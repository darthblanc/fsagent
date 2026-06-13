import pytest

from core.errors import ToolError
from core.tool_definition import PRIMITIVE, Targets, ToolGroup
from tools import ALL_TOOLS
from tools.append import DEFINITION, run


class TestDefinition:
    def test_matches_spec_table(self):
        assert DEFINITION.name == "append"
        assert DEFINITION.group is ToolGroup.MUTATE_CONTENT
        assert DEFINITION.composition == PRIMITIVE
        assert DEFINITION.policy_union == frozenset({ToolGroup.MUTATE_CONTENT})
        assert DEFINITION.targets is Targets.FILES
        assert DEFINITION.pagination is False
        assert DEFINITION.git is True
        assert DEFINITION.friction == frozenset()

    def test_registered(self):
        assert "append" in ALL_TOOLS


class TestAppend:
    def test_appends_as_new_line_and_returns_diff(self, tmp_path):
        path = tmp_path / "log.txt"
        path.write_text("one\n")
        result = run(path, content="two")
        assert path.read_text() == "one\ntwo\n"
        assert "+two" in result
        assert "-one" not in result

    def test_starts_on_a_new_line_when_file_lacks_trailing_newline(self, tmp_path):
        path = tmp_path / "log.txt"
        path.write_text("one")
        run(path, content="two")
        assert path.read_text() == "one\ntwo\n"

    def test_multiple_lines(self, tmp_path):
        path = tmp_path / "log.txt"
        path.write_text("one\n")
        result = run(path, content="two\nthree\n")
        assert path.read_text() == "one\ntwo\nthree\n"
        assert "+two" in result and "+three" in result


class TestCsvValidation:
    @pytest.fixture
    def csv_path(self, tmp_path):
        path = tmp_path / "sales.csv"
        path.write_text("date,region,revenue\n2026-01-01,na,100\n")
        return path

    def test_matching_row_appends(self, csv_path):
        result = run(csv_path, content="2026-01-02,eu,200")
        assert csv_path.read_text().endswith("2026-01-02,eu,200\n")
        assert "+2026-01-02,eu,200" in result

    def test_wrong_column_count_fails_with_expected_shape(self, csv_path):
        with pytest.raises(ToolError) as exc:
            run(csv_path, content="2026-01-02,eu")
        assert str(exc.value) == "file has 3 columns (date,region,revenue); got 2"
        assert csv_path.read_text() == "date,region,revenue\n2026-01-01,na,100\n"

    def test_any_bad_row_in_a_batch_fails_whole_append(self, csv_path):
        with pytest.raises(ToolError, match="got 4"):
            run(csv_path, content="2026-01-02,eu,200\n2026-01-03,ap,300,extra")
        assert csv_path.read_text() == "date,region,revenue\n2026-01-01,na,100\n"


class TestTierFlag:
    def test_tier_3_change_is_flagged(self, tmp_path):
        path = tmp_path / "big.txt"
        path.write_text("x" * 100 + "\n")
        result = run(path, content="more", tier_threshold=50)
        assert "tier 3 — this change is NOT reversible" in result


class TestFailureShaping:
    def test_missing_file_routes_to_write(self, tmp_path):
        with pytest.raises(ToolError, match="use write"):
            run(tmp_path / "nope.txt", content="x")

    def test_folder_target_is_shaped_failure(self, tmp_path):
        with pytest.raises(ToolError, match="folder"):
            run(tmp_path, content="x")

    def test_empty_content_is_refused(self, tmp_path):
        path = tmp_path / "log.txt"
        path.write_text("one\n")
        with pytest.raises(ToolError, match="content"):
            run(path, content="")
