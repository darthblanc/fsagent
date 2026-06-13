import pytest

from core.errors import ToolError
from core.tool_definition import PRIMITIVE, Targets, ToolGroup
from tools import ALL_TOOLS
from tools.create_dir import DEFINITION, run


class TestDefinition:
    def test_matches_spec_table(self):
        assert DEFINITION.name == "create_dir"
        assert DEFINITION.group is ToolGroup.MUTATE_STRUCTURE
        assert DEFINITION.composition == PRIMITIVE
        assert DEFINITION.policy_union == frozenset({ToolGroup.MUTATE_STRUCTURE})
        assert DEFINITION.targets is Targets.FOLDERS
        assert DEFINITION.pagination is False
        assert DEFINITION.git is True
        assert DEFINITION.friction == frozenset()

    def test_registered(self):
        assert "create_dir" in ALL_TOOLS


class TestCreate:
    def test_creates_folder_with_gitkeep(self, tmp_path):
        path = tmp_path / "raw"
        result = run(path)
        assert result == f"created '{path}'"
        assert path.is_dir()
        assert (path / ".gitkeep").is_file()

    def test_parents_created_as_needed(self, tmp_path):
        path = tmp_path / "a" / "b" / "c"
        result = run(path)
        assert result == f"created '{path}' (including 2 parent folders)"
        assert path.is_dir()
        assert (path / ".gitkeep").is_file()
        assert not (tmp_path / "a" / ".gitkeep").exists()

    def test_already_exists_is_informative_not_fatal(self, tmp_path):
        path = tmp_path / "raw"
        run(path)
        (path / "data.txt").write_text("x\n")
        result = run(path)
        assert result == f"'{path}' already exists"
        assert (path / "data.txt").is_file()

    def test_existing_file_is_shaped_failure(self, tmp_path):
        path = tmp_path / "raw"
        path.write_text("x\n")
        with pytest.raises(ToolError, match="is a file"):
            run(path)
