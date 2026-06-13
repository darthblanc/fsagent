import subprocess

from core.gitstage import GitCommit
from tools.write import DEFINITION as WRITE_DEFINITION


def git(*args, cwd):
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout


class TestGitCommit:
    def test_first_commit_initializes_repo_and_tags_message(self, tmp_path):
        (tmp_path / "a.txt").write_text("x\n")
        GitCommit(tmp_path, session_id="s-1").commit(WRITE_DEFINITION, request_id=3)
        assert (tmp_path / ".git").is_dir()
        assert git("log", "-1", "--format=%s", cwd=tmp_path).strip() == (
            "write [session=s-1 request=3]"
        )
        assert "a.txt" in git("ls-files", cwd=tmp_path)

    def test_commits_accumulate_per_request(self, tmp_path):
        stage = GitCommit(tmp_path, session_id="s-1")
        (tmp_path / "a.txt").write_text("x\n")
        stage.commit(WRITE_DEFINITION, request_id=1)
        (tmp_path / "a.txt").write_text("y\n")
        stage.commit(WRITE_DEFINITION, request_id=2)
        assert git("rev-list", "--count", "HEAD", cwd=tmp_path).strip() == "2"

    def test_oversized_files_are_excluded_by_size_policy(self, tmp_path):
        (tmp_path / "big.bin").write_bytes(b"x" * 100)
        (tmp_path / "small.txt").write_text("x\n")
        GitCommit(tmp_path, session_id="s-1", tier_threshold=50).commit(
            WRITE_DEFINITION, request_id=1
        )
        tracked = git("ls-files", cwd=tmp_path)
        assert "small.txt" in tracked
        assert "big.bin" not in tracked
        assert "big.bin" in (tmp_path / ".git" / "info" / "exclude").read_text()
