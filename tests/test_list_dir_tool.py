import pytest

from core.errors import ToolError
from core.tool_definition import PRIMITIVE, Targets, ToolGroup
from tools.list_dir import DEFINITION, run


@pytest.fixture
def root(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"x" * 5)
    (tmp_path / "b.csv").write_bytes(b"x" * 10)
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.csv").write_bytes(b"x" * 20)
    deep = sub / "deep"
    deep.mkdir()
    (deep / "d.txt").write_bytes(b"x" * 30)
    return tmp_path


class TestDefinition:
    def test_matches_spec_table(self):
        assert DEFINITION.name == "list_dir"
        assert DEFINITION.group is ToolGroup.READ
        assert DEFINITION.composition == PRIMITIVE
        assert DEFINITION.policy_union == frozenset({ToolGroup.READ})
        assert DEFINITION.targets is Targets.FOLDERS
        assert DEFINITION.pagination is True
        assert DEFINITION.git is False
        assert DEFINITION.friction == frozenset()


class TestFlatListing:
    def test_name_type_size_lines(self, root):
        assert run(root) == (
            "a.txt · file · 5\n"
            "b.csv · file · 10\n"
            "sub · folder · -"
        )

    def test_gitkeep_is_filtered_from_display(self, tmp_path):
        (tmp_path / ".gitkeep").write_bytes(b"")
        (tmp_path / "a.txt").write_bytes(b"x")
        assert run(tmp_path) == "a.txt · file · 1"

    def test_empty_folder(self, tmp_path):
        assert run(tmp_path) == "(empty folder)"

    def test_trash_is_filtered_from_display(self, tmp_path):
        trash = tmp_path / "_trash"
        trash.mkdir()
        (trash / "old.txt").write_text("x\n")
        (tmp_path / "a.txt").write_text("x\n")
        assert run(tmp_path, depth=3) == "a.txt · file · 2"


class TestPagination:
    @pytest.fixture
    def many(self, tmp_path):
        for i in range(5):
            (tmp_path / f"f{i}.txt").write_bytes(b"x")
        return tmp_path

    def test_truncation_notice_with_resumption_offset(self, many):
        result = run(many, limit=2)
        assert result.startswith("f0.txt · file · 1\n")
        assert result.endswith("entries 1–2 of 5 — next: offset=2")

    def test_offset_resumes(self, many):
        result = run(many, offset=2, limit=2)
        assert result.startswith("f2.txt · file · 1\n")
        assert result.endswith("entries 3–4 of 5 — next: offset=4")

    def test_final_page_has_no_notice(self, many):
        result = run(many, offset=4, limit=2)
        assert result == "f4.txt · file · 1"

    def test_offset_beyond_end_raises(self, many):
        with pytest.raises(ToolError, match="beyond"):
            run(many, offset=10)

    def test_negative_offset_raises(self, many):
        with pytest.raises(ToolError):
            run(many, offset=-1)


class TestDepth:
    def test_depth_2_is_indented_tree(self, root):
        assert run(root, depth=2) == (
            "a.txt · file · 5\n"
            "b.csv · file · 10\n"
            "sub · folder · -\n"
            "  c.csv · file · 20\n"
            "  deep · folder · -"
        )

    def test_depth_3_reaches_deepest_level(self, root):
        result = run(root, depth=3)
        assert "    d.txt · file · 30" in result

    def test_depth_above_max_raises(self, root):
        with pytest.raises(ToolError, match="3"):
            run(root, depth=4)

    def test_depth_below_one_raises(self, root):
        with pytest.raises(ToolError):
            run(root, depth=0)

    def test_tree_lines_paginate(self, root):
        result = run(root, depth=2, limit=4)
        assert result.endswith("entries 1–4 of 5 — next: offset=4")


class TestFailureShaping:
    def test_file_target_is_shaped_failure(self, root):
        with pytest.raises(ToolError, match="folder"):
            run(root / "a.txt")

    def test_not_found_suggests_similar_paths(self, root):
        with pytest.raises(ToolError) as exc:
            run(root / "subb")
        assert "not found — similar paths:" in str(exc.value)
        assert "sub" in str(exc.value)
