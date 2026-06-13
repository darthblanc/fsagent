import json

import pytest

from core.errors import ToolError
from core.tool_definition import PRIMITIVE, Targets, ToolGroup
from tools.read import DEFINITION, run


def make_file(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text)
    return path


class TestDefinition:
    def test_matches_spec_table(self):
        assert DEFINITION.name == "read"
        assert DEFINITION.group is ToolGroup.READ
        assert DEFINITION.composition == PRIMITIVE
        assert DEFINITION.policy_union == frozenset({ToolGroup.READ})
        assert DEFINITION.targets is Targets.FILES
        assert DEFINITION.pagination is True
        assert DEFINITION.git is False
        assert DEFINITION.friction == frozenset()


class TestPlainText:
    def test_numbers_lines_cat_n_style(self, tmp_path):
        path = make_file(tmp_path, "a.txt", "alpha\nbeta\n")
        assert run(path) == "     1\talpha\n     2\tbeta"

    def test_truncation_notice_is_a_continuation_instruction(self, tmp_path):
        text = "".join(f"line{i}\n" for i in range(1, 11))
        path = make_file(tmp_path, "a.txt", text)
        result = run(path, limit=3)
        assert result.startswith("     1\tline1\n")
        assert result.endswith("lines 1–3 of 10 — next: offset=4")

    def test_offset_continues_from_notice(self, tmp_path):
        text = "".join(f"line{i}\n" for i in range(1, 11))
        path = make_file(tmp_path, "a.txt", text)
        result = run(path, offset=4, limit=3)
        assert result.startswith("     4\tline4\n")
        assert result.endswith("lines 4–6 of 10 — next: offset=7")

    def test_final_page_has_no_notice(self, tmp_path):
        text = "".join(f"line{i}\n" for i in range(1, 11))
        path = make_file(tmp_path, "a.txt", text)
        result = run(path, offset=8, limit=10)
        assert "next:" not in result
        assert result.startswith("     8\tline8")

    def test_default_limit_is_500(self, tmp_path):
        text = "".join(f"L{i}\n" for i in range(1, 601))
        path = make_file(tmp_path, "a.txt", text)
        result = run(path)
        assert result.endswith("lines 1–500 of 600 — next: offset=501")

    def test_hard_token_cap_stops_early(self, tmp_path, monkeypatch):
        monkeypatch.setattr("tools.read.HARD_CHAR_CAP", 100)
        text = "".join("x" * 30 + "\n" for _ in range(10))
        path = make_file(tmp_path, "a.txt", text)
        result = run(path)
        assert result.count("\t") == 3
        assert result.endswith("lines 1–3 of 10 — next: offset=4")

    def test_empty_file(self, tmp_path):
        path = make_file(tmp_path, "a.txt", "")
        assert run(path) == "(empty file)"

    def test_offset_beyond_end_raises(self, tmp_path):
        path = make_file(tmp_path, "a.txt", "one\ntwo\n")
        with pytest.raises(ToolError, match="beyond"):
            run(path, offset=10)

    def test_offset_must_be_positive(self, tmp_path):
        path = make_file(tmp_path, "a.txt", "one\n")
        with pytest.raises(ToolError):
            run(path, offset=0)

    def test_selector_on_plain_text_is_shaped_failure(self, tmp_path):
        path = make_file(tmp_path, "a.txt", "one\n")
        with pytest.raises(ToolError, match="selector"):
            run(path, selector="anything")


class TestFailureShaping:
    def test_not_found_suggests_similar_paths(self, tmp_path):
        make_file(tmp_path, "sales_2024.csv", "a,b\n")
        with pytest.raises(ToolError) as exc:
            run(tmp_path / "sales2024.csv")
        assert "not found — similar paths:" in str(exc.value)
        assert "sales_2024.csv" in str(exc.value)

    def test_not_found_without_candidates(self, tmp_path):
        with pytest.raises(ToolError, match="not found"):
            run(tmp_path / "zzz.txt")

    def test_folder_target_is_shaped_failure(self, tmp_path):
        with pytest.raises(ToolError, match="folder"):
            run(tmp_path)


JSON_DATA = {
    "config": {"database": {"host": "db.local"}},
    "x": [
        {"y": 1, "name": "a", "id": 7},
        {"y": 2, "name": "b", "id": 8},
        {"y": 3, "name": "c", "id": 9},
    ],
}


class TestJsonSelector:
    @pytest.fixture
    def path(self, tmp_path):
        return make_file(tmp_path, "data.json", json.dumps(JSON_DATA))

    def test_dotted_path_selects_value(self, path):
        assert run(path, selector="config.database.host") == '     1\t"db.local"'

    def test_object_renders_pretty_printed(self, path):
        result = run(path, selector="config.database")
        assert '"host": "db.local"' in result
        assert len(result.splitlines()) == 3

    def test_array_traversed_as_object(self, path):
        with pytest.raises(ToolError) as exc:
            run(path, selector="x.y")
        assert str(exc.value) == "x is an array[3], not an object — index it: x.0.y"

    def test_index_out_of_range(self, path):
        with pytest.raises(ToolError) as exc:
            run(path, selector="x.5.y")
        assert str(exc.value) == "index 5 out of range — x has 3 elements (0–2)"

    def test_missing_key_lists_available(self, path):
        with pytest.raises(ToolError) as exc:
            run(path, selector="x.0.z")
        assert str(exc.value) == "no key 'z' at x.0 — available keys: y, name, id"

    def test_missing_root_key(self, path):
        with pytest.raises(ToolError) as exc:
            run(path, selector="nope")
        assert "no key 'nope' at root" in str(exc.value)
        assert "config" in str(exc.value)


CSV_TEXT = "name,team,score\nann,red,10\nbob,blue,20\ncy,red,30\n"


class TestCsvSelector:
    @pytest.fixture
    def path(self, tmp_path):
        return make_file(tmp_path, "data.csv", CSV_TEXT)

    def test_column_selection(self, path):
        result = run(path, selector={"columns": ["name", "score"]})
        lines = [line.split("\t")[1] for line in result.splitlines()]
        assert lines == ["name,score", "ann,10", "bob,20", "cy,30"]

    def test_rows_head(self, path):
        result = run(path, selector={"rows": "head:2"})
        lines = [line.split("\t")[1] for line in result.splitlines()]
        assert lines == ["name,team,score", "ann,red,10", "bob,blue,20"]

    def test_rows_tail(self, path):
        result = run(path, selector={"rows": "tail:1"})
        lines = [line.split("\t")[1] for line in result.splitlines()]
        assert lines == ["name,team,score", "cy,red,30"]

    def test_rows_range_is_one_indexed_inclusive(self, path):
        result = run(path, selector={"rows": "2:3"})
        lines = [line.split("\t")[1] for line in result.splitlines()]
        assert lines == ["name,team,score", "bob,blue,20", "cy,red,30"]

    def test_unknown_column_lists_available(self, path):
        with pytest.raises(ToolError) as exc:
            run(path, selector={"columns": ["scores"]})
        assert str(exc.value) == "no column 'scores' — available columns: name, team, score"

    def test_invalid_rows_spec(self, path):
        with pytest.raises(ToolError, match="rows"):
            run(path, selector={"rows": "mid:5"})

    def test_selector_must_be_object(self, path):
        with pytest.raises(ToolError, match="object"):
            run(path, selector="name")


MD_TEXT = "# Title\nintro\n## Setup\nstep one\nstep two\n## Usage\nrun it\n"


class TestMarkdownSelector:
    @pytest.fixture
    def path(self, tmp_path):
        return make_file(tmp_path, "doc.md", MD_TEXT)

    def test_section_keeps_original_line_numbers(self, path):
        result = run(path, selector="Setup")
        assert result == "     3\t## Setup\n     4\tstep one\n     5\tstep two"

    def test_unknown_heading_lists_available(self, path):
        with pytest.raises(ToolError) as exc:
            run(path, selector="Install")
        message = str(exc.value)
        assert "no heading 'Install'" in message
        assert "Title" in message and "Setup" in message and "Usage" in message
