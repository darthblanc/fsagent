import pytest

from core.errors import FrictionRequired, ToolError
from core.tool_definition import PRIMITIVE, Friction, Targets, ToolGroup
from tools import ALL_TOOLS
from tools.delete import DEFINITION, run


class TestDefinition:
    def test_matches_spec_table(self):
        assert DEFINITION.name == "delete"
        assert DEFINITION.group is ToolGroup.MUTATE_STRUCTURE
        assert DEFINITION.composition == PRIMITIVE
        assert DEFINITION.policy_union == frozenset({ToolGroup.MUTATE_STRUCTURE})
        assert DEFINITION.targets is Targets.BOTH
        assert DEFINITION.pagination is False
        assert DEFINITION.git is True
        assert DEFINITION.friction == frozenset({Friction.RECURSIVE})

    def test_registered(self):
        assert "delete" in ALL_TOOLS


class TestDelete:
    def test_deletes_file(self, tmp_path):
        path = tmp_path / "a.txt"
        path.write_text("x\n")
        assert run(path) == f"deleted '{path}'"
        assert not path.exists()

    def test_deletes_empty_folder(self, tmp_path):
        path = tmp_path / "empty"
        path.mkdir()
        assert run(path) == f"deleted '{path}'"
        assert not path.exists()

    def test_gitkeep_only_folder_counts_as_empty(self, tmp_path):
        path = tmp_path / "kept"
        path.mkdir()
        (path / ".gitkeep").write_bytes(b"")
        assert run(path) == f"deleted '{path}'"
        assert not path.exists()

    def test_recursive_confirms_with_census(self, tmp_path):
        path = tmp_path / "proj"
        sub = path / "sub"
        sub.mkdir(parents=True)
        (path / "a.txt").write_text("x\n")
        (sub / "b.txt").write_text("y\n")
        result = run(path, recursive=True)
        assert result == f"deleted '{path}' (2 files, 1 subfolders)"
        assert not path.exists()


class TestFrictionAsInformedConsent:
    def test_first_attempt_tells_you_what_is_inside(self, tmp_path):
        path = tmp_path / "proj"
        sub = path / "sub"
        sub.mkdir(parents=True)
        (path / "a.txt").write_text("x\n")
        (sub / "b.txt").write_text("y\n")
        with pytest.raises(FrictionRequired) as exc:
            run(path)
        assert str(exc.value) == (
            f"'{path}' contains 2 files, 1 subfolders — pass recursive=true to confirm"
        )
        assert path.exists()
        assert (path / "a.txt").exists()


class TestTierFlag:
    def test_tier_3_file_deletion_warns_not_recoverable(self, tmp_path):
        path = tmp_path / "big.bin"
        path.write_bytes(b"x" * 100)
        result = run(path, tier_threshold=50)
        assert "tier 3 — contents NOT recoverable from history" in result

    def test_tier_3_content_inside_folder_warns(self, tmp_path):
        path = tmp_path / "proj"
        path.mkdir()
        (path / "big.bin").write_bytes(b"x" * 100)
        result = run(path, recursive=True, tier_threshold=50)
        assert "tier 3 — contents NOT recoverable from history" in result

    def test_tier_1_deletion_is_recoverable_no_flag(self, tmp_path):
        path = tmp_path / "a.txt"
        path.write_text("x\n")
        assert "tier 3" not in run(path)


class TestTrashStaging:
    def test_delete_stages_to_trash_invisibly(self, tmp_path):
        path = tmp_path / "reports" / "q1.csv"
        path.parent.mkdir()
        path.write_text("data\n")
        result = run(path, sandbox_root=tmp_path)
        # exact match proves the confirmation never mentions staging
        assert result == f"deleted '{path}'"
        assert not path.exists()
        assert (tmp_path / "_trash" / "reports" / "q1.csv").read_text() == "data\n"

    def test_repeat_deletions_do_not_collide(self, tmp_path):
        path = tmp_path / "a.txt"
        path.write_text("first\n")
        run(path, sandbox_root=tmp_path)
        path.write_text("second\n")
        run(path, sandbox_root=tmp_path)
        trash = tmp_path / "_trash"
        staged = sorted(p.name for p in trash.iterdir())
        assert staged == ["a.txt", "a.txt~1"]
        assert (trash / "a.txt").read_text() == "first\n"
        assert (trash / "a.txt~1").read_text() == "second\n"

    def test_folder_staged_with_structure(self, tmp_path):
        proj = tmp_path / "proj"
        (proj / "sub").mkdir(parents=True)
        (proj / "sub" / "b.txt").write_text("y\n")
        run(proj, recursive=True, sandbox_root=tmp_path)
        assert not proj.exists()
        assert (tmp_path / "_trash" / "proj" / "sub" / "b.txt").read_text() == "y\n"

    def test_deleting_inside_trash_is_real_deletion(self, tmp_path):
        path = tmp_path / "a.txt"
        path.write_text("x\n")
        run(path, sandbox_root=tmp_path)
        staged = tmp_path / "_trash" / "a.txt"
        assert staged.exists()
        run(staged, sandbox_root=tmp_path)
        assert not staged.exists()
        assert not (tmp_path / "_trash" / "_trash").exists()


class TestFailureShaping:
    def test_missing_path_suggests_similar(self, tmp_path):
        (tmp_path / "report.txt").write_text("x\n")
        with pytest.raises(ToolError, match="not found"):
            run(tmp_path / "reprot.txt")
