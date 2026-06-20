import json

import pytest

from core.errors import ToolError
from core.policy import PolicyDecision
from core.tool_definition import PRIMITIVE, Targets, ToolGroup
from tools.inspect import DEFINITION, run


class ReadSearchOnly:
    def check(self, path, group, tool=None):
        if group in (ToolGroup.READ, ToolGroup.SEARCH):
            return PolicyDecision(allowed=True)
        return PolicyDecision(allowed=False, reason="read-only zone")


def result_of(path, **kwargs):
    return json.loads(run(path, **kwargs))


class TestDefinition:
    def test_matches_spec_table(self):
        assert DEFINITION.name == "inspect"
        assert DEFINITION.group is ToolGroup.READ
        assert DEFINITION.composition == PRIMITIVE
        assert DEFINITION.policy_union == frozenset({ToolGroup.READ})
        assert DEFINITION.targets is Targets.BOTH
        assert DEFINITION.pagination is False
        assert DEFINITION.git is False
        assert DEFINITION.friction == frozenset()


class TestFile:
    def test_csv_file_schema(self, tmp_path):
        path = tmp_path / "sales.csv"
        path.write_text("date,region,revenue\n2026-01-01,na,100\n2026-01-02,eu,200\n")
        result = result_of(path)
        assert result["type"] == "file"
        assert result["format"] == "csv"
        assert result["size_bytes"] == path.stat().st_size
        assert result["tier"] == 1
        assert result["structure"] == {
            "headers": ["date", "region", "revenue"],
            "rows": 2,
        }
        assert result["mtime"].endswith("Z")

    def test_default_permissions_are_all_groups(self, tmp_path):
        path = tmp_path / "a.txt"
        path.write_text("x\n")
        assert result_of(path)["permissions"] == [
            "read",
            "search",
            "mutate-content",
            "mutate-structure",
        ]

    def test_permissions_reflect_policy(self, tmp_path):
        path = tmp_path / "a.txt"
        path.write_text("x\n")
        result = result_of(path, policy=ReadSearchOnly())
        assert result["permissions"] == ["read", "search"]

    def test_json_structure_is_top_level_keys(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text(json.dumps({"config": {"a": 1}, "x": [1, 2, 3]}))
        assert result_of(path)["structure"] == {"keys": ["config", "x"]}

    def test_json_top_level_array_structure(self, tmp_path):
        path = tmp_path / "rows.json"
        path.write_text(json.dumps([1, 2, 3]))
        assert result_of(path)["structure"] == {"length": 3}

    def test_markdown_structure_is_heading_outline(self, tmp_path):
        path = tmp_path / "doc.md"
        path.write_text("# Title\nintro\n## Setup\nsteps\n## Usage\nrun\n")
        assert result_of(path)["structure"] == {
            "outline": ["# Title", "## Setup", "## Usage"]
        }

    def test_plain_text_structure_is_line_count(self, tmp_path):
        path = tmp_path / "notes.txt"
        path.write_text("a\nb\nc\n")
        assert result_of(path)["structure"] == {"lines": 3}

    def test_binary_file_has_tier_2_and_no_structure(self, tmp_path):
        path = tmp_path / "blob.bin"
        path.write_bytes(b"\x00\x01\x02")
        result = result_of(path)
        assert result["tier"] == 2
        assert "structure" not in result

    def test_tier_3_file_is_not_parsed(self, tmp_path):
        path = tmp_path / "big.csv"
        path.write_text("a,b\n" + "1,2\n" * 20)
        result = result_of(path, tier_threshold=10)
        assert result["tier"] == 3
        assert "structure" not in result


class TestFolder:
    @pytest.fixture
    def root(self, tmp_path):
        (tmp_path / "a.csv").write_bytes(b"x" * 10)
        (tmp_path / "b.txt").write_bytes(b"x" * 5)
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "c.csv").write_bytes(b"x" * 20)
        deep = sub / "deep"
        deep.mkdir()
        (deep / "d.pdf").write_bytes(b"x" * 30)
        return tmp_path

    def test_folder_schema(self, root):
        result = result_of(root)
        assert result["type"] == "folder"
        assert result["entries"] == {"files": 2, "dirs": 1}
        assert result["subtree_size_bytes"] == 65
        assert result["max_depth"] == 3
        assert result["tier_3_files"] == 0
        assert result["by_extension"] == {"csv": 2, "pdf": 1, "txt": 1}

    def test_tier_3_files_counted_against_threshold(self, root):
        result = result_of(root, tier_threshold=25)
        assert result["tier_3_files"] == 1

    def test_folder_permissions_reflect_policy(self, root):
        result = result_of(root, policy=ReadSearchOnly())
        assert result["permissions"] == ["read", "search"]

    def test_folder_stats_exclude_trash(self, root):
        trash = root / "_trash"
        trash.mkdir()
        (trash / "old.csv").write_bytes(b"x" * 1000)
        result = result_of(root)
        assert result["entries"] == {"files": 2, "dirs": 1}
        assert result["subtree_size_bytes"] == 65
        assert result["by_extension"] == {"csv": 2, "pdf": 1, "txt": 1}

    def test_folder_stats_exclude_fsagent(self, root):
        scratchpad_dir = root / ".fsagent"
        scratchpad_dir.mkdir()
        (scratchpad_dir / "scratchpad.md").write_bytes(b"x" * 1000)
        result = result_of(root)
        assert result["entries"] == {"files": 2, "dirs": 1}
        assert result["subtree_size_bytes"] == 65
        assert result["by_extension"] == {"csv": 2, "pdf": 1, "txt": 1}


class TestFailureShaping:
    def test_not_found_suggests_similar_paths(self, tmp_path):
        (tmp_path / "sales_2024.csv").write_text("a,b\n")
        with pytest.raises(ToolError) as exc:
            run(tmp_path / "sales2024.csv")
        assert "not found — similar paths:" in str(exc.value)
        assert "sales_2024.csv" in str(exc.value)
