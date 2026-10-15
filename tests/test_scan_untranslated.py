from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "scan_untranslated", ROOT / "scripts" / "scan_untranslated.py"
)
assert SPEC is not None and SPEC.loader is not None
scan_untranslated = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scan_untranslated)


class ScanUntranslatedTests(unittest.TestCase):
    def test_audit_skills_detects_covered_and_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            manifest_file = temp_path / "skill-translations.json"
            skills_dir = temp_path / "skills"
            skills_dir.mkdir(parents=True)

            (skills_dir / "known-skill").mkdir()
            (skills_dir / "known-skill" / "SKILL.md").write_text("description: test")
            (skills_dir / "new-skill").mkdir()
            (skills_dir / "new-skill" / "SKILL.md").write_text("description: new")

            manifest_file.write_text(
                json.dumps(
                    {
                        "patches": [
                            {
                                "path": "skills/known-skill/SKILL.md",
                                "context": "/known-skill 右侧说明",
                            }
                        ]
                    }
                )
            )

            result = scan_untranslated.audit_skills(manifest_file, skills_dir)
            self.assertEqual(len(result["covered"]), 1)
            self.assertEqual(len(result["missing"]), 1)
            self.assertEqual(result["missing"][0]["skill_name"], "new-skill")

    def test_current_repo_has_zero_missing_commands(self) -> None:
        binary_path = scan_untranslated.locate_pristine_binary()
        if not binary_path.exists():
            self.skipTest(f"Binary not found: {binary_path}")

        audit = scan_untranslated.run_audit(
            binary_path=binary_path,
            binary_manifest_path=ROOT / "i18n" / "binary-translations.json",
            skill_manifest_path=ROOT / "i18n" / "skill-translations.json",
            skills_dir=scan_untranslated.SKILL_DIR,
        )

        self.assertGreater(audit["summary"]["commands_total"], 30)
        self.assertEqual(
            audit["summary"]["commands_missing"],
            0,
            f"Found untranslated commands: {audit['commands']['missing']}",
        )
        self.assertEqual(
            audit["summary"]["skills_missing"],
            0,
            f"Found untranslated skills: {audit['skills']['missing']}",
        )


if __name__ == "__main__":
    unittest.main()
