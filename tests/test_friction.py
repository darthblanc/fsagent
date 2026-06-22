import pytest

from core.errors import FrictionRequired
from core.friction import StandardFriction
from tools.edit import DEFINITION as EDIT_DEFINITION
from tools.read import DEFINITION as READ_DEFINITION
from tools.write import DEFINITION as WRITE_DEFINITION


@pytest.fixture
def gate():
    return StandardFriction()


class TestOverwriteFriction:
    def test_first_attempt_on_existing_file_fails_informatively(self, gate, tmp_path):
        path = tmp_path / "r.txt"
        path.write_text("one\ntwo\nthree\n")
        with pytest.raises(FrictionRequired) as exc:
            gate.check(WRITE_DEFINITION, {"path": path, "content": "x"})
        assert str(exc.value) == f"'{path}' exists (3 lines) — pass overwrite=true, or use edit"
        assert exc.value.kwarg == "overwrite"

    def test_overwrite_true_is_an_informed_action(self, gate, tmp_path):
        path = tmp_path / "r.txt"
        path.write_text("old\n")
        gate.check(WRITE_DEFINITION, {"path": path, "content": "x", "overwrite": True})

    def test_new_file_needs_no_flag(self, gate, tmp_path):
        gate.check(WRITE_DEFINITION, {"path": tmp_path / "new.txt", "content": "x"})

    def test_tool_without_overwrite_friction_is_untouched(self, gate, tmp_path):
        path = tmp_path / "r.txt"
        path.write_text("x\n")
        gate.check(READ_DEFINITION, {"path": path})


class TestMoveOverwriteFriction:
    @pytest.fixture
    def move_definition(self):
        from tools.move import DEFINITION

        return DEFINITION

    def test_existing_file_dest_is_friction_denied(self, gate, tmp_path, move_definition):
        src = tmp_path / "a.txt"
        src.write_text("x\n")
        dest = tmp_path / "b.txt"
        dest.write_text("y\n")
        with pytest.raises(FrictionRequired) as exc:
            gate.check(move_definition, {"src": src, "dest": dest})
        assert str(exc.value) == f"destination '{dest}' exists — pass overwrite=true"
        assert exc.value.kwarg == "overwrite"

    def test_overwrite_true_is_an_informed_action(self, gate, tmp_path, move_definition):
        dest = tmp_path / "b.txt"
        dest.write_text("y\n")
        gate.check(move_definition, {"src": tmp_path / "a.txt", "dest": dest, "overwrite": True})

    def test_new_dest_passes(self, gate, tmp_path, move_definition):
        gate.check(move_definition, {"src": tmp_path / "a.txt", "dest": tmp_path / "new.txt"})

    def test_folder_dest_is_left_to_the_handler(self, gate, tmp_path, move_definition):
        gate.check(move_definition, {"src": tmp_path / "a.txt", "dest": tmp_path})


class TestRecursiveFriction:
    @pytest.fixture
    def delete_definition(self):
        from tools.delete import DEFINITION

        return DEFINITION

    def test_non_empty_folder_is_friction_denied_with_census(self, gate, tmp_path, delete_definition):
        folder = tmp_path / "proj"
        sub = folder / "sub"
        sub.mkdir(parents=True)
        (folder / "a.txt").write_text("x\n")
        (sub / "b.txt").write_text("y\n")
        with pytest.raises(FrictionRequired) as exc:
            gate.check(delete_definition, {"path": folder})
        assert str(exc.value) == (
            f"'{folder}' contains 2 files, 1 subfolders — pass recursive=true to confirm"
        )
        assert exc.value.kwarg == "recursive"

    def test_recursive_true_is_an_informed_action(self, gate, tmp_path, delete_definition):
        folder = tmp_path / "proj"
        folder.mkdir()
        (folder / "a.txt").write_text("x\n")
        gate.check(delete_definition, {"path": folder, "recursive": True})

    def test_empty_folder_passes(self, gate, tmp_path, delete_definition):
        folder = tmp_path / "empty"
        folder.mkdir()
        gate.check(delete_definition, {"path": folder})

    def test_gitkeep_only_folder_passes(self, gate, tmp_path, delete_definition):
        folder = tmp_path / "kept"
        folder.mkdir()
        (folder / ".gitkeep").write_bytes(b"")
        gate.check(delete_definition, {"path": folder})

    def test_file_target_passes(self, gate, tmp_path, delete_definition):
        path = tmp_path / "a.txt"
        path.write_text("x\n")
        gate.check(delete_definition, {"path": path})


class TestUniqueMatchFriction:
    def test_ambiguous_match_is_friction_denied(self, gate, tmp_path):
        path = tmp_path / "r.txt"
        path.write_text("foo\nfoo\n")
        with pytest.raises(FrictionRequired, match="matched 2 locations") as exc:
            gate.check(EDIT_DEFINITION, {"path": path, "old_str": "foo", "new_str": "x"})
        assert exc.value.kwarg == "replace_all"

    def test_ambiguous_match_with_replace_all_is_an_informed_action(self, gate, tmp_path):
        path = tmp_path / "r.txt"
        path.write_text("foo\nfoo\n")
        gate.check(
            EDIT_DEFINITION,
            {"path": path, "old_str": "foo", "new_str": "x", "replace_all": True},
        )

    def test_zero_matches_is_friction_denied(self, gate, tmp_path):
        path = tmp_path / "r.txt"
        path.write_text("bar\n")
        with pytest.raises(FrictionRequired, match="no exact match") as exc:
            gate.check(EDIT_DEFINITION, {"path": path, "old_str": "foo", "new_str": "x"})
        assert exc.value.kwarg is None

    def test_zero_matches_ignores_replace_all(self, gate, tmp_path):
        # replace_all can't manufacture text that doesn't exist in the file.
        path = tmp_path / "r.txt"
        path.write_text("bar\n")
        with pytest.raises(FrictionRequired, match="no exact match"):
            gate.check(
                EDIT_DEFINITION,
                {"path": path, "old_str": "foo", "new_str": "x", "replace_all": True},
            )

    def test_unique_match_passes(self, gate, tmp_path):
        path = tmp_path / "r.txt"
        path.write_text("foo\nbar\n")
        gate.check(EDIT_DEFINITION, {"path": path, "old_str": "foo", "new_str": "x"})

    def test_missing_file_is_left_to_the_handler(self, gate, tmp_path):
        gate.check(EDIT_DEFINITION, {"path": tmp_path / "nope.txt", "old_str": "foo", "new_str": "x"})
