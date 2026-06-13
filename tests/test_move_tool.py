import pytest

from core.errors import ToolError
from core.tool_definition import PRIMITIVE, Friction, Targets, ToolGroup
from tools import ALL_TOOLS
from tools.move import DEFINITION, run


class TestDefinition:
    def test_matches_spec_table(self):
        assert DEFINITION.name == "move"
        assert DEFINITION.group is ToolGroup.MUTATE_STRUCTURE
        assert DEFINITION.composition == PRIMITIVE
        assert DEFINITION.policy_union == frozenset({ToolGroup.MUTATE_STRUCTURE})
        assert DEFINITION.targets is Targets.BOTH
        assert DEFINITION.pagination is False
        assert DEFINITION.git is True
        assert DEFINITION.friction == frozenset({Friction.OVERWRITE})

    def test_registered(self):
        assert "move" in ALL_TOOLS


class TestMove:
    def test_moves_file_and_confirms_old_to_new(self, tmp_path):
        src = tmp_path / "a.txt"
        src.write_text("data\n")
        dest = tmp_path / "b.txt"
        result = run(src, dest)
        assert result == f"moved '{src}' → '{dest}'"
        assert not src.exists()
        assert dest.read_text() == "data\n"

    def test_rename_is_moving_within_the_same_directory(self, tmp_path):
        src = tmp_path / "draft.txt"
        src.write_text("x\n")
        run(src, tmp_path / "final.txt")
        assert (tmp_path / "final.txt").is_file()

    def test_moves_folder_with_contents(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "a.txt").write_text("x\n")
        dest = tmp_path / "dest"
        result = run(src, dest)
        assert result == f"moved '{src}' → '{dest}'"
        assert (dest / "a.txt").read_text() == "x\n"
        assert not src.exists()

    def test_overwrite_replaces_existing_file(self, tmp_path):
        src = tmp_path / "a.txt"
        src.write_text("new\n")
        dest = tmp_path / "b.txt"
        dest.write_text("old\n")
        run(src, dest, overwrite=True)
        assert dest.read_text() == "new\n"

    def test_tier_3_move_is_flagged(self, tmp_path):
        src = tmp_path / "big.txt"
        src.write_text("x" * 100 + "\n")
        result = run(src, tmp_path / "moved.txt", tier_threshold=50)
        assert "tier 3 — this change is NOT reversible" in result


class TestFailureShaping:
    def test_collision_without_overwrite(self, tmp_path):
        src = tmp_path / "a.txt"
        src.write_text("new\n")
        dest = tmp_path / "b.txt"
        dest.write_text("old\n")
        with pytest.raises(ToolError, match="pass overwrite=true"):
            run(src, dest)
        assert dest.read_text() == "old\n"
        assert src.exists()

    def test_existing_folder_dest_suggests_full_path(self, tmp_path):
        src = tmp_path / "a.txt"
        src.write_text("x\n")
        folder = tmp_path / "archive"
        folder.mkdir()
        with pytest.raises(ToolError) as exc:
            run(src, folder)
        message = str(exc.value)
        assert "existing folder" in message
        assert str(folder / "a.txt") in message

    def test_folder_into_itself_is_refused(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        with pytest.raises(ToolError, match="into itself"):
            run(src, src / "sub")

    def test_missing_src_suggests_similar(self, tmp_path):
        (tmp_path / "report.txt").write_text("x\n")
        with pytest.raises(ToolError, match="not found"):
            run(tmp_path / "reprot.txt", tmp_path / "b.txt")

    def test_identical_src_and_dest(self, tmp_path):
        src = tmp_path / "a.txt"
        src.write_text("x\n")
        with pytest.raises(ToolError, match="identical"):
            run(src, src)

    def test_missing_dest_parent_suggests_create_dir(self, tmp_path):
        src = tmp_path / "a.txt"
        src.write_text("x\n")
        with pytest.raises(ToolError, match="create_dir"):
            run(src, tmp_path / "missing" / "b.txt")
