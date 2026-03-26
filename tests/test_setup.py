import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import setup


class InstruxTests(unittest.TestCase):
    def test_split_sectioned_block_supports_agent_sections(self):
        sections = setup.split_sectioned_block(
            """
[shared]
shared rules

[claude]
claude rules

[agents]
codex rules
""".strip()
        )

        self.assertEqual(sections["shared"], "shared rules")
        self.assertEqual(sections["claude"], "claude rules")
        self.assertEqual(sections["codex"], "codex rules")

    def test_init_and_remove_render_agent_specific_blocks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            target = temp_path / "project"
            target.mkdir()

            blocks_dir = temp_path / "blocks"
            blocks_dir.mkdir()
            (blocks_dir / "agent-rules.txt").write_text(
                """
[shared]
Shared guidance

[claude]
Claude guidance

[codex]
Codex guidance
""".strip()
                + "\n"
            )

            with patch.object(setup, "BLOCKS_DIR", blocks_dir), patch.object(
                setup, "DEFAULT_BLOCKS", []
            ), patch.object(setup, "update_global_gitignore"):
                setup.cmd_init(
                    Namespace(target=str(target), extra_blocks=["agent-rules"])
                )

                self.assertIn(
                    "Shared guidance", (target / "instructions.md").read_text()
                )
                self.assertIn("Claude guidance", (target / "CLAUDE.md").read_text())
                self.assertIn("Codex guidance", (target / "AGENTS.md").read_text())

                setup.cmd_remove(Namespace(target=str(target), block="agent-rules"))

                self.assertNotIn(
                    "agent-rules", (target / "instructions.md").read_text()
                )
                self.assertNotIn("agent-rules", (target / "CLAUDE.md").read_text())
                self.assertNotIn("agent-rules", (target / "AGENTS.md").read_text())


if __name__ == "__main__":
    unittest.main()
