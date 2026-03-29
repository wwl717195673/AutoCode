import unittest
from pathlib import Path

from autocode.specs import discover_specs


class DiscoverSpecsTest(unittest.TestCase):
    def test_discover_specs_reads_frontmatter(self) -> None:
        with self.subTest("frontmatter"):
            from tempfile import TemporaryDirectory

            with TemporaryDirectory() as temp_dir:
                tmp_path = Path(temp_dir)
                spec_dir = tmp_path / "specs"
                spec_dir.mkdir()
                (spec_dir / "002_second.md").write_text(
                    "---\n"
                    "title: Second\n"
                    "priority: 5\n"
                    "agent: codex\n"
                    "max_rounds: 4\n"
                    "acceptance_checks:\n"
                    "  - pytest -q\n"
                    "---\n"
                    "\n"
                    "Implement second task.\n",
                    encoding="utf-8",
                )
                (spec_dir / "001_first.md").write_text("First task.\n", encoding="utf-8")

                specs = discover_specs(spec_dir)

                self.assertEqual([spec.title for spec in specs], ["Second", "001 first"])
                self.assertEqual(specs[0].acceptance_checks, ["pytest -q"])
                self.assertEqual(specs[0].max_rounds, 4)


if __name__ == "__main__":
    unittest.main()
