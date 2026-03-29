import unittest
from pathlib import Path

from autocode.models import AgentName, BatchRunState, TaskRunState, utc_now
from autocode.state import load_batch_state, save_batch_state


class BatchStateTest(unittest.TestCase):
    def test_save_and_load_batch_state(self) -> None:
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temp_dir:
            tmp_path = Path(temp_dir)
            state = BatchRunState(
                batch_id="batch123",
                created_at=utc_now(),
                updated_at=utc_now(),
                repo=str(tmp_path),
                spec_dir=str(tmp_path / "specs"),
                config={"agent": "codex"},
                tasks=[
                    TaskRunState(
                        task_id="task-001",
                        title="Example",
                        spec_path="specs/example.md",
                        branch_name="autocode/test/task-001",
                        worktree_path=str(tmp_path / "wt"),
                        agent=AgentName.CODEX,
                    )
                ],
            )

            save_batch_state(tmp_path, ".autocode/runs", state)
            loaded = load_batch_state(tmp_path, ".autocode/runs", "batch123")

            self.assertEqual(loaded.batch_id, "batch123")
            self.assertEqual(loaded.tasks[0].title, "Example")


if __name__ == "__main__":
    unittest.main()
