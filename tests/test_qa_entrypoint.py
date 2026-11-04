"""Guard native QA's direct-script entry point against cwd/PYTHONPATH assumptions."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NativeQAEntrypointTests(unittest.TestCase):
    def test_native_verifier_import_from_external_cwd_without_pythonpath(self):
        script = ROOT / "scripts" / "qa.py"
        expression = (
            "import runpy; "
            + "runpy.run_path(" + repr(str(script)) + "); "
            + "from scripts.verify_release import digest, json_file; "
            + "assert callable(digest) and callable(json_file)"
        )
        environment = dict(os.environ)
        environment.pop("PYTHONPATH", None)
        with tempfile.TemporaryDirectory(prefix="garasu-qa-entry-") as folder:
            result = subprocess.run(
                [sys.executable, "-c", expression],
                cwd=folder,
                env=environment,
                text=True,
                capture_output=True,
                timeout=15,
            )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
