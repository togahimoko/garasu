#!/usr/bin/env python3
"""Rebuild/verify compact Garasu MRS + SRS from one canonical source snapshot.

No network and no automatic publication. --check never changes a file.
--write promotes a complete validated set, restoring old files on write failure.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from release.mihomo.build import build as build_mrs
from scripts.refresh import promote_staged
from scripts.sync_universal_routing import provider_sets, load_policy


def build_assets(root: Path, mihomo: Path, singbox: Path, *, write: bool) -> int:
    upstream = json.loads((root / "install/manifest.json").read_text())["upstream_revision"]
    sets = provider_sets(load_policy(root))
    with tempfile.TemporaryDirectory(prefix="garasu-compiled-") as temp:
        staged = Path(temp)
        mrsdir = staged / "release/mihomo/.mrs"
        srsdir = staged / "release/singbox/rules"
        srsdir.mkdir(parents=True, exist_ok=True)
        build_mrs(mihomo, root, mrsdir, source_commit=upstream)
        generated = {}
        for file in mrsdir.iterdir():
            if file.suffix not in (".mrs", ".json"):
                continue
            relative = "release/mihomo/.mrs/" + file.name
            generated[relative] = file.read_bytes()
        for name in sets:
            src = root / ("release/singbox/rules/" + name + ".json")
            out = srsdir / (name + ".srs")
            subprocess.run([str(singbox), "rule-set", "compile", "--output",
                            str(out), str(src)], check=True,
                           capture_output=True, text=True)
            if out.stat().st_size < 20:
                raise ValueError("Unexpectedly small SRS: " + name)
            generated["release/singbox/rules/" + name + ".srs"] = out.read_bytes()
        if write:
            promote_staged(root, staged, generated)
        else:
            stale = [name for name, blob in generated.items()
                     if not (root / name).is_file()
                     or (root / name).read_bytes() != blob]
            if stale:
                raise ValueError("Stale binary release assets: " + ", ".join(stale))
        print(f"PASS {len(generated)} native assets: 13 MRS + 10 SRS + 1 manifest; write={write}")
        return len(generated)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--mihomo-core", type=Path, required=True)
    parser.add_argument("--singbox-core", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()
    build_assets(args.root.resolve(), args.mihomo_core.resolve(),
                 args.singbox_core.resolve(), write=args.write)


if __name__ == "__main__":
    main()
