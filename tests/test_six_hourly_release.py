"""A six-hour rule refresher must build and QA before any publish."""
from pathlib import Path
import plistlib
import unittest

ROOT = Path(__file__).resolve().parents[1]

class SixHourlyPublisher(unittest.TestCase):
    def test_refresh_script_validates_before_any_push(self):
        source = (ROOT / "scripts/update_six_hourly.sh").read_text()
        for stage in ("git clone", "scripts/refresh.py",
                      "scripts/sync_universal_routing.py",
                      "scripts/build_binary_assets.py", "scripts/qa.py", "git push"):
            self.assertIn(stage, source)
        self.assertLess(source.index("scripts/qa.py"), source.index("git push"))
        self.assertIn("GIT_TERMINAL_PROMPT=0", source)

    def test_macos_timer_fires_every_six_hours(self):
        config = plistlib.loads((ROOT / "automation/garasu-six-hourly.plist").read_bytes())
        self.assertEqual(config["StartInterval"], 21600)
        self.assertFalse(config.get("RunAtLoad", False))

if __name__ == "__main__":
    unittest.main()
