import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALLER = ROOT/"scripts/install_skills.py"

from scripts.install_skills import runtime_status


class InstallerTests(unittest.TestCase):
    def install(self, dest, *flags):
        return subprocess.run([sys.executable, str(INSTALLER), "--target", "directory", "--directory", str(dest), *flags],
                              capture_output=True, text=True)

    def test_dry_run_and_check_do_not_create_directories(self):
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp)/"skills"
            self.assertEqual(self.install(dest, "--dry-run").returncode, 0)
            self.assertFalse(dest.exists())
            self.assertEqual(self.install(dest, "--check").returncode, 0)
            self.assertFalse(dest.exists())

    def test_missing_optional_packages_do_not_trigger_import_failure(self):
        with patch("scripts.install_skills.importlib.util.find_spec", side_effect=ModuleNotFoundError):
            status = runtime_status()
        self.assertFalse(status["network_dependencies"])
        self.assertTrue(status["supported"])
        self.assertEqual(status["interpreter"], sys.executable)

    def test_runtime_reports_unsupported_interpreter(self):
        with patch("scripts.install_skills.sys.version_info", (3, 10, 0)):
            self.assertFalse(runtime_status()["supported"])

    def test_conflict_preflight_refuses_whole_install(self):
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp)/"skills"
            dest.mkdir()
            first = sorted((ROOT/"skills").iterdir())[0].name
            (dest/first).symlink_to("missing-folder", target_is_directory=True)
            self.assertEqual(self.install(dest).returncode, 1)
            self.assertEqual([p.name for p in dest.iterdir()], [first])
            self.assertEqual(os.readlink(dest/first), "missing-folder")

    def test_symlink_install_points_to_canonical_skill(self):
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp)/"skills"
            result = self.install(dest)
            self.assertEqual(result.returncode, 0, result.stderr)
            skill = dest/"play-aso-research"
            self.assertTrue(skill.is_symlink())
            self.assertEqual(skill.resolve(), ROOT/"skills/play-aso-research")

    def test_copy_runs_without_repository_relative_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp)/"skills"
            result = self.install(dest, "--copy")
            self.assertEqual(result.returncode, 0, result.stderr)
            for path in dest.rglob("*"):
                self.assertFalse(path.is_symlink(), str(path))
            cli = dest/"play-aso-research/references/shared/cli.py"
            input_file = Path(temp)/"listing.json"
            input_file.write_text(json.dumps({"en-GB": {"title": "Focus", "shortDescription": "Focus sessions", "fullDescription": "Start a timer."}}))
            result = subprocess.run([sys.executable, str(cli), "validate", str(input_file)], cwd=temp, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(result.stdout)["valid"])
            publisher = dest/"play-metadata/references/shared/play_api.py"
            result = subprocess.run([sys.executable, str(publisher), "apply", "--package", "com.example.focus", "--input", str(input_file)], cwd=temp, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "dry-run")
            ads_example = dest/"google-ads-launch/references/examples/data/google-ads-create.json"
            ads_cli = dest/"google-ads-launch/references/shared/google_ads.py"
            result = subprocess.run([sys.executable, str(ads_cli), "plan", "--customer", "1234567890", "--api-version", "v25", "--config", str(ads_example)], cwd=temp, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "offline-plan")


if __name__ == "__main__":
    unittest.main()
