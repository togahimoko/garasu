"""Offline release must fail closed and never mutate active Remnawave templates."""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import zipfile

from scripts import package_unified_release as release

ROOT = Path(__file__).resolve().parents[1]


class ImmutableUnifiedBundle(unittest.TestCase):
    def test_complete_deterministic_release_contains_shadowrocket_and_pinned_assets(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp)
            first = release.publish(ROOT, out)
            current = release.read_current(out)
            self.assertEqual(current["schema_version"], 1)
            self.assertIsNone(current["previous"])
            self.assertEqual(current["active"]["file"], first.name)
            self.assertEqual(current["active"]["sha256"],
                             hashlib.sha256(first.read_bytes()).hexdigest())
            self.assertEqual(release.verify_current(out)["status"], "verified")
            with zipfile.ZipFile(first) as z:
                files = set(z.namelist())
                self.assertIn("clients/unified/shadowrocket.conf", files)
                self.assertIn("clients/unified/mihomo-remnawave.yaml", files)
                self.assertIn("clients/unified/singbox-remnawave-1.14.json", files)
                self.assertIn("rules/unified/refilter-domain-full.list", files)
                self.assertIn("geo/geoip.dat", files)
                self.assertIn("policy/unified-release-lock.json", files)
                self.assertIn("bundle-manifest.json", files)
                shadow = z.read("clients/unified/shadowrocket.conf").decode()
                self.assertIn("FINAL,PROXY,dns-failed", shadow)
                self.assertNotIn("update-url = https://raw.githubusercontent.com/togahimoko/garasu/main/", shadow)
                manifest = json.loads(z.read("bundle-manifest.json"))
                self.assertEqual(manifest["schema_version"], 1)
                self.assertEqual(len(manifest["assets"]), len(files) - 1)
                self.assertNotIn("subscription_url", json.dumps(manifest).lower())
            before = first.read_bytes()
            second = release.publish(ROOT, out)
            self.assertEqual(first, second)
            self.assertEqual(before, second.read_bytes())
            self.assertEqual(current, release.read_current(out))

    def test_corrupted_release_refuses_promotion_and_preserves_current(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp)
            first = release.publish(ROOT, out)
            original = (out / "CURRENT.json").read_bytes()
            # An existing release at the same ID must not be overwritten.
            first.write_bytes(b"corrupt")
            with self.assertRaises(ValueError):
                release.publish(ROOT, out)
            self.assertEqual((out / "CURRENT.json").read_bytes(), original)
            with self.assertRaises(ValueError):
                release.verify_current(out)

    def test_failed_pointer_swap_keeps_last_known_good_and_supports_rollback(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp)
            first = release.publish(ROOT, out)
            first_state = release.read_current(out)
            # A fault before pointer swap must leave the old release intact.
            with patch.object(release, "_atomic_current", side_effect=OSError("injected")):
                with self.assertRaises(OSError):
                    release.publish(ROOT, out, generation="canary-2")
            self.assertEqual(release.read_current(out), first_state)
            second = release.publish(ROOT, out, generation="canary-2")
            self.assertNotEqual(first.name, second.name)
            state = release.read_current(out)
            self.assertEqual(state["previous"], first_state["active"])
            self.assertEqual(release.verify_current(out)["status"], "verified")
            release.rollback(out)
            restored = release.read_current(out)
            self.assertEqual(restored["active"], first_state["active"])
            self.assertEqual(restored["previous"], state["active"])
            self.assertEqual(release.verify_current(out)["status"], "verified")

    def test_missing_or_bad_previous_release_fails_without_pointer_change(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp)
            release.publish(ROOT, out)
            release.publish(ROOT, out, generation="canary-2")
            state = release.read_current(out)
            (out / state["previous"]["file"]).unlink()
            with self.assertRaises(ValueError):
                release.rollback(out)
            self.assertEqual(release.read_current(out), state)


if __name__ == "__main__":
    unittest.main()
