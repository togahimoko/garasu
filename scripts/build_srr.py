#!/usr/bin/env python3
"""Build offline Remnawave response-rules candidates. Never changes the live panel."""
import argparse
import base64
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = {"MIHOMO": "Garasu Mihomo", "STASH": "Garasu Stash", "SINGBOX": "Garasu Singbox"}
TEST_AGENTS = {"incy": "garasu-test-incy", "happ": "garasu-test-happ",
               "mihomo": "garasu-test-mihomo", "stash": "garasu-test-stash",
               "singbox": "garasu-test-singbox"}
PREVIEW_NAMES = {"Garasu INCY preview", "Garasu Happ preview", "Garasu Mihomo preview",
                 "Garasu Stash preview", "Garasu Singbox preview"}


def _validate_links(links):
    inc = links.get("incy", "")
    hap = links.get("happ", "")
    if not isinstance(inc, str) or not inc.startswith("incy://autorouting/onadd/https://"):
        raise ValueError("Invalid INCY routing URL")
    if not isinstance(hap, str) or not hap.startswith("happ://routing/onadd/"):
        raise ValueError("Invalid Happ routing URL")
    if len(hap.encode("utf-8")) > 3000:
        raise ValueError("Happ header exceeds conservative 3000-byte budget")
    try:
        profile = json.loads(base64.b64decode(hap.split("/onadd/", 1)[1], validate=True))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("Malformed Happ routing payload") from exc
    if profile.get("Name") != "Garasu MAX":
        raise ValueError("Unexpected Happ routing profile")


def _target_rules(rules):
    result = {}
    for rule in rules:
        typ = rule.get("responseType")
        c = rule.get("conditions", [])
        v = c[0].get("value", "").lower() if c and isinstance(c[0], dict) else ""
        if typ in TEMPLATES:
            key = typ.lower()
        elif typ == "XRAY_BASE64" and c and c[0].get("headerName", "").lower() == "user-agent":
            key = "incy" if v.startswith("incy") else "happ" if v.startswith("happ") else None
        else:
            key = None
        if key:
            if key in result:
                raise ValueError("Ambiguous duplicate rules for " + key)
            result[key] = rule
    missing = set(TEST_AGENTS) - set(result)
    if missing:
        raise ValueError("Missing existing client rules: " + ", ".join(sorted(missing)))
    return result


def _full(current, links):
    if not isinstance(current, dict) or current.get("version") != "1":
        raise ValueError("Not a supported Remnawave SRR export")
    raw = current.get("rules")
    if not isinstance(raw, list) or len(raw) < 8:
        raise ValueError("Expected an 8+ rule SRR export")
    rules = [r for r in raw if r.get("name") not in PREVIEW_NAMES]
    if not rules or rules[0].get("responseType") != "BROWSER":
        raise ValueError("First rule must remain BROWSER")
    if rules[-1].get("responseType") != "XRAY_BASE64" or rules[-1].get("conditions"):
        raise ValueError("Last rule must remain unconditional XRAY_BASE64")
    _validate_links(links)
    result = copy.deepcopy(current)
    result["rules"] = copy.deepcopy(rules)
    targets = _target_rules(result["rules"])
    for key, label, header_name in [("incy", "INCY + Garasu MAX", "autorouting"),
                                    ("happ", "Happ + Garasu MAX", "routing")]:
        rule = targets[key]
        mod = rule.setdefault("responseModifications", {})
        mod["headers"] = [{"key": header_name, "value": links[key]}]
        mod["applyHeadersToEnd"] = True
        mod["ignoreServeJsonAtBaseSubscription"] = True
        rule["name"] = label
        rule["description"] = (
            "Garasu MAX autorouting; preserves personal XRAY_BASE64 subscription"
            if key == "incy" else
            "Garasu MAX embedded routing profile; preserves personal XRAY_BASE64 subscription"
        )
    for typ, template in TEMPLATES.items():
        targets[typ.lower()].setdefault("responseModifications", {})["subscriptionTemplate"] = template
    return result


def patch(current, links, mode="test"):
    """test: real client UAs remain unchanged; full: switch five client rules."""
    if mode not in ("test", "full"):
        raise ValueError("Choose test or full")
    full = _full(current, links)
    if mode == "full":
        return full
    orig = copy.deepcopy(current)
    orig["rules"] = [r for r in orig["rules"] if r.get("name") not in PREVIEW_NAMES]
    targets = _target_rules(full["rules"])
    previews = []
    labels = {"incy": "Garasu INCY preview", "happ": "Garasu Happ preview",
              "mihomo": "Garasu Mihomo preview", "stash": "Garasu Stash preview",
              "singbox": "Garasu Singbox preview"}
    for key, agent in TEST_AGENTS.items():
        rule = copy.deepcopy(targets[key])
        rule["name"] = labels[key]
        rule["description"] = "TEST ONLY: matches custom diagnostic User-Agent; existing customer rules unchanged"
        rule["conditions"] = [{"headerName": "user-agent", "operator": "STARTS_WITH",
                               "value": agent, "caseSensitive": False}]
        previews.append(rule)
    orig["rules"] = orig["rules"][:1] + previews + orig["rules"][1:]
    return orig


def main():
    p = argparse.ArgumentParser()
    p.add_argument("source", help="Current Remnawave SRR export JSON")
    p.add_argument("destination", help="New output path; original never overwritten")
    p.add_argument("--mode", choices=["test", "full"], default="test")
    a = p.parse_args()
    source, dest = Path(a.source), Path(a.destination)
    if source.resolve() == dest.resolve():
        p.error("Input and output paths must differ")
    current = json.loads(source.read_text(encoding="utf-8"))
    links = json.loads((ROOT / "install/links.json").read_text(encoding="utf-8"))
    result = patch(current, links, mode=a.mode)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Garasu mode=" + a.mode, "rules=" + str(len(result["rules"])))
    print("Offline only. Remnawave was NOT modified.")


if __name__ == "__main__":
    main()
