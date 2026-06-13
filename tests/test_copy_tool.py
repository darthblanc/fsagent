import pytest

from core.errors import ToolError
from core.tool_definition import Friction, Targets, ToolGroup
from tools import ALL_TOOLS
from tools.copy import DEFINITION, run


class TestDefinition:
    def test_matches_spec_table(self):
        assert DEFINITION.name == "copy"
        assert DEFINITION.group is ToolGroup.MUTATE_STRUCTURE
        assert DEFINITION.composition == ("read", "write")
        assert DEFINITION.policy_union == frozenset(
            {ToolGroup.READ, ToolGroup.MUTATE_STRUCTURE}
        )
        assert DEFINITION.policy_map == {
            "src": ToolGroup.READ,
            "dest": ToolGroup.MUTATE_STRUCTURE,
        }
        assert DEFINITION.targets is Targets.BOTH
        assert DEFINITION.pagination is False
        assert DEFINITION.git is True
        assert DEFINITION.friction == frozenset({Friction.OVERWRITE})

    def test_registered(self):
        assert "copy" in ALL_TOOLS


class TestCopy:
    def test_copies_file_and_confirms(self, tmp_path):
        src = tmp_path / "a.txt"
        src.write_text("data\n")
        dest = tmp_path / "b.txt"
        result = run(src, dest)
        assert result == f"copied '{src}' → '{dest}'"
        assert src.read_text() == "data\n"
        assert dest.read_text() == "data\n"

    def test_byte_perfect_fidelity_below_the_membrane(self, tmp_path):
        src = tmp_path / "blob.bin"
        src.write_bytes(b"\x00\x01\x02raw")
        dest = tmp_path / "copy.bin"
        run(src, dest)
        assert dest.read_bytes() == src.read_bytes()

    def test_copies_folder_recursively(self, tmp_path):
        src = tmp_path / "src"
        (src / "deep").mkdir(parents=True)
        (src / "a.txt").write_text("x\n")
        (src / "deep" / "b.txt").write_text("y\n")
        dest = tmp_path / "dest"
        result = run(src, dest)
        assert result == f"copied '{src}' → '{dest}'"
        assert (dest / "a.txt").read_text() == "x\n"
        assert (dest / "deep" / "b.txt").read_text() == "y\n"
        assert (src / "a.txt").exists()

    def test_overwrite_replaces_existing_file(self, tmp_path):
        src = tmp_path / "a.txt"
        src.write_text("new\n")
        dest = tmp_path / "b.txt"
        dest.write_text("old\n")
        run(src, dest, overwrite=True)
        assert dest.read_text() == "new\n"

    def test_tier_3_copy_is_flagged(self, tmp_path):
        src = tmp_path / "big.txt"
        src.write_text("x" * 100 + "\n")
        result = run(src, tmp_path / "copy.txt", tier_threshold=50)
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

    def test_existing_folder_dest_suggests_full_path(self, tmp_path):
        src = tmp_path / "a.txt"
        src.write_text("x\n")
        folder = tmp_path / "archive"
        folder.mkdir()
        with pytest.raises(ToolError, match="existing folder"):
            run(src, folder)

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
