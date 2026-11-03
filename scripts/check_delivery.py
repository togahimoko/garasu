#!/usr/bin/env python3
"""Probe Garasu rule delivery over TLS from the network where this runs.

Compares downloaded bytes with the local release manifest, without reading
subscription tokens, VPN nodes or user credentials.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import urlsplit, quote
from urllib.request import Request, ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATHS = (
    "rules/youtube.list",
    "rules/rkn-domains.list",
    "rules/singbox/youtube.json",
    "geo/geoip.dat",
    "geo/geosite.dat",
)


def validate_base_url(value):
    if not isinstance(value, str):
        raise ValueError("Base URL must be a string")
    parsed = urlsplit(value.rstrip("/"))
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment
            or ".." in parsed.path.split("/") or "\\" in parsed.path):
        raise ValueError("Rules must be fetched from a plain trusted HTTPS base URL")
    return value.rstrip("/")


def verify_asset(path, payload, manifest):
    record = manifest.get("files", {}).get(path)
    if not isinstance(record, dict):
        raise ValueError("Unknown asset not recorded in release manifest: " + path)
    if len(payload) != record.get("bytes"):
        raise ValueError("Length mismatch for " + path)
    if hashlib.sha256(payload).hexdigest() != record.get("sha256"):
        raise ValueError("SHA256 mismatch for " + path)
    return True


def probe(opener, base, path, manifest, timeout):
    if path not in manifest.get("files", {}):
        raise ValueError("Not in manifest: " + path)
    if path.startswith("/") or ".." in path.split("/"):
        raise ValueError("Unsafe relative path")
    url = base + "/" + quote(path, safe="/")
    expected = manifest["files"][path]["bytes"]
    req = Request(url, headers={"User-Agent": "Garasu-Delivery-Probe/1.0",
                                "Accept-Encoding": "identity"})
    start = time.monotonic()
    with opener.open(req, timeout=timeout) as response:
        if response.status != 200:
            raise ValueError(path + ": HTTP " + str(response.status))
        if urlsplit(response.geturl()).scheme != "https":
            raise ValueError(path + ": unsafe redirect")
        payload = response.read(expected + 1)
    verify_asset(path, payload, manifest)
    return {"file": path, "status": "ok", "bytes": len(payload),
            "elapsed_ms": round((time.monotonic() - start) * 1000)}


def main():
    p = argparse.ArgumentParser(description="Test Garasu HTTPS rule integrity from this network")
    p.add_argument("--base-url", default="https://raw.githubusercontent.com/togahimoko/garasu/main")
    p.add_argument("--manifest", type=Path, default=ROOT / "install/manifest.json")
    p.add_argument("--timeout", type=float, default=15)
    p.add_argument("--json-output", type=Path)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--direct", action="store_true", help="Ignore proxy environment variables")
    mode.add_argument("--proxy", help="Explicit local HTTP proxy, e.g. http://127.0.0.1:7890")
    args = p.parse_args()
    base = validate_base_url(args.base_url)
    if args.timeout <= 0 or args.timeout > 120:
        p.error("timeout must be in (0, 120] seconds")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if args.direct:
        opener = build_opener(ProxyHandler({}))
        mode_label = "direct"
    elif args.proxy:
        parsed = urlsplit(args.proxy)
        if (parsed.scheme != "http" or parsed.hostname not in
                ("127.0.0.1", "localhost", "::1") or not parsed.port
                or parsed.username or parsed.password):
            p.error("--proxy must be a local HTTP proxy without credentials")
        opener = build_opener(ProxyHandler({"http": args.proxy, "https": args.proxy}))
        mode_label = "local-proxy"
    else:
        opener = build_opener()
        mode_label = "environment"
    results = []
    for path in DEFAULT_PATHS:
        try:
            item = probe(opener, base, path, manifest, args.timeout)
            print("PASS", path, str(item["elapsed_ms"]) + "ms")
        except Exception as exc:
            item = {"file": path, "status": "error", "reason": str(exc)}
            print("FAIL", path, str(exc))
        results.append(item)
    report = {"system": "Garasu delivery", "base_url": base,
              "route": mode_label, "results": results}
    if args.json_output:
        args.json_output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if any(item["status"] != "ok" for item in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
