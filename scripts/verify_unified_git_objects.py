#!/usr/bin/env python3
"""Validate immutable Garasu release assets from original Git objects.

A scheduled refresh legitimately mutates rule files and geo/geosite.dat in
the working tree. This tool verifies the lock against the original, committed
Git objects and path/revision links, not the moving working tree. Fail closed
if history is missing, a blob differs or an asset's source commit is wrong.
"""
import argparse
import hashlib
from pathlib import Path, PurePosixPath
import re
import subprocess

from scripts import unified_policy

SHA = re.compile(r"^[a-f0-9]{40}$")
PATH = re.compile(r"^[a-zA-Z0-9_./-]+$")


def _git(root, *args):
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), *args], stderr=subprocess.PIPE)
    except (subprocess.CalledProcessError, OSError) as exc:
        raise ValueError("Locked Git source revision/blob unavailable") from exc


def verify_history(root, lock):
    root = Path(root)
    sources = lock.get("sources")
    assets = lock.get("assets")
    if not isinstance(sources, dict) or not isinstance(assets, dict) or not assets:
        raise ValueError("Incomplete historical release lock")
    for source in sources.values():
        if not isinstance(source, dict) or not SHA.fullmatch(source.get("revision", "")):
            raise ValueError("Unpinned source Git commit")
    count = 0
    for path, metadata in sorted(assets.items()):
        if (not isinstance(path, str) or not PATH.fullmatch(path)
                or path.startswith("/")
                or any(part in ("", ".", "..") for part in PurePosixPath(path).parts)):
            raise ValueError("Unsafe locked asset path")
        if not isinstance(metadata, dict):
            raise ValueError("Invalid locked asset metadata")
        source = metadata.get("source")
        if source not in sources:
            raise ValueError("Unknown locked release source")
        sha = metadata.get("git_blob")
        length = metadata.get("bytes")
        if (not isinstance(sha, str) or not SHA.fullmatch(sha)
                or not isinstance(length, int) or length <= 0):
            raise ValueError("Invalid Git blob integrity metadata")
        revision = sources[source]["revision"]
        line = _git(root, "ls-tree", revision, "--", path).decode("utf-8").strip()
        expected = "blob " + sha + "\t" + path
        if not line.endswith(expected):
            raise ValueError("Locked asset differs from source commit: " + path)
        data = _git(root, "cat-file", "blob", sha)
        git_hash = hashlib.sha1(
            b"blob " + str(len(data)).encode("ascii") + b"\x00" + data
        ).hexdigest()
        if len(data) != length or git_hash != sha:
            raise ValueError("Historical Git asset integrity mismatch: " + path)
        count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path,
                        default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.root.resolve()
    policy = unified_policy.load_policy(root / "policy/unified-v1.json")
    lock = unified_policy.load_release_lock(
        root / "policy/unified-release-lock.json", policy)
    print("Verified historical pinned Git assets:", verify_history(root, lock))
    print("Mutable current-main rule files are intentionally not compared.")


if __name__ == "__main__":
    main()
