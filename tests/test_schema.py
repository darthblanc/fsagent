from agent.schema import args_schema_for
from tools import ALL_TOOLS

_EXCLUDED = {"policy", "tier_threshold", "sandbox_root"}


def schema_for(name):
    return args_schema_for(ALL_TOOLS[name]).model_json_schema()


def test_write_schema():
    schema = schema_for("write")
    assert set(schema["properties"]) == {"path", "content", "overwrite"}
    assert schema["required"] == ["path", "content"]
    assert schema["properties"]["overwrite"]["type"] == "boolean"
    assert schema["properties"]["overwrite"]["default"] is False


def test_edit_schema():
    schema = schema_for("edit")
    assert set(schema["properties"]) == {"path", "old_str", "new_str"}
    assert schema["required"] == ["path", "old_str", "new_str"]


def test_append_schema():
    schema = schema_for("append")
    assert set(schema["properties"]) == {"path", "content"}
    assert schema["required"] == ["path", "content"]


def test_create_dir_schema():
    schema = schema_for("create_dir")
    assert set(schema["properties"]) == {"path"}
    assert schema["required"] == ["path"]


def test_delete_schema_excludes_pipeline_extras():
    schema = schema_for("delete")
    assert set(schema["properties"]) == {"path", "recursive"}
    assert schema["required"] == ["path"]
    assert schema["properties"]["recursive"]["type"] == "boolean"
    assert schema["properties"]["recursive"]["default"] is False


def test_move_and_copy_schema():
    for name in ("move", "copy"):
        schema = schema_for(name)
        assert set(schema["properties"]) == {"src", "dest", "overwrite"}
        assert schema["required"] == ["src", "dest"]


def test_inspect_schema_excludes_policy_and_tier_threshold():
    schema = schema_for("inspect")
    assert set(schema["properties"]) == {"path"}
    assert schema["required"] == ["path"]


def test_list_dir_schema():
    schema = schema_for("list_dir")
    assert set(schema["properties"]) == {"path", "offset", "limit", "depth"}
    assert schema["required"] == ["path"]


def test_glob_schema_excludes_sandbox_root():
    schema = schema_for("glob")
    assert set(schema["properties"]) == {"pattern", "scope", "offset", "limit"}
    assert schema["required"] == ["pattern"]


def test_read_selector_anyof():
    schema = schema_for("read")
    assert set(schema["properties"]) == {"path", "offset", "limit", "selector"}
    assert schema["required"] == ["path"]
    selector = schema["properties"]["selector"]
    types = {branch.get("type") for branch in selector["anyOf"]}
    assert types == {"string", "object", "null"}


def test_grep_mode_enum():
    schema = schema_for("grep")
    assert set(schema["properties"]) == {
        "pattern", "scope", "mode", "context_lines", "offset", "limit",
    }
    assert schema["required"] == ["pattern"]
    mode = schema["properties"]["mode"]
    assert mode["enum"] == ["files", "content"]
    assert mode["default"] == "files"


def test_all_tools_produce_schema_without_pipeline_extras():
    for tool in ALL_TOOLS.values():
        schema = args_schema_for(tool).model_json_schema()
        assert _EXCLUDED.isdisjoint(schema["properties"])
