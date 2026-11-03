"""RU-only direct candidate must embed full immutable blocker lists."""
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import patch
import yaml
from scripts import unified_policy

ROOT = Path(__file__).resolve().parents[1]


class VerifiedInlineRussianTLD(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The legacy data/core CI workflows refresh moving upstream files
        # before running the shared tests. This immutable candidate is tested
        # on the clean snapshot by the unified-candidate workflow.
        policy = unified_policy.load_policy(ROOT / "policy/unified-v1.json")
        lock = unified_policy.load_release_lock(
            ROOT / "policy/unified-release-lock.json", policy)
        from scripts import verify_unified_git_objects
        try:
            verify_unified_git_objects.verify_history(ROOT, lock)
        except ValueError:
            if os.environ.get("GARASU_ALLOW_REFRESHED_CANDIDATE_SKIP") == "1":
                raise unittest.SkipTest("moving data refresh; clean snapshot "
                                        "validated by unified-candidate workflow")
            raise

    def setUp(self):
        self.policy = unified_policy.load_policy(ROOT / "policy/unified-v1.json")

    def test_full_blocked_registry_embedded_before_russian_suffix_direct(self):
        result = unified_policy.build_ru_tld_mihomo_candidate(ROOT, self.policy)
        self.assertIn("proxies: # LEAVE THIS LINE!", result)
        config = yaml.safe_load(result)
        full_domain = config["rule-providers"]["rkn-domains-full"]
        full_ip = config["rule-providers"]["rkn-ips-full"]
        self.assertEqual(full_domain["type"], "inline")
        self.assertEqual(full_ip["type"], "inline")
        self.assertEqual(full_domain["behavior"], "domain")
        self.assertEqual(full_ip["behavior"], "ipcidr")
        self.assertEqual(len(full_domain["payload"]), 75306)
        self.assertEqual(len(full_ip["payload"]), 25391)
        self.assertNotIn("url", full_domain)
        self.assertNotIn("url", full_ip)
        rules = config["rules"]
        self.assertLess(rules.index("RULE-SET,rkn-domains-full,Garasu"),
                        rules.index("DOMAIN-SUFFIX,ru,DIRECT"))
        self.assertLess(rules.index("RULE-SET,rkn-ips-full,Garasu"),
                        rules.index("DOMAIN-SUFFIX,ru,DIRECT"))
        self.assertNotIn("RULE-SET,rkn-ips-full,Garasu,no-resolve", rules)
        self.assertNotIn("RULE-SET,ru-ips,DIRECT,no-resolve", rules)
        self.assertEqual(rules[-1], "MATCH,Garasu")
        self.assertNotIn("DOMAIN-SUFFIX,com,DIRECT", rules)
        self.assertNotIn("RULE-SET,games,DIRECT", rules)
        self.assertNotIn("DIRECT", config["proxy-groups"][0]["proxies"])

    def test_refuses_to_generate_if_any_pinned_asset_is_unverified(self):
        from scripts import verify_unified_git_objects
        with patch.object(verify_unified_git_objects, "verify_history",
                          side_effect=ValueError("integrity")):
            with self.assertRaisesRegex(ValueError, "integrity"):
                unified_policy.build_ru_tld_mihomo_candidate(ROOT, self.policy)

    def test_installs_verified_mihomo_candidate_into_offline_zip_only(self):
        from scripts import package_unified_release
        with tempfile.TemporaryDirectory() as directory:
            entries, _ = package_unified_release._source_entries(ROOT)
            self.assertIn("clients/unified/mihomo-ru-tld-verified.yaml", entries)
            text = entries["clients/unified/mihomo-ru-tld-verified.yaml"].decode()
            self.assertIn("type: inline", text)
            self.assertEqual(text.count("proxies: # LEAVE THIS LINE!"), 2)


if __name__ == "__main__":
    unittest.main()
