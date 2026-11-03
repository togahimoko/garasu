"""Immutable release source validation must survive mutable main refreshes."""
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts import verify_unified_git_objects as history

ROOT = Path(__file__).resolve().parents[1]


def git(folder, *args):
    return subprocess.check_output(["git", "-C", str(folder), *args],
                                   stderr=subprocess.PIPE).decode().strip()


class PinnedGitHistory(unittest.TestCase):
    def test_verified_objects_are_independent_of_current_worktree_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            git(directory, "init", "-q")
            git(directory, "config", "user.name", "CI")
            git(directory, "config", "user.email", "ci@example.invalid")
            asset = directory / "rules" / "test.list"
            asset.parent.mkdir(parents=True)
            payload = b"+.example.org\n"
            asset.write_bytes(payload)
            git(directory, "add", "rules/test.list")
            git(directory, "commit", "-qm", "frozen source")
            rev = git(directory, "rev-parse", "HEAD")
            blob = git(directory, "rev-parse", "HEAD:rules/test.list")
            lock = {"sources": {"base": {"revision": rev}},
                    "assets": {"rules/test.list": {"source": "base",
                                               "git_blob": blob,
                                               "bytes": len(payload)}}}
            self.assertEqual(history.verify_history(directory, lock), 1)
            # Exactly what scheduled refresh does: mutate local files, but do
            # not mutate the locked historical Git release.
            asset.write_bytes(b"+.different.example.org\n")
            self.assertEqual(history.verify_history(directory, lock), 1)
            lock["assets"]["rules/test.list"]["bytes"] += 1
            with self.assertRaises(ValueError):
                history.verify_history(directory, lock)

    def test_missing_git_object_and_traversal_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            git(root, "init", "-q")
            git(root, "config", "user.name", "CI")
            git(root, "config", "user.email", "ci@example.invalid")
            (root / "file").write_text("hello")
            git(root, "add", "file")
            git(root, "commit", "-qm", "hello")
            rev = git(root, "rev-parse", "HEAD")
            blob = git(root, "rev-parse", "HEAD:file")
            lock = {"sources": {"base": {"revision": rev}},
                    "assets": {"../file": {"source": "base", "git_blob": blob, "bytes": 5}}}
            with self.assertRaises(ValueError):
                history.verify_history(root, lock)
            lock["assets"] = {"file": {"source": "base", "git_blob": "a"*40, "bytes": 5}}
            with self.assertRaises(ValueError):
                history.verify_history(root, lock)


if __name__ == "__main__":
    unittest.main()
