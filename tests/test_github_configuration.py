"""GitHub repository conventions: issue forms, binary assets and no Actions."""
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]


class GitHubConfigurationTests(unittest.TestCase):
    def test_no_automated_workflows(self):
        directory = ROOT / ".github" / "workflows"
        self.assertFalse(list(directory.glob("*.yml")))
        self.assertFalse(list(directory.glob("*.yaml")))

    def test_issues_are_redacted_and_structured(self):
        path = ROOT / ".github" / "ISSUE_TEMPLATE"
        for file in ("bug_report.yml", "feature_request.yml"):
            with self.subTest(file=file):
                template = yaml.safe_load((path / file).read_text(encoding="utf-8"))
                self.assertTrue(template["name"])
                self.assertGreaterEqual(len(template["body"]), 3)
                self.assertTrue(any(
                    field.get("validations", {}).get("required")
                    for field in template["body"]
                ))
        text = (path / "bug_report.yml").read_text(encoding="utf-8").lower()
        self.assertIn("uuid", text)
        self.assertIn("токен", text)

    def test_compiled_assets_are_binary_in_git(self):
        attr = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        for line in ("*.mrs binary", "*.dat binary"):
            self.assertIn(line, attr)
        self.assertTrue((ROOT / ".github/PULL_REQUEST_TEMPLATE.md").is_file())

    def test_release_docs_and_security_disclosure_exist(self):
        for path in ("SECURITY.md", "CONTRIBUTING.md",
                     "docs/release-checklist.md", ".editorconfig"):
            self.assertTrue((ROOT / path).is_file(), path)


if __name__ == "__main__":
    unittest.main()
