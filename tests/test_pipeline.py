import json
import subprocess

import pytest

from core.errors import FrictionRequired, PolicyDenial, SandboxViolation, ToolError
from core.gitstage import GitCommit
from core.pipeline import Pipeline
from core.policy import AllowAllPolicy, PolicyDecision
from core.sandbox import Sandbox
from core.trajectory import Trajectory
from tools import ALL_TOOLS


class DenyReports:
    def check(self, path, group, tool=None):
        return PolicyDecision(
            allowed=False,
            reason="reports/ is read-only this session",
            alternative="copy it into drafts/ first",
        )


def make_pipeline(tmp_path, policy=None, **kwargs):
    root = tmp_path / "sandbox"
    root.mkdir(exist_ok=True)
    trajectory_path = tmp_path / "trajectory.jsonl"
    pipeline = Pipeline(
        sandbox=Sandbox(root),
        policy=policy or AllowAllPolicy(),
        trajectory=Trajectory(trajectory_path, session_id="s-test"),
        tools=ALL_TOOLS,
        **kwargs,
    )
    return pipeline, root, trajectory_path


def last_entry(trajectory_path):
    lines = trajectory_path.read_text().splitlines()
    return json.loads(lines[-1])


class TestSandboxStage:
    def test_relative_paths_resolve_inside_sandbox(self, tmp_path):
        pipeline, root, _ = make_pipeline(tmp_path)
        (root / "a.txt").write_text("hello\n")
        assert pipeline.call("read", path="a.txt") == "     1\thello"

    def test_escape_via_dotdot_is_denied(self, tmp_path):
        pipeline, _, trajectory_path = make_pipeline(tmp_path)
        (tmp_path / "secret.txt").write_text("x")
        with pytest.raises(SandboxViolation, match="sandbox"):
            pipeline.call("read", path="../secret.txt")
        entry = last_entry(trajectory_path)
        assert entry["status"] == "denied"
        assert entry["stage"] == "sandbox"

    def test_absolute_path_outside_is_denied(self, tmp_path):
        pipeline, _, _ = make_pipeline(tmp_path)
        with pytest.raises(SandboxViolation):
            pipeline.call("read", path="/etc/hostname")


class TestPolicyStage:
    def test_denial_carries_reason_and_alternative(self, tmp_path):
        pipeline, root, trajectory_path = make_pipeline(tmp_path, policy=DenyReports())
        (root / "a.txt").write_text("hello\n")
        with pytest.raises(PolicyDenial) as exc:
            pipeline.call("read", path="a.txt")
        message = str(exc.value)
        assert "reports/ is read-only this session" in message
        assert "copy it into drafts/ first" in message
        entry = last_entry(trajectory_path)
        assert entry["status"] == "denied"
        assert entry["stage"] == "policy"


class TestTrajectoryStage:
    def test_success_entry_fields(self, tmp_path):
        pipeline, root, trajectory_path = make_pipeline(tmp_path)
        (root / "a.txt").write_text("hello\n")
        pipeline.call("read", path="a.txt")
        entry = last_entry(trajectory_path)
        assert entry["tool"] == "read"
        assert entry["status"] == "ok"
        assert entry["session"] == "s-test"
        assert entry["args"] == {"path": "a.txt"}
        assert entry["tier"] == 1
        assert entry["token_estimate"] >= 1
        assert isinstance(entry["request_id"], int)

    def test_execute_errors_are_recorded(self, tmp_path):
        pipeline, _, trajectory_path = make_pipeline(tmp_path)
        with pytest.raises(ToolError, match="not found"):
            pipeline.call("read", path="missing.txt")
        entry = last_entry(trajectory_path)
        assert entry["status"] == "error"
        assert entry["stage"] == "execute"


class TestTierWarnings:
    def test_binary_file_recorded_as_tier_2(self, tmp_path):
        pipeline, root, trajectory_path = make_pipeline(tmp_path)
        (root / "blob.bin").write_bytes(b"\x00\x01binary")
        pipeline.call("read", path="blob.bin")
        assert last_entry(trajectory_path)["tier"] == 2

    def test_oversized_file_recorded_as_tier_3_but_still_readable(self, tmp_path):
        pipeline, root, trajectory_path = make_pipeline(tmp_path, tier_threshold=10)
        (root / "big.txt").write_text("x" * 40 + "\n")
        result = pipeline.call("read", path="big.txt")
        assert "x" in result
        assert last_entry(trajectory_path)["tier"] == 3


class ReadSearchOnly:
    def check(self, path, group, tool=None):
        from core.tool_definition import ToolGroup

        if group in (ToolGroup.READ, ToolGroup.SEARCH):
            return PolicyDecision(allowed=True)
        return PolicyDecision(allowed=False, reason="read-only zone")


class TestHandlerInjection:
    def test_inspect_sees_effective_policy_through_pipeline(self, tmp_path):
        pipeline, root, _ = make_pipeline(tmp_path, policy=ReadSearchOnly())
        (root / "a.txt").write_text("x\n")
        result = json.loads(pipeline.call("inspect", path="a.txt"))
        assert result["permissions"] == ["read", "search"]

    def test_inspect_sees_tier_threshold_through_pipeline(self, tmp_path):
        pipeline, root, _ = make_pipeline(tmp_path, tier_threshold=10)
        (root / "big.txt").write_text("x" * 40)
        result = json.loads(pipeline.call("inspect", path="big.txt"))
        assert result["tier"] == 3


class TestGlobThroughPipeline:
    def test_scope_defaults_to_sandbox_root(self, tmp_path):
        pipeline, root, _ = make_pipeline(tmp_path)
        (root / "a.txt").write_text("x")
        (root / "b.csv").write_text("x")
        assert pipeline.call("glob", pattern="*.txt") == "a.txt"

    def test_explicit_scope_is_sandbox_checked(self, tmp_path):
        pipeline, _, _ = make_pipeline(tmp_path)
        with pytest.raises(SandboxViolation):
            pipeline.call("glob", pattern="*", scope="..")

    def test_explicit_scope_none_defaults_to_sandbox_root(self, tmp_path):
        # Pydantic fills the handler's scope=None default into kwargs when
        # the model omits it via StructuredTool.invoke() — unlike the test
        # suite's direct tool.func() calls, the key is present with value
        # None, not absent. Must behave the same as omitting it entirely.
        pipeline, root, _ = make_pipeline(tmp_path)
        (root / "a.txt").write_text("x")
        assert pipeline.call("glob", pattern="*.txt", scope=None) == "a.txt"


class TestGrepThroughPipeline:
    def test_explicit_scope_none_defaults_to_sandbox_root(self, tmp_path):
        pipeline, root, _ = make_pipeline(tmp_path)
        (root / "a.txt").write_text("alpha\n")
        assert pipeline.call("grep", pattern="alpha", scope=None) == "a.txt · 1"


def commit_count(root):
    result = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=root, capture_output=True, text=True,
    )
    return int(result.stdout) if result.returncode == 0 else 0


class TestWriteThroughPipeline:
    def make(self, tmp_path):
        root = tmp_path / "sandbox"
        root.mkdir(exist_ok=True)
        return make_pipeline(tmp_path, git=GitCommit(root, session_id="s-test"))

    def test_write_executes_commits_and_logs(self, tmp_path):
        pipeline, root, trajectory_path = self.make(tmp_path)
        result = pipeline.call("write", path="r.txt", content="hello\n")
        assert (root / "r.txt").read_text() == "hello\n"
        assert "+hello" in result
        assert commit_count(root) == 1
        entry = last_entry(trajectory_path)
        assert entry["status"] == "ok"
        assert entry["tier"] == 1

    def test_friction_first_attempt_denied_then_informed_retry_succeeds(self, tmp_path):
        pipeline, root, trajectory_path = self.make(tmp_path)
        (root / "r.txt").write_text("old\n")
        with pytest.raises(FrictionRequired, match="overwrite=true"):
            pipeline.call("write", path="r.txt", content="new\n")
        assert (root / "r.txt").read_text() == "old\n"
        assert commit_count(root) == 0
        entry = last_entry(trajectory_path)
        assert entry["status"] == "denied"
        assert entry["stage"] == "friction"

        result = pipeline.call("write", path="r.txt", content="new\n", overwrite=True)
        assert "-old" in result and "+new" in result
        assert (root / "r.txt").read_text() == "new\n"
        assert commit_count(root) == 1


class TestCreateDirThroughPipeline:
    def test_empty_folder_is_tracked_via_gitkeep(self, tmp_path):
        root = tmp_path / "sandbox"
        root.mkdir(exist_ok=True)
        pipeline, root, _ = make_pipeline(
            tmp_path, git=GitCommit(root, session_id="s-test")
        )
        pipeline.call("create_dir", path="newdir")
        tracked = subprocess.run(
            ["git", "ls-files"], cwd=root, capture_output=True, text=True, check=True
        ).stdout
        assert "newdir/.gitkeep" in tracked


class ReadDeniedUnder:
    """Deny read inside one zone; allow everything else."""

    def __init__(self, zone):
        self.zone = zone

    def check(self, path, group, tool=None):
        from core.tool_definition import ToolGroup

        if group is ToolGroup.READ and self.zone in str(path):
            return PolicyDecision(
                allowed=False,
                reason=f"{self.zone}/ is read-denied",
                alternative="ask for the zone to be opened",
            )
        return PolicyDecision(allowed=True)


class MutateDeniedUnder:
    """Deny mutation inside one zone; allow read/search everywhere."""

    def __init__(self, zone):
        self.zone = zone

    def check(self, path, group, tool=None):
        from core.tool_definition import ToolGroup

        mutating = group in (ToolGroup.MUTATE_CONTENT, ToolGroup.MUTATE_STRUCTURE)
        if mutating and self.zone in str(path):
            return PolicyDecision(allowed=False, reason=f"{self.zone}/ is read-only")
        return PolicyDecision(allowed=True)


class TestCopyPolicyMap:
    def test_anti_exfiltration_copy_out_of_read_denied_zone_is_denied(self, tmp_path):
        pipeline, root, trajectory_path = make_pipeline(
            tmp_path, policy=ReadDeniedUnder("originals")
        )
        originals = root / "originals"
        originals.mkdir()
        (originals / "secret.txt").write_text("x\n")
        with pytest.raises(PolicyDenial, match="read-denied"):
            pipeline.call("copy", src="originals/secret.txt", dest="leaked.txt")
        assert not (root / "leaked.txt").exists()
        entry = last_entry(trajectory_path)
        assert entry["status"] == "denied"
        assert entry["stage"] == "policy"

    def test_copy_out_of_read_only_zone_is_allowed(self, tmp_path):
        # The per-arg policy map fix: cartesian checking would demand
        # mutate-structure on the read-only src and wrongly deny this.
        pipeline, root, _ = make_pipeline(tmp_path, policy=MutateDeniedUnder("reports"))
        reports = root / "reports"
        reports.mkdir()
        (reports / "q1.txt").write_text("numbers\n")
        result = pipeline.call("copy", src="reports/q1.txt", dest="draft.txt")
        assert "copied" in result
        assert (root / "draft.txt").read_text() == "numbers\n"

    def test_copy_into_read_only_zone_is_denied(self, tmp_path):
        pipeline, root, _ = make_pipeline(tmp_path, policy=MutateDeniedUnder("reports"))
        reports = root / "reports"
        reports.mkdir()
        (root / "draft.txt").write_text("x\n")
        with pytest.raises(PolicyDenial, match="read-only"):
            pipeline.call("copy", src="draft.txt", dest="reports/new.txt")


class TestDeleteThroughPipeline:
    def test_delete_stages_below_the_membrane_and_read_tools_are_blind(self, tmp_path):
        root = tmp_path / "sandbox"
        root.mkdir(exist_ok=True)
        pipeline, root, _ = make_pipeline(
            tmp_path, git=GitCommit(root, session_id="s-test")
        )
        pipeline.call("write", path="r.txt", content="precious\n")
        result = pipeline.call("delete", path="r.txt")
        assert "_trash" not in result
        assert not (root / "r.txt").exists()
        assert (root / "_trash" / "r.txt").read_text() == "precious\n"
        # only .git and _trash remain in the sandbox — the model sees neither
        assert pipeline.call("list_dir", path=".") == "(empty folder)"
        assert pipeline.call("glob", pattern="**/*") == "no matches for '**/*'"
        assert pipeline.call("grep", pattern="precious") == "no matches for 'precious'"

    def test_tier_1_content_lives_in_git_history(self, tmp_path):
        root = tmp_path / "sandbox"
        root.mkdir(exist_ok=True)
        pipeline, root, _ = make_pipeline(
            tmp_path, git=GitCommit(root, session_id="s-test")
        )
        pipeline.call("write", path="r.txt", content="precious\n")
        pipeline.call("delete", path="r.txt")
        assert not (root / "r.txt").exists()
        assert commit_count(root) == 2
        recovered = subprocess.run(
            ["git", "show", "HEAD^:r.txt"],
            cwd=root, capture_output=True, text=True, check=True,
        ).stdout
        assert recovered == "precious\n"


class TestYamlPolicyThroughPipeline:
    ARCHIVE = """
default: allow
rules:
  - path: "sandbox/originals/**"
    deny: [mutate-content, mutate-structure]
"""

    def make(self, tmp_path, config):
        from core.policy import YamlPolicy

        root = tmp_path / "sandbox"
        root.mkdir(exist_ok=True)
        return make_pipeline(tmp_path, policy=YamlPolicy(config, root))

    def test_write_into_archive_denied(self, tmp_path):
        pipeline, root, trajectory_path = self.make(tmp_path, self.ARCHIVE)
        (root / "originals").mkdir()
        with pytest.raises(PolicyDenial, match="originals"):
            pipeline.call("write", path="originals/new.txt", content="x\n")
        assert last_entry(trajectory_path)["stage"] == "policy"

    def test_copy_out_of_archive_is_the_standard_recovery(self, tmp_path):
        pipeline, root, _ = self.make(tmp_path, self.ARCHIVE)
        (root / "originals").mkdir()
        (root / "originals" / "data.csv").write_text("a,b\n")
        result = pipeline.call("copy", src="originals/data.csv", dest="work.csv")
        assert "copied" in result
        assert (root / "work.csv").read_text() == "a,b\n"

    def test_inspect_surfaces_effective_permissions(self, tmp_path):
        pipeline, root, _ = self.make(tmp_path, self.ARCHIVE)
        (root / "originals").mkdir()
        (root / "originals" / "doc.txt").write_text("x\n")
        result = json.loads(pipeline.call("inspect", path="originals/doc.txt"))
        assert result["permissions"] == ["read", "search"]

    def test_glob_default_scope_is_policy_checked(self, tmp_path):
        config = """
default: allow
rules:
  - path: "sandbox"
    deny: [search]
  - path: "sandbox/**"
    deny: [search]
"""
        pipeline, root, trajectory_path = self.make(tmp_path, config)
        (root / "a.txt").write_text("x\n")
        with pytest.raises(PolicyDenial, match="search"):
            pipeline.call("glob", pattern="*")
        assert last_entry(trajectory_path)["stage"] == "policy"

    def test_grep_content_mode_requires_read(self, tmp_path):
        config = """
default: allow
rules:
  - path: "sandbox"
    deny: [read]
  - path: "sandbox/**"
    deny: [read]
"""
        pipeline, root, _ = self.make(tmp_path, config)
        (root / "notes.txt").write_text("alpha\n")
        assert pipeline.call("grep", pattern="alpha") == "notes.txt · 1"
        with pytest.raises(PolicyDenial, match="read"):
            pipeline.call("grep", pattern="alpha", mode="content")


class TestLookup:
    def test_unknown_tool_is_shaped_failure(self, tmp_path):
        pipeline, _, _ = make_pipeline(tmp_path)
        with pytest.raises(ToolError, match="unknown tool"):
            pipeline.call("nope", path="a.txt")
