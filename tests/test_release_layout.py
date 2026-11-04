"""Release directory invariants: one stable path, no dated folders.

This is a static, credential-free test; no VPS or subscription changes.
Run: python3 -m unittest tests.test_release_layout
"""
from pathlib import Path
import hashlib
import json
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "release"
MRS = RELEASE / "mihomo" / ".mrs"
CATEGORIES = (
    "rkn-domains", "youtube", "discord", "ai", "crypto", "proxy", "ads",
    "games", "direct", "rkn-ips", "proxy-ips", "direct-ips", "ru-ips"
)


def load_yaml(rel):
    return yaml.safe_load((RELEASE / rel).read_text(encoding="utf-8"))


class ReleaseLayoutTest(unittest.TestCase):
    def test_one_stable_structure_no_dated_subtrees(self):
        expected = {
            "mihomo/config.yaml", "mihomo/build.py",
            "mihomo/.mrs/README.md", "mihomo/.mrs/manifest.json",
            "stash/config.yaml", "incy/config.json", "happ/config.json",
            "shadowrocket/config.conf", "singbox/config.json", "xray/config.json",
            "README.md", "remnawave/srr.json", "remnawave/README.md",
        }
        providers = ("ads", "rkn-domains", "rkn-ips", "proxy-ips", "ru-ips",
                     "youtube", "discord", "ai", "crypto", "proxy")
        expected.update("providers/" + name + ".txt" for name in providers)
        expected.update("singbox/rules/" + name + ".json" for name in providers)
        actual = {p.relative_to(RELEASE).as_posix()
                  for p in RELEASE.rglob("*") if p.is_file()}
        self.assertEqual(actual, expected | {
            "mihomo/.mrs/" + name + ".mrs" for name in CATEGORIES
        })
        self.assertFalse(any("one-control" in p or "2026" in p for p in actual))

    def test_native_mrs_blobs_match_manifest_and_template_urls(self):
        manifest = json.loads((MRS / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual({x["name"] for x in manifest["files"]}, set(CATEGORIES))
        for name in CATEGORIES:
            item = next(x for x in manifest["files"] if x["name"] == name)
            blob = (MRS / (name + ".mrs")).read_bytes()
            self.assertEqual(len(blob), item["mrs_bytes"])
            self.assertEqual(hashlib.sha256(blob).hexdigest(), item["sha256"])
        for client in ("mihomo","stash"):
            data = load_yaml(client + "/config.yaml")
            providers = data["rule-providers"]
            self.assertEqual(len(providers), 10)
            self.assertTrue(all(p["format"] == "text" and p["url"].startswith(
                "https://raw.githubusercontent.com/togahimoko/garasu/main/release/providers/")
                and "payload" not in p for p in providers.values()))

    def test_mihomo_only_one_visible_policy(self):
        text = (RELEASE / "mihomo/config.yaml").read_text(encoding="utf-8")
        data = load_yaml("mihomo/config.yaml")
        self.assertEqual(text.count("proxies: # LEAVE THIS LINE!"), 3)
        self.assertIsNone(data["proxies"])
        self.assertEqual([g["name"] for g in data["proxy-groups"]
                          if not g.get("hidden")], ["Garasu"])
        self.assertEqual(len(data["proxy-groups"]), 2)
        self.assertEqual(data["proxy-groups"][0]["type"], "select")
        self.assertEqual(data["proxy-groups"][0]["default-selected"], "Garasu Auto")
        self.assertEqual(data["proxy-groups"][0]["proxies"], ["Garasu Auto"])
        self.assertNotIn("remnawave", data["proxy-groups"][0])
        self.assertEqual(data["proxy-groups"][1]["type"], "url-test")
        self.assertTrue(data["proxy-groups"][1]["hidden"])
        self.assertEqual(data["proxy-groups"][1]["empty-fallback"], "REJECT")
        self.assertEqual(data["rules"][-1], "MATCH,Garasu")
        self.assertNotIn("tun", data)
        self.assertTrue(all(p["type"] == "http"
                            for p in data["rule-providers"].values()))
        self.assertIn("DOMAIN-SUFFIX,ru,DIRECT", data["rules"])
        self.assertIn("RULE-SET,rkn-domains,Garasu", data["rules"])
        self.assertIn("DOMAIN-SUFFIX,sberbank.ru,DIRECT", data["rules"])

    def test_stash_and_native_client_exports(self):
        stash = load_yaml("stash/config.yaml")
        self.assertEqual(stash["proxy-groups"][0]["name"], "Garasu")
        self.assertEqual(stash["proxy-groups"][0]["proxies"], ["REJECT"])
        incy = json.loads((RELEASE / "incy/config.json").read_text(encoding="utf-8"))
        happ = json.loads((RELEASE / "happ/config.json").read_text(encoding="utf-8"))
        self.assertEqual(incy, happ)
        self.assertEqual(incy["Name"], "Garasu")
        sh = (RELEASE / "shadowrocket/config.conf").read_text(encoding="utf-8")
        self.assertIn("/main/release/shadowrocket/config.conf", sh)
        self.assertIn("FINAL,PROXY", sh)
        sb = json.loads((RELEASE / "singbox/config.json").read_text(encoding="utf-8"))
        self.assertEqual(sb["route"]["final"], "→ Remnawave")
        self.assertEqual(next(o for o in sb["outbounds"]
                              if o["tag"] == "→ Remnawave")["type"], "urltest")
        xr = json.loads((RELEASE / "xray/config.json").read_text(encoding="utf-8"))
        self.assertTrue(xr["remnawave"]["addVirtualHostAsOutbound"])


if __name__ == "__main__":
    unittest.main()
