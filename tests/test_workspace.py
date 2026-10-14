"""Local artifact safety: do not lose source files or publish partial workspaces."""
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from shared.cli import create_workspace, main, protect_inputs
from scripts.install_skills import main as install


class WorkspaceTests(unittest.TestCase):
    def test_output_cannot_overwrite_source_or_its_aliases(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp)/"listings.json"
            original = json.dumps({"en-US": {"title": "Habits", "shortDescription": "Daily habits", "fullDescription": "Track a daily checklist."}})
            source.write_text(original)
            symlink = Path(temp)/"symlink.json"; symlink.symlink_to(source)
            hardlink = Path(temp)/"hardlink.json"; os.link(source, hardlink)
            for target in (source, symlink, hardlink):
                with self.subTest(target=target), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(main(["validate", str(source), "--output", str(target)]), 2)
                    self.assertEqual(source.read_text(), original)
            with self.assertRaises(ValueError):
                protect_inputs(source, [Path(temp)/"other.csv", symlink])

    def test_failed_workspace_creation_leaves_no_partial_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)/"app"
            with patch("shared.cli.write_json", side_effect=OSError("disk unavailable")):
                with self.assertRaises(OSError): create_workspace(target, "com.example.app")
            self.assertFalse(target.exists())
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_dangling_link_destination_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)/"app"; target.symlink_to("unavailable", target_is_directory=True)
            with self.assertRaises(ValueError): create_workspace(target, "com.example.app")
            self.assertTrue(target.is_symlink())
            self.assertEqual(os.readlink(target), "unavailable")

    def test_portable_install_omits_runtime_packages_but_keeps_generator_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)/"repo"; generator = root/"examples/generator"; generator.mkdir(parents=True)
            (generator/"engine.js").write_text("fixture engine")
            dependencies = generator/"node_modules/large-package"; dependencies.mkdir(parents=True)
            (dependencies/"runtime.bin").write_text("not a skill asset")
            skill = root/"skills/fixture-skill"; (skill/"references").mkdir(parents=True)
            (skill/"SKILL.md").write_text("fixture skill")
            (skill/"references/generator").symlink_to(generator, target_is_directory=True)
            dest = Path(temp)/"installed"
            with patch("scripts.install_skills.ROOT", root), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(install(["--target", "directory", "--directory", str(dest), "--copy"]), 0)
            copy = dest/"fixture-skill/references/generator"
            self.assertEqual((copy/"engine.js").read_text(), "fixture engine")
            self.assertFalse((copy/"node_modules").exists())


if __name__ == "__main__":
    unittest.main()
