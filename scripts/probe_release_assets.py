#!/usr/bin/env python3
"""Opt-in HTTPS verification of published Garasu release files (no subscriptions)."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys
import time
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://raw.githubusercontent.com/togahimoko/garasu/"
ASSETS = (
    "release/mihomo/config.yaml",
    "release/stash/config.yaml",
    "release/singbox/config.json",
    "release/incy/config.json",
    "release/happ/config.json",
    "release/shadowrocket/config.conf",
    "release/xray/config.json",
    "release/remnawave/srr.json",
)


def candidate_files(root: Path) -> list[str]:
    mrs = sorted("release/mihomo/.mrs/" + path.name
                 for path in (root / "release/mihomo/.mrs").glob("*.mrs"))
    return list(ASSETS) + mrs + ["release/mihomo/.mrs/manifest.json"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", choices=("main", "dev"), default="main")
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    if not 1 <= args.timeout <= 60:
        parser.error("--timeout must be between 1 and 60 seconds")

    opener = build_opener(ProxyHandler({}))  # HTTPS DIRECT, no profile changes.
    files = candidate_files(args.root)
    problems = []
    for relative in files:
        expected = (args.root / relative).read_bytes()
        url = BASE + args.branch + "/" + relative
        req = Request(url, headers={"User-Agent": "Garasu-Release-Audit/1.0",
                                    "Accept-Encoding": "identity"})
        started = time.monotonic()
        try:
            with opener.open(req, timeout=args.timeout) as response:
                if response.status != 200:
                    raise ValueError("HTTP " + str(response.status))
                remote = response.read(len(expected) + 1)
            if hashlib.sha256(expected).digest() != hashlib.sha256(remote).digest():
                raise ValueError("remote bytes differ from the checkout")
            print("PASS", relative, str(round(1000 * (time.monotonic() - started))) + "ms")
        except (OSError, ValueError) as exc:
            problems.append(relative)
            print("FAIL", relative, str(exc), file=sys.stderr)
    if problems:
        raise SystemExit("Published assets differ: " +
                         str(len(problems)) + "/" + str(len(files)))
    print("PASS published", args.branch, str(len(files)) + "/" + str(len(files)))


if __name__ == "__main__":
    main()
