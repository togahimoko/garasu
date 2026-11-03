"""The complete blocked snapshot must reach every published client format."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import refresh


def varint(value):
    output = bytearray()
    while value >= 128:
        output.append((value & 127) | 128)
        value >>= 7
    return bytes(output + bytes([value]))


def field(number, value):
    return varint(number * 8 + 2) + varint(len(value)) + value


def category(name, items):
    return field(1, field(1, name.encode()) + b"".join(field(2, item) for item in items))


class FullSourceBuilderTests(unittest.TestCase):
    def test_direct_script_import_resolves_policy_contract(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, "-c", "import sys; sys.path = ['scripts'] + sys.path[1:]; import refresh"],
            cwd=root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_complete_sources_are_selected_and_require_large_inputs(self):
        self.assertEqual(refresh.DOMAIN["rkn-domains"][0],
                         "release/refilter-domain-full.list")
        self.assertGreaterEqual(refresh.DOMAIN["rkn-domains"][1], 70000)
        self.assertEqual(refresh.IP["rkn-ips"][0], "release/refilter-ip-full.list")
        self.assertGreaterEqual(refresh.IP["rkn-ips"][1], 20000)

    def test_git_ref_lookup_accepts_only_main_commit_sha(self):
        sha = "a" * 40
        self.assertEqual(refresh.parse_git_revision((sha + "\trefs/heads/main\n").encode()), sha)
        for response in (b"", b"main\trefs/heads/main\n",
                         (sha + "\trefs/heads/other\n").encode(),
                         (sha + "\trefs/heads/main\n" + sha + "\trefs/heads/main\n").encode()):
            with self.subTest(response=response), self.assertRaises(ValueError):
                refresh.parse_git_revision(response)

    def test_one_time_full_source_migration_keeps_future_churn_gate(self):
        old = {"files": {"rules/rkn-domains.list": {
            "entries": 10000, "source": "https://raw.githubusercontent.com/DigneZzZ/routing/"
            + "a" * 40 + "/release/refilter-domain.list"}}}
        new = {"rules/rkn-domains.list": {"entries": 75306,
               "source": "https://raw.githubusercontent.com/DigneZzZ/routing/"
               + "b" * 40 + "/release/refilter-domain-full.list"}}
        refresh.validate_update_budget(new, old)
        old["files"]["rules/singbox/rkn-domains.json"] = {
            "entries": 10000, "source": "https://raw.githubusercontent.com/DigneZzZ/routing/"
            + "a" * 40 + "/release/refilter-domain.list"}
        new["rules/singbox/rkn-domains.json"] = {
            "entries": 75306, "source": "https://raw.githubusercontent.com/DigneZzZ/routing/"
            + "b" * 40 + "/release/refilter-domain-full.list"}
        refresh.validate_update_budget(new, old)
        new["rules/rkn-domains.list"]["source"] = (
            "https://raw.githubusercontent.com/DigneZzZ/routing/" + "c" * 40
            + "/release/refilter-domain-full.list")
        old["files"]["rules/rkn-domains.list"] = {
            "entries": 75306, "source": "https://raw.githubusercontent.com/DigneZzZ/routing/"
            + "b" * 40 + "/release/refilter-domain-full.list"}
        new["rules/rkn-domains.list"]["entries"] = 10000
        with self.assertRaisesRegex(ValueError, "Source drift"):
            refresh.validate_update_budget(new, old)

    def test_geodata_replacement_is_deterministic_and_preserves_other_categories(self):
        original = category("OTHER", [b"untouched"]) + category("BANNED-RU", [b"old"])
        canonical = b"# provenance\n+.blocked.example\n+.blocked.ru\n"
        first = refresh.replace_geodata_category("geosite.dat", original,
                                                 "banned-ru", canonical)
        second = refresh.replace_geodata_category("geosite.dat", original,
                                                  "banned-ru", canonical)
        self.assertEqual(first, second)
        entries = [list(refresh._protobuf_fields(payload))
                   for number, payload in refresh._protobuf_fields(first) if number == 1]
        by_name = {next(value.decode() for number, value in item if number == 1):
                   [value for number, value in item if number == 2] for item in entries}
        self.assertEqual(by_name["OTHER"], [b"untouched"])
        domains = [dict(refresh._protobuf_fields(item)) for item in by_name["BANNED-RU"]]
        self.assertEqual([item[2] for item in domains],
                         [b"blocked.example", b"blocked.ru"])

    def test_ip_geodata_replacement_contains_the_same_networks(self):
        original = category("BLOCKED-RU", [b"old"])
        canonical = b"# provenance\n1.2.3.0/24\n2001:db8::/32\n"
        result = refresh.replace_geodata_category("geoip.dat", original,
                                                  "blocked-ru", canonical)
        entry = next(payload for number, payload in refresh._protobuf_fields(result)
                     if number == 1)
        cidrs = [payload for number, payload in refresh._protobuf_fields(entry)
                 if number == 2]
        self.assertEqual(cidrs,
                         [field(1, b"\x01\x02\x03\x00") + b"\x10\x18",
                          field(1, bytes.fromhex("20010db8000000000000000000000000"))
                          + b"\x10\x20"])

    def test_invalid_source_leaves_last_published_snapshot_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "rules").mkdir()
            target = root / "rules/ads.list"
            target.write_bytes(b"# previous valid snapshot\n+.example.com\n")
            with patch.object(refresh, "ROOT", root), \
                 patch.object(refresh, "DOMAIN", {"ads": ("release/reject.list", 1),
                                                 "ai": ("release/ai.list", 1)}), \
                 patch.object(refresh, "resolve_upstream_revision", return_value="a" * 40), \
                 patch.object(refresh, "fetch", side_effect=[b"+.example.com\n",
                                                            ValueError("invalid full source")]):
                with self.assertRaisesRegex(ValueError, "invalid full source"):
                    refresh.run()
            self.assertEqual(target.read_bytes(), b"# previous valid snapshot\n+.example.com\n")

    def test_published_snapshot_manifest_matches_all_blocked_formats(self):
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / "install/manifest.json").read_text())
        sources = manifest["sources"]
        self.assertEqual(set(sources), {"blocked_domains", "blocked_ips"})
        self.assertEqual(sources["blocked_domains"]["entries"],
                         sum(line.startswith(b"+.") for line in
                             (root / "rules/rkn-domains.list").read_bytes().splitlines()))
        self.assertEqual(sources["blocked_ips"]["entries"],
                         sum(line and not line.startswith(b"#") for line in
                             (root / "rules/rkn-ips.cidr").read_bytes().splitlines()))
        for path in ("rules/rkn-domains.list", "rules/singbox/rkn-domains.json",
                     "rules/surge/rkn-domains.list", "rules/quantumultx/rkn-domains.list",
                     "rules/rkn-ips.cidr", "rules/singbox/rkn-ips.json",
                     "rules/surge/rkn-ips.list", "rules/quantumultx/rkn-ips.list"):
            record = manifest["files"][path]
            self.assertEqual(record["entries"], sources[
                "blocked_domains" if "domains" in path else "blocked_ips"]["entries"])
            self.assertEqual(record["sha256"], hashlib.sha256((root / path).read_bytes()).hexdigest())
        self.assertEqual(refresh.validate_geodata("geosite.dat", (root / "geo/geosite.dat").read_bytes())[
            "banned-ru"], sources["blocked_domains"]["entries"])
        self.assertEqual(refresh.validate_geodata("geoip.dat", (root / "geo/geoip.dat").read_bytes())[
            "blocked-ru"], sources["blocked_ips"]["entries"])


if __name__ == "__main__":
    unittest.main()
