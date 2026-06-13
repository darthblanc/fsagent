import pytest

from core.errors import ToolError
from core.tool_definition import PRIMITIVE, Targets, ToolGroup
from tools import ALL_TOOLS
from tools.grep import DEFINITION, run


@pytest.fixture
def root(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "sales_2024.csv").write_text("date,region,revenue\n2026-01-01,na,100\n2026-01-02,eu,200\n")
    (data / "sales_2025.csv").write_text("date,region,revenue\n2026-01-01,eu,300\n2026-01-02,eu,400\n")
    (tmp_path / "notes.txt").write_text("alpha\nbeta\ngamma\n")
    (tmp_path / "blob.bin").write_bytes(b"\x00eu\x00")
    return tmp_path


class TestDefinition:
    def test_matches_spec_table(self):
        assert DEFINITION.name == "grep"
        assert DEFINITION.group is ToolGroup.SEARCH
        assert DEFINITION.composition == PRIMITIVE
        assert DEFINITION.policy_union == frozenset({ToolGroup.SEARCH})
        assert DEFINITION.targets is Targets.FILES
        assert DEFINITION.pagination is True
        assert DEFINITION.git is False
        assert DEFINITION.friction == frozenset()

    def test_registered(self):
        assert "grep" in ALL_TOOLS


class TestFilesMode:
    def test_default_returns_paths_with_match_counts(self, root):
        assert run("eu", scope=root) == (
            "data/sales_2024.csv · 1\ndata/sales_2025.csv · 2"
        )

    def test_binary_files_are_skipped(self, root):
        result = run("eu", scope=root)
        assert "blob.bin" not in result

    def test_pattern_is_a_regex(self, root):
        assert run(r"^beta", scope=root) == "notes.txt · 1"

    def test_invalid_regex_falls_back_to_substring(self, tmp_path):
        (tmp_path / "weird.txt").write_text("a(b\n")
        assert run("a(b", scope=tmp_path) == "weird.txt · 1"

    def test_no_matches_is_informative_not_an_error(self, root):
        assert run("zzz", scope=root) == "no matches for 'zzz'"

    def test_scope_falls_back_to_sandbox_root(self, root):
        assert run("alpha", sandbox_root=root) == "notes.txt · 1"

    def test_trash_contents_are_not_searched(self, tmp_path):
        trash = tmp_path / "_trash"
        trash.mkdir()
        (trash / "old.txt").write_text("target\n")
        (tmp_path / "live.txt").write_text("target\n")
        assert run("target", scope=tmp_path) == "live.txt · 1"


class TestContentMode:
    def test_match_with_context_feeds_read_and_edit(self, root):
        assert run("beta", scope=root, mode="content") == (
            "notes.txt:1- alpha\n"
            "notes.txt:2: beta\n"
            "notes.txt:3- gamma"
        )

    def test_context_lines_zero(self, root):
        assert run("beta", scope=root, mode="content", context_lines=0) == (
            "notes.txt:2: beta"
        )

    def test_multiple_match_blocks_are_separated(self, tmp_path):
        (tmp_path / "m.txt").write_text("one\nfoo\nthree\nfour\nfoo\nsix\n")
        assert run("foo", scope=tmp_path, mode="content", context_lines=1) == (
            "m.txt:1- one\n"
            "m.txt:2: foo\n"
            "m.txt:3- three\n"
            "--\n"
            "m.txt:4- four\n"
            "m.txt:5: foo\n"
            "m.txt:6- six"
        )


class TestPagination:
    @pytest.fixture
    def many(self, tmp_path):
        for i in range(5):
            (tmp_path / f"f{i}.txt").write_text("target\n")
        return tmp_path

    def test_truncation_notice_offers_continuation(self, many):
        result = run("target", scope=many, limit=2)
        assert result.startswith("f0.txt · 1\nf1.txt · 1\n")
        assert result.endswith(
            "5 matches, showing 1–2 — narrow the pattern or scope, "
            "or continue with offset=2"
        )

    def test_offset_resumes(self, many):
        result = run("target", scope=many, offset=2, limit=2)
        assert result.startswith("f2.txt · 1\n")
        assert "showing 3–4" in result

    def test_final_page_has_no_notice(self, many):
        assert run("target", scope=many, offset=4, limit=2) == "f4.txt · 1"

    def test_hard_cap_is_honest_and_does_not_offer_continuation(self, many, monkeypatch):
        monkeypatch.setattr("tools.grep.RESULT_CAP", 3)
        result = run("target", scope=many)
        assert result.endswith("3+ matches, showing 1–3 — narrow the pattern or scope")
        assert "offset=" not in result

    def test_offset_beyond_end_raises(self, many):
        with pytest.raises(ToolError, match="beyond"):
            run("target", scope=many, offset=10)

    def test_negative_offset_raises(self, many):
        with pytest.raises(ToolError):
            run("target", scope=many, offset=-1)


class TestFailureShaping:
    def test_invalid_mode(self, root):
        with pytest.raises(ToolError, match="mode"):
            run("x", scope=root, mode="lines")

    def test_negative_context_lines(self, root):
        with pytest.raises(ToolError, match="context_lines"):
            run("x", scope=root, mode="content", context_lines=-1)

    def test_missing_scope_folder(self, root):
        with pytest.raises(ToolError, match="not found"):
            run("x", scope=root / "missing")

    def test_file_scope_is_shaped_failure(self, root):
        with pytest.raises(ToolError, match="folder"):
            run("x", scope=root / "notes.txt")

    def test_no_scope_at_all_raises(self):
        with pytest.raises(ToolError, match="scope"):
            run("x")
