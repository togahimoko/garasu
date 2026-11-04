"""Binary release compiler must be reproducible and support safe checking."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]

class BuilderContract(unittest.TestCase):
    def test_compiler_exposes_safe_check_mode(self):
        result = subprocess.run([sys.executable, "scripts/build_binary_assets.py", "--help"],
                                cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--check", result.stdout)
        self.assertIn("--write", result.stdout)
        self.assertIn("--mihomo-core", result.stdout)
        self.assertIn("--singbox-core", result.stdout)

if __name__ == "__main__":
    unittest.main()
