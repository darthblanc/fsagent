import pytest

from functions import (
    append,
    create_dir,
    delete,
    edit,
    glob,
    grep,
    inspect,
    list_dir,
    move,
    read,
    write,
)


class TestRead:
    def test_returns_file_bytes(self, tmp_path):
        path = tmp_path / "a.txt"
        path.write_bytes(b"hello\nworld\n")
        assert read(path) == b"hello\nworld\n"

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            read(tmp_path / "missing.txt")


class TestInspect:
    def test_file_metadata(self, tmp_path):
        path = tmp_path / "a.txt"
        path.write_bytes(b"12345")
        info = inspect(path)
        assert info.kind == "file"
        assert info.size == 5
        assert info.mtime > 0

    def test_folder_metadata(self, tmp_path):
        info = inspect(tmp_path)
        assert info.kind == "folder"

    def test_missing_path_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            inspect(tmp_path / "missing")


class TestListDir:
    def test_returns_sorted_entry_names(self, tmp_path):
        (tmp_path / "b.txt").write_bytes(b"")
        (tmp_path / "a.txt").write_bytes(b"")
        (tmp_path / "sub").mkdir()
        assert list_dir(tmp_path) == ["a.txt", "b.txt", "sub"]

    def test_file_target_raises(self, tmp_path):
        path = tmp_path / "a.txt"
        path.write_bytes(b"")
        with pytest.raises(NotADirectoryError):
            list_dir(path)


class TestGlob:
    def test_matches_files_and_folders(self, tmp_path):
        (tmp_path / "a.py").write_bytes(b"")
        (tmp_path / "b.txt").write_bytes(b"")
        (tmp_path / "pkg").mkdir()
        (tmp_path / "pkg" / "c.py").write_bytes(b"")
        assert glob(tmp_path, "**/*.py") == [
            tmp_path / "a.py",
            tmp_path / "pkg" / "c.py",
        ]
        assert glob(tmp_path, "p*") == [tmp_path / "pkg"]

    def test_no_matches_is_empty(self, tmp_path):
        assert glob(tmp_path, "*.rs") == []


class TestGrep:
    def test_returns_matching_lines_with_numbers(self, tmp_path):
        path = tmp_path / "a.txt"
        path.write_bytes(b"alpha\nbeta\ngamma beta\n")
        assert grep(path, rb"beta") == [(2, b"beta"), (3, b"gamma beta")]

    def test_pattern_is_a_regex(self, tmp_path):
        path = tmp_path / "a.txt"
        path.write_bytes(b"x1\ny2\nz3\n")
        assert grep(path, rb"^[xy]\d") == [(1, b"x1"), (2, b"y2")]

    def test_no_matches_is_empty(self, tmp_path):
        path = tmp_path / "a.txt"
        path.write_bytes(b"alpha\n")
        assert grep(path, rb"beta") == []


class TestWrite:
    def test_creates_file(self, tmp_path):
        path = tmp_path / "a.txt"
        write(path, b"data")
        assert path.read_bytes() == b"data"

    def test_overwrites_existing_file(self, tmp_path):
        path = tmp_path / "a.txt"
        path.write_bytes(b"old")
        write(path, b"new")
        assert path.read_bytes() == b"new"


class TestEdit:
    def test_replaces_occurrences_and_returns_count(self, tmp_path):
        path = tmp_path / "a.txt"
        path.write_bytes(b"foo bar foo")
        assert edit(path, b"foo", b"qux") == 2
        assert path.read_bytes() == b"qux bar qux"

    def test_no_match_returns_zero_and_leaves_file_untouched(self, tmp_path):
        path = tmp_path / "a.txt"
        path.write_bytes(b"foo")
        before = path.stat().st_mtime_ns
        assert edit(path, b"zzz", b"qux") == 0
        assert path.read_bytes() == b"foo"
        assert path.stat().st_mtime_ns == before


class TestAppend:
    def test_appends_to_existing_file(self, tmp_path):
        path = tmp_path / "a.txt"
        path.write_bytes(b"one")
        append(path, b"two")
        assert path.read_bytes() == b"onetwo"

    def test_creates_file_when_missing(self, tmp_path):
        path = tmp_path / "a.txt"
        append(path, b"data")
        assert path.read_bytes() == b"data"


class TestCreateDir:
    def test_creates_directory(self, tmp_path):
        path = tmp_path / "sub"
        create_dir(path)
        assert path.is_dir()

    def test_existing_directory_raises(self, tmp_path):
        with pytest.raises(FileExistsError):
            create_dir(tmp_path)

    def test_missing_parent_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            create_dir(tmp_path / "a" / "b")


class TestMove:
    def test_moves_file(self, tmp_path):
        src = tmp_path / "a.txt"
        src.write_bytes(b"data")
        dest = tmp_path / "b.txt"
        move(src, dest)
        assert not src.exists()
        assert dest.read_bytes() == b"data"

    def test_overwrites_existing_destination_file(self, tmp_path):
        src = tmp_path / "a.txt"
        src.write_bytes(b"new")
        dest = tmp_path / "b.txt"
        dest.write_bytes(b"old")
        move(src, dest)
        assert dest.read_bytes() == b"new"

    def test_moves_folder(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "a.txt").write_bytes(b"data")
        dest = tmp_path / "dest"
        move(src, dest)
        assert not src.exists()
        assert (dest / "a.txt").read_bytes() == b"data"


class TestDelete:
    def test_deletes_file(self, tmp_path):
        path = tmp_path / "a.txt"
        path.write_bytes(b"")
        delete(path)
        assert not path.exists()

    def test_deletes_empty_folder(self, tmp_path):
        path = tmp_path / "sub"
        path.mkdir()
        delete(path)
        assert not path.exists()

    def test_non_empty_folder_requires_recursive(self, tmp_path):
        path = tmp_path / "sub"
        path.mkdir()
        (path / "a.txt").write_bytes(b"")
        with pytest.raises(OSError):
            delete(path)
        assert path.exists()

    def test_recursive_deletes_non_empty_folder(self, tmp_path):
        path = tmp_path / "sub"
        path.mkdir()
        (path / "a.txt").write_bytes(b"")
        delete(path, recursive=True)
        assert not path.exists()
