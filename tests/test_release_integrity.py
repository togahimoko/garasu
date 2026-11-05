"""Offline release invariants and regression tests for the quality gate."""
from pathlib import Path
import tempfile
import unittest

from scripts.verify_release import (
    ReleaseError, require, verify, verify_manifest, verify_mrs, verify_contract,
)

ROOT = Path(__file__).resolve().parents[1]


class ReleaseIntegrityTests(unittest.TestCase):
    def test_checkout_is_complete(self):
        result = verify(ROOT, branch="main")
        self.assertGreaterEqual(result["binary_mrs"], 35)
        self.assertGreaterEqual(result["manifest_assets"], 50)
        self.assertGreater(result["checked_links"], 40)

    def test_tampered_binary_is_detected(self):
        import shutil
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            shutil.copytree(ROOT / "release/mihomo/.mrs",
                            tmp / "release/mihomo/.mrs")
            (tmp / "rules").mkdir(parents=True)
            for source in (ROOT / "rules").glob("*.list"):
                shutil.copy2(source, tmp / "rules" / source.name)
            for source in (ROOT / "rules").glob("*.cidr"):
                shutil.copy2(source, tmp / "rules" / source.name)
            shutil.copytree(ROOT / "release/providers", tmp / "release/providers")
            shutil.copytree(ROOT / "policy", tmp / "policy")
            shutil.copytree(ROOT / "rules/extra", tmp / "rules/extra")
            with (tmp / "release/mihomo/.mrs/youtube.mrs").open("ab") as f:
                f.write(b"corrupted")
            with self.assertRaisesRegex(ReleaseError, "integrity mismatch"):
                verify_mrs(tmp)

    def test_missing_manifest_asset_is_detected(self):
        import shutil
        with tempfile.TemporaryDirectory() as name:
            tmp = Path(name)
            (tmp / "install").mkdir()
            shutil.copy2(ROOT / "install/manifest.json", tmp / "install/manifest.json")
            shutil.copy2(ROOT / "install/links.json", tmp / "install/links.json")
            with self.assertRaisesRegex(ReleaseError, "Missing or unsafe"):
                verify_manifest(tmp)

    def test_xray_json_requires_explicit_agent_and_known_template(self):
        import json
        import re
        srr = json.loads((ROOT / "release/remnawave/srr.json").read_text())
        matching = [r for r in srr["rules"]
                    if r["responseType"] == "XRAY_JSON" and r["enabled"]]
        self.assertEqual(len(matching), 1)
        rule = matching[0]
        self.assertEqual(rule["responseModifications"]["subscriptionTemplate"], "Default")
        self.assertTrue(rule["responseModifications"]["ignoreHostXrayJsonTemplate"])
        self.assertEqual(len(rule["conditions"]), 1)
        expr = rule["conditions"][0]["value"]
        self.assertIsNotNone(re.search(expr, "garasu-xray-json/1.0", re.I))
        self.assertIsNone(re.search(expr, "v2rayN/7.0", re.I))
        self.assertIsNone(re.search(expr, "happ/1.0", re.I))

    def test_rejects_invalid_release_branch(self):
        with self.assertRaisesRegex(ReleaseError, "main or dev"):
            verify(ROOT, branch="staging")


if __name__ == "__main__":
    unittest.main()
