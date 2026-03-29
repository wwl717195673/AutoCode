import subprocess
import unittest
from pathlib import Path

from autocode.models import AgentName, AutoConfirmMode, BatchConfig, TaskStatus
from autocode.orchestrator import continue_batch, initialize_batch


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True)


class OrchestratorTest(unittest.TestCase):
    def test_initialize_and_continue_batch_failure_without_agent(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temp_dir:
            tmp_path = Path(temp_dir)
            repo = tmp_path / "repo"
            repo.mkdir()
            _git(repo, "init")
            _git(repo, "config", "user.name", "Test User")
            _git(repo, "config", "user.email", "test@example.com")
            (repo / "README.md").write_text("hello\n", encoding="utf-8")
            _git(repo, "add", "README.md")
            _git(repo, "commit", "-m", "init")

            spec_dir = tmp_path / "specs"
            spec_dir.mkdir()
            (spec_dir / "task.md").write_text("Implement the task.\n", encoding="utf-8")

            config = BatchConfig(
                repo=repo,
                spec_dir=spec_dir,
                agent=AgentName.CODEX,
                default_checks=[],
                max_rounds=1,
                continue_on_failure=True,
                auto_confirm_mode=AutoConfirmMode.SAFE,
            )

            state = initialize_batch(config)
            finished = continue_batch(config, state.batch_id)

            self.assertEqual(len(finished.tasks), 1)
            self.assertEqual(finished.tasks[0].status, TaskStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
