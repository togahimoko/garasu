#!/usr/bin/env python3
"""Build an OFFLINE Remnawave Subscription Response Rules candidate.

Never invokes the Remnawave API or writes to the input export.
Only creates a new JSON file for an operator to review and test.
"""
import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OUR_NAMES = {"Garasu INCY", "Garasu Happ"}

def new_rule(name, regex, key, value):
    if not value or not isinstance(value, str):
        raise ValueError("Invalid installation link")
    if len(value.encode("utf-8")) > 3000:
        raise ValueError("Header is too large to stage safely")
    return {
        "name": name,
        "description": "Garasu routing for this client only; default server URLs unchanged.",
        "enabled": True,
        "operator": "AND",
        "conditions": [{
            "headerName": "user-agent",
            "operator": "REGEX",
            "value": regex,
            "caseSensitive": False,
        }],
        "responseType": "XRAY_BASE64",
        "responseModifications": {
            "headers": [{"key": key, "value": value}],
            "applyHeadersToEnd": True,
            "ignoreServeJsonAtBaseSubscription": True,
        },
    }

def patch(current, links, clients=("incy", "happ")):
    if not isinstance(current, dict) or not isinstance(current.get("rules"), list):
        raise ValueError("Not a Remnawave SRR export")
    if current.get("version") != "1":
        raise ValueError("Unexpected Remnawave SRR version")
    rules = current["rules"]
    if not any(r.get("responseType") == "BROWSER" for r in rules):
        raise ValueError("Missing browser rule; refusing unsafe edit")
    if not rules or not (
        rules[-1].get("responseType") == "XRAY_BASE64"
        and not rules[-1].get("conditions")
    ):
        raise ValueError("Missing unconditional XRAY_BASE64 fallback; refusing edit")
    if not any(r.get("responseType") == "MIHOMO" for r in rules):
        raise ValueError("Missing MIHOMO rule; refusing edit")
    if not set(clients).issubset({"incy", "happ"}):
        raise ValueError("Unknown client")
    preserved = [r for r in rules if r.get("name") not in OUR_NAMES]
    insertion = next(i for i,r in enumerate(preserved) if r.get("responseType") != "BROWSER")
    additions = []
    if "incy" in clients:
        if not re.match(r"^incy://autorouting/onadd/https://", links["incy"]):
            raise ValueError("INCY autorouting URL missing or not HTTPS")
        additions.append(new_rule("Garasu INCY", r"^incy/", "autorouting", links["incy"]))
    if "happ" in clients:
        if not links["happ"].startswith("happ://routing/onadd/"):
            raise ValueError("Happ routing onadd URL missing")
        additions.append(new_rule("Garasu Happ", r"^happ/", "routing", links["happ"]))
    output = json.loads(json.dumps(current))
    output["rules"] = preserved[:insertion] + additions + preserved[insertion:]
    return output

def main():
    p = argparse.ArgumentParser()
    p.add_argument("source", help="LATEST CURRENT SRR export downloaded from your Remnawave")
    p.add_argument("destination", help="NEW staged output JSON for local testing")
    p.add_argument("--client", choices=["incy", "happ", "both"], default="both")
    a = p.parse_args()
    original, out = Path(a.source), Path(a.destination)
    if original.resolve() == out.resolve():
        p.error("Refusing to overwrite source")
    rules = json.loads(original.read_text(encoding="utf-8"))
    links = json.loads((ROOT / "install/links.json").read_text(encoding="utf-8"))
    clients = ("incy", "happ") if a.client == "both" else (a.client,)
    candidate = patch(rules, links, clients=clients)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Staged {a.client} routing; preserved {len(rules)} existing rules and original input.")
    print("NOTE: NOT APPLIED. Test HTTP format and connectivity on a disposable subscription.")

if __name__ == "__main__":
    main()
