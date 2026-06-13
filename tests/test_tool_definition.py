import pytest
from pydantic import ValidationError

from core.tool_definition import (
    PRIMITIVE,
    Friction,
    Targets,
    ToolDefinition,
    ToolGroup,
)


def make_tool(**overrides) -> ToolDefinition:
    """Build a valid primitive read tool, with per-test overrides."""
    fields = dict(
        name="read_file",
        group=ToolGroup.READ,
        composition=PRIMITIVE,
        policy_union={ToolGroup.READ},
        targets=Targets.FILES,
        pagination=True,
        git=False,
    )
    fields.update(overrides)
    return ToolDefinition(**fields)


class TestValidDeclarations:
    def test_primitive_tool_round_trips(self):
        tool = make_tool()
        assert tool.name == "read_file"
        assert tool.group is ToolGroup.READ
        assert tool.composition == PRIMITIVE
        assert tool.policy_union == frozenset({ToolGroup.READ})
        assert tool.targets is Targets.FILES
        assert tool.pagination is True
        assert tool.git is False

    def test_friction_defaults_to_empty(self):
        assert make_tool().friction == frozenset()

    def test_composed_tool_with_mixed_policy_union(self):
        tool = make_tool(
            name="move_matching",
            group=ToolGroup.MUTATE_STRUCTURE,
            composition=["find_entries", "move_entry"],
            policy_union={ToolGroup.SEARCH, ToolGroup.MUTATE_STRUCTURE},
            friction={Friction.UNIQUE_MATCH, Friction.OVERWRITE},
            targets=Targets.BOTH,
        )
        assert tool.composition == ("find_entries", "move_entry")
        assert tool.policy_union == frozenset(
            {ToolGroup.SEARCH, ToolGroup.MUTATE_STRUCTURE}
        )
        assert tool.friction == frozenset(
            {Friction.UNIQUE_MATCH, Friction.OVERWRITE}
        )

    def test_string_values_coerce_to_enums(self):
        tool = make_tool(
            name="delete_folder",
            group="mutate-structure",
            policy_union={"mutate-structure"},
            friction={"recursive"},
            targets="folders",
        )
        assert tool.group is ToolGroup.MUTATE_STRUCTURE
        assert tool.policy_union == frozenset({ToolGroup.MUTATE_STRUCTURE})
        assert tool.friction == frozenset({Friction.RECURSIVE})
        assert tool.targets is Targets.FOLDERS


class TestName:
    @pytest.mark.parametrize(
        "bad_name",
        ["", "ReadFile", "read-file", "1read", "read file"],
    )
    def test_rejects_non_snake_case_identifiers(self, bad_name):
        with pytest.raises(ValidationError):
            make_tool(name=bad_name)


class TestGroup:
    def test_transform_group_is_reserved(self):
        with pytest.raises(ValidationError, match="reserved"):
            make_tool(group=ToolGroup.TRANSFORM, policy_union={ToolGroup.READ})


class TestPolicyUnion:
    def test_rejects_empty_policy_union(self):
        with pytest.raises(ValidationError):
            make_tool(policy_union=set())

    def test_rejects_transform_in_policy_union(self):
        with pytest.raises(ValidationError, match="reserved"):
            make_tool(policy_union={ToolGroup.READ, ToolGroup.TRANSFORM})


class TestComposition:
    def test_rejects_empty_function_list(self):
        with pytest.raises(ValidationError):
            make_tool(composition=[])

    def test_rejects_duplicate_function_names(self):
        with pytest.raises(ValidationError):
            make_tool(composition=["find_entries", "find_entries"])

    def test_rejects_invalid_function_names(self):
        with pytest.raises(ValidationError):
            make_tool(composition=["find entries"])


class TestPolicyConsistency:
    def test_primitive_policy_union_must_equal_its_group(self):
        with pytest.raises(ValidationError):
            make_tool(policy_union={ToolGroup.READ, ToolGroup.SEARCH})

    def test_composed_policy_union_must_contain_its_group(self):
        with pytest.raises(ValidationError):
            make_tool(
                name="grep_files",
                group=ToolGroup.SEARCH,
                composition=["read_entry"],
                policy_union={ToolGroup.READ},
            )


class TestComposedPolicyWarning:
    def test_composed_tool_surfaces_cartesian_fallback_note(self):
        from core.tool_definition import ComposedPolicyWarning

        with pytest.warns(ComposedPolicyWarning) as captured:
            make_tool(
                name="copy",
                group=ToolGroup.MUTATE_STRUCTURE,
                composition=["read", "write"],
                policy_union={ToolGroup.READ, ToolGroup.MUTATE_STRUCTURE},
            )
        message = str(captured[0].message)
        assert "cartesian" in message
        assert "over-deny" in message
        assert "fails closed" in message

    def test_primitive_tool_does_not_warn(self, recwarn):
        make_tool()
        assert len(recwarn) == 0

    def test_composed_tool_with_policy_map_does_not_warn(self, recwarn):
        make_tool(
            name="copy",
            group=ToolGroup.MUTATE_STRUCTURE,
            composition=["read", "write"],
            policy_union={ToolGroup.READ, ToolGroup.MUTATE_STRUCTURE},
            policy_map={"src": ToolGroup.READ, "dest": ToolGroup.MUTATE_STRUCTURE},
        )
        assert len(recwarn) == 0


class TestPolicyMap:
    def composed(self, **overrides):
        fields = dict(
            name="copy",
            group=ToolGroup.MUTATE_STRUCTURE,
            composition=["read", "write"],
            policy_union={ToolGroup.READ, ToolGroup.MUTATE_STRUCTURE},
            policy_map={"src": ToolGroup.READ, "dest": ToolGroup.MUTATE_STRUCTURE},
        )
        fields.update(overrides)
        return make_tool(**fields)

    def test_valid_map_round_trips(self):
        tool = self.composed()
        assert tool.policy_map == {
            "src": ToolGroup.READ,
            "dest": ToolGroup.MUTATE_STRUCTURE,
        }

    def test_string_groups_coerce(self):
        tool = self.composed(
            policy_map={"src": "read", "dest": "mutate-structure"}
        )
        assert tool.policy_map["src"] is ToolGroup.READ

    def test_map_must_union_to_exactly_policy_union(self):
        with pytest.raises(ValidationError, match="policy_union"):
            self.composed(policy_map={"src": ToolGroup.READ, "dest": ToolGroup.READ})

    def test_empty_map_is_rejected(self):
        with pytest.raises(ValidationError):
            self.composed(policy_map={})

    def test_primitive_with_map_is_rejected(self):
        with pytest.raises(ValidationError, match="composed"):
            make_tool(policy_map={"path": ToolGroup.READ})


class TestImmutability:
    def test_declarations_are_frozen(self):
        tool = make_tool()
        with pytest.raises(ValidationError):
            tool.pagination = False
