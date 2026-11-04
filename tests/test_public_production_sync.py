"""Regression gates for one production Garasu delivery, without extra SSR."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from scripts.sync_public_links import ROOT, expected_files, sync


class OneProductionDelivery(unittest.TestCase):
    def test_one_srr_and_all_links_point_to_production_release(self):
        self.assertEqual([p.name for p in (ROOT / "release/remnawave").glob("*.json")],
                         ["srr.json"])
        self.assertEqual(sync(write=False), [])
        links = json.loads((ROOT / "install/links.json").read_text())
        for key in ("mihomo_template", "stash_template", "singbox_template",
                    "xray_advanced_template", "incy"):
            self.assertIn("/main/release/", links[key])
        self.assertNotIn("/main/clients/", links["shadowrocket"])

    def test_stale_mobile_compatibility_file_blocks_release(self):
        with tempfile.TemporaryDirectory(prefix="garasu-delivery-") as directory:
            root = Path(directory)
            for name in ("release/incy/config.json", "release/happ/config.json",
                         "release/remnawave/srr.json", "clients/incy.json",
                         "clients/happ.json",
                         "release/mihomo/config.yaml", "release/stash/config.yaml",
                         "release/singbox/config.json", "release/shadowrocket/config.conf",
                         "clients/mihomo-remnawave.yaml", "clients/stash-remnawave.yaml",
                         "clients/singbox-remnawave.json", "clients/singbox-remnawave-1.14.json",
                         "clients/shadowrocket.conf", "install/manifest.json",
                         "install/links.json"):
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, target)
            self.assertEqual(sync(root=root), [])
            (root / "clients/happ.json").write_text("{}")
            with self.assertRaisesRegex(SystemExit, "clients/happ.json"):
                sync(root=root)

    def test_extra_test_srr_blocks_release_even_if_formats_are_valid(self):
        with tempfile.TemporaryDirectory(prefix="garasu-srr-") as directory:
            root = Path(directory)
            for name in ("release/incy/config.json", "release/happ/config.json",
                         "release/remnawave/srr.json",
                         "release/mihomo/config.yaml", "release/stash/config.yaml",
                         "release/singbox/config.json", "release/shadowrocket/config.conf",
                         "install/manifest.json", "install/links.json"):
                dest = root / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, dest)
            (root / "release/remnawave/srr-test.json").write_text('{"version":"1"}')
            with self.assertRaisesRegex(ValueError, "separate test SSR"):
                expected_files(root)


if __name__ == "__main__":
    unittest.main()
