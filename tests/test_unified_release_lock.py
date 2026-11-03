"""Pinned, mixed-format assets cannot silently drift between refreshes."""
import json
from pathlib import Path
import re
import unittest

from scripts import unified_policy

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "policy/unified-v1.json"
LOCK = ROOT / "policy/unified-release-lock.json"


class UnifiedDeliveryLock(unittest.TestCase):
    def setUp(self):
        self.policy = unified_policy.load_policy(POLICY)

    def test_loads_checked_immutable_release_lock(self):
        lock = unified_policy.load_release_lock(LOCK, self.policy)
        self.assertEqual(lock["schema_version"], 1)
        self.assertEqual(lock["repository"], "togahimoko/garasu")
        self.assertEqual(set(lock["categories"]),
                         {x["category"] for x in self.policy["priority"]})
        for source in lock["sources"].values():
            self.assertRegex(source["revision"], r"^[a-f0-9]{40}$")
            self.assertNotIn(source["revision"], ("main", "master"))

    def test_all_download_urls_are_content_addressed_and_consistent(self):
        lock = unified_policy.load_release_lock(LOCK, self.policy)
        expected = {}
        for item in self.policy["priority"]:
            cat = item["category"]
            expected[cat] = {
                engine: unified_policy.asset_url(lock, cat, engine)
                for engine in ("mihomo", "singbox", "shadowrocket")
            }
        outputs = unified_policy.build_candidates(ROOT, self.policy)
        yaml_text = outputs["clients/unified/mihomo-remnawave.yaml"]
        stash_text = outputs["clients/unified/stash-remnawave.yaml"]
        sb = json.loads(outputs["clients/unified/singbox-remnawave-1.14.json"])
        shadow = outputs["clients/unified/shadowrocket.conf"]
        for cat, urls in expected.items():
            with self.subTest(cat=cat):
                self.assertIn(urls["mihomo"], yaml_text)
                self.assertIn(urls["mihomo"], stash_text)
                self.assertIn(urls["shadowrocket"], shadow)
                sb_source = next(x for x in sb["route"]["rule_set"]
                                 if x["tag"] == "garasu-" + cat)
                self.assertEqual(sb_source["url"], urls["singbox"])
                for url in urls.values():
                    self.assertRegex(url,
                        r"^https://raw[.]githubusercontent[.]com/togahimoko/garasu/[a-f0-9]{40}/rules/")
                    self.assertNotIn("/main/", url)
                    self.assertNotIn("/feature/", url)

    def test_integrity_verifies_actual_bytes_and_detects_tampering(self):
        from tempfile import TemporaryDirectory
        import hashlib
        category = "rules/ai.list"
        original = b"+.example.org\\n"
        blob = (b"blob " + str(len(original)).encode("ascii") +
                b"\\x00" + original)
        lock = {"assets": {category: {
            "source": "base", "git_blob": hashlib.sha1(blob).hexdigest(),
            "bytes": len(original)}}}
        with TemporaryDirectory() as folder:
            relative = Path(folder) / category
            relative.parent.mkdir(parents=True)
            relative.write_bytes(original)
            self.assertEqual(
                unified_policy.verify_release_assets(folder, lock, paths=[category]), 1
            )
            relative.write_bytes(original + b"tampering")
            with self.assertRaisesRegex(ValueError, "integrity"):
                unified_policy.verify_release_assets(folder, lock, paths=[category])

    def test_integrity_rejects_missing_files_and_unknown_inventory(self):
        from tempfile import TemporaryDirectory
        lock = unified_policy.load_release_lock(LOCK, self.policy)
        with TemporaryDirectory() as folder:
            with self.assertRaises((FileNotFoundError, ValueError)):
                unified_policy.verify_release_assets(
                    folder, lock, paths=["rules/ai.list"])
            with self.assertRaises(ValueError):
                unified_policy.verify_release_assets(
                    folder, lock, paths=["../private-token"])

    def test_rejects_modified_or_incomplete_lock(self):
        lock = json.loads(LOCK.read_text(encoding="utf-8"))
        broken = json.loads(json.dumps(lock))
        del broken["categories"]["ads"]
        with self.assertRaises(ValueError):
            unified_policy.validate_release_lock(broken, self.policy)
        broken = json.loads(json.dumps(lock))
        broken["sources"]["base"]["revision"] = "main"
        with self.assertRaises(ValueError):
            unified_policy.validate_release_lock(broken, self.policy)
        broken = json.loads(json.dumps(lock))
        broken["categories"]["youtube"]["mihomo"] = "clients/../secrets.txt"
        with self.assertRaises(ValueError):
            unified_policy.validate_release_lock(broken, self.policy)


if __name__ == "__main__":
    unittest.main()
