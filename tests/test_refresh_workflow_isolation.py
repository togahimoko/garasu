"""Regression coverage for normal scheduled source refresh and immutable snapshots.

In the refresh workflow, pinned-release tests must pass BEFORE the rolling
upstream refresh. AFTER refresh they are tested separately in dedicated CI.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RefreshWorkflowIsolation(unittest.TestCase):
    def test_pinned_tests_verified_before_refresh_and_never_after_without_isolation(self):
        workflow = (ROOT / ".github/workflows/refresh.yml").read_text(encoding="utf-8")
        self.assertLess(workflow.index("Check static profiles and builder"),
                        workflow.index("Download and validate full routing datasets"))
        # The clean checkout runs the entire suite, including locked assets.
        initial = workflow.split("Download and validate full routing datasets")[0]
        self.assertIn("python -m unittest discover -s tests -v", initial)
        post = workflow.split("      - name: Verify generated output", 1)[1]
        self.assertIn("GARASU_ALLOW_REFRESHED_CANDIDATE_SKIP: '1'", post)
        self.assertIn("python -m unittest discover -s tests -v", post)
        self.assertIn("python scripts/audit_rules.py --root . --check", post)
        self.assertLess(workflow.index("Verify generated output"),
                        workflow.index("Publish only complete validated build"))

    def test_do_not_disable_unified_release_gates(self):
        workflow = (ROOT / ".github/workflows/unified-candidate.yml").read_text()
        self.assertNotIn("GARASU_ALLOW_REFRESHED_CANDIDATE_SKIP", workflow)
        self.assertIn("scripts/unified_policy.py --verify-assets", workflow)
        self.assertIn("Real Mihomo 1.19.32 parses embedded full-blocker", workflow)


if __name__ == "__main__":
    unittest.main()
