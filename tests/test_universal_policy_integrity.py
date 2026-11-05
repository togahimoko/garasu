"""The source of all routing decisions must be versioned in release manifest."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

class PolicyIntegrity(unittest.TestCase):
    def test_both_policy_sources_are_content_addressed(self):
        manifest=json.loads((ROOT/"install/manifest.json").read_text())
        for relative in ("policy/universal.json","policy/extra_categories.json"):
            with self.subTest(relative=relative):
                blob=(ROOT/relative).read_bytes()
                record=manifest["files"][relative]
                self.assertEqual(record["bytes"],len(blob))
                self.assertEqual(record["sha256"],hashlib.sha256(blob).hexdigest())

if __name__=="__main__":
    unittest.main()
