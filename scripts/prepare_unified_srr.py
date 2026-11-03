#!/usr/bin/env python3
"""Generate OFFLINE Remnawave SRR previews / full candidates from a live export.

Source JSON is required; never writes to the Remnawave panel or to the source.
For eight-rule layouts preserve the existing Browser, XRAY_BASE64 fallback,
client conditions, template names and arbitrary user-provided properties.
"""
import argparse
import base64
import copy
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
REPO = "togahimoko/garasu"
HEX_SHA = re.compile(r"^[a-f0-9]{40}$")
PREVIEW = [
    ("incy", 1, "Garasu Unified INCY preview"),
    ("happ", 2, "Garasu Unified Happ preview"),
    ("mihomo", 3, "Garasu Unified Mihomo preview"),
    ("stash", 4, "Garasu Unified Stash preview"),
    ("singbox", 5, "Garasu Unified Singbox preview"),
]
PREVIEW_NAMES = {item[2] for item in PREVIEW}
SINGBOX_UA = "^(?:sfa|sfi|sfm|sft|karing|singbox)"


def _ua(rule):
    if rule.get("operator") != "AND":
        raise ValueError("Unexpected SRR rule operator")
    conditions = rule.get("conditions")
    if (not isinstance(conditions, list) or len(conditions) != 1 or
            not isinstance(conditions[0], dict)):
        raise ValueError("Unexpected SRR condition structure")
    cond = conditions[0]
    if cond.get("headerName", "").lower() != "user-agent":
        raise ValueError("Expected a user-agent condition")
    if cond.get("caseSensitive") is not False:
        raise ValueError("SRR client User-Agent conditions must be case-insensitive")
    return cond


def _validate(source):
    if (not isinstance(source, dict) or source.get("version") != "1" or
            not isinstance(source.get("rules"), list)):
        raise ValueError("Expected version=1 Remnawave SRR export")
    cleaned = copy.deepcopy(source)
    cleaned["rules"] = [rule for rule in cleaned["rules"]
                        if rule.get("name") not in PREVIEW_NAMES]
    rules = cleaned["rules"]
    if len(rules) != 8:
        raise ValueError("This generator accepts the supplied 8-rule SRR layout")
    expected = ("BROWSER", "XRAY_BASE64", "XRAY_BASE64", "MIHOMO",
                "STASH", "SINGBOX", "CLASH", "XRAY_BASE64")
    if tuple(r.get("responseType") for r in rules) != expected:
        raise ValueError("Unsupported SRR rule order or response types")
    if (not isinstance(rules[0].get("conditions"), list) or
            rules[0]["conditions"][0].get("headerName", "").lower() != "accept" or
            not isinstance(rules[-1].get("conditions"), list) or
            rules[-1]["conditions"]):
        raise ValueError("Browser and unconditional XRAY_BASE64 fallback required")
    if not all(rule.get("enabled", True) is True for rule in rules):
        raise ValueError("Disabled SRR rules must be reviewed manually")
    for i, prefix in ((1, "incy/"), (2, "happ")):
        condition = _ua(rules[i])
        if (condition.get("operator") != "STARTS_WITH" or
                condition.get("value", "").lower() != prefix):
            raise ValueError("Unexpected dedicated INCY/Happ User-Agent")
    for i in (3, 4, 5, 6):
        condition = _ua(rules[i])
        if condition.get("operator") != "REGEX":
            raise ValueError("Unexpected client routing regex")
    for i, fmt in ((3, "MIHOMO"), (4, "STASH"), (5, "SINGBOX")):
        modifications = rules[i].get("responseModifications", {})
        if (not isinstance(modifications, dict) or
                not isinstance(modifications.get("subscriptionTemplate"), str) or
                not modifications["subscriptionTemplate"].strip()):
            raise ValueError("Missing installed Remnawave template for " + fmt)
    for i, key in ((1, "autorouting"), (2, "routing")):
        mod = rules[i].get("responseModifications")
        if not isinstance(mod, dict) or not isinstance(mod.get("headers"), list):
            raise ValueError("Missing original device routing header")
        if [h.get("key", "").lower() for h in mod["headers"]] != [key]:
            raise ValueError("Unexpected INCY/Happ routing headers; review manually")
    return cleaned


def _make_links(root, ref):
    if not isinstance(ref, str) or not HEX_SHA.fullmatch(ref):
        raise ValueError("A pinned, full 40-char Git SHA is required")
    inc = json.loads((Path(root) / "clients/unified/incy.json").read_text(
        encoding="utf-8"))
    happ = json.loads((Path(root) / "clients/unified/happ.json").read_text(
        encoding="utf-8"))
    if inc != happ:
        raise ValueError("INCY/Happ unified policies disagree")
    if (happ.get("DirectSites") != ["geosite:private"] or
            happ.get("DirectIp") != ["geoip:private"] or
            happ.get("BlockSites") != [] or
            happ.get("BlockIp") != [] or
            not happ.get("GlobalProxy")):
        raise ValueError("Client profile has unexpected broad DIRECT/fallback")
    compact = json.dumps(happ, ensure_ascii=False, separators=(",", ":"))
    encoded = base64.b64encode(compact.encode("utf-8")).decode("ascii")
    happ_link = "happ://routing/onadd/" + encoded
    if len(happ_link.encode("utf-8")) > 3000:
        raise ValueError("Embedded Happ header exceeds conservative 3000-byte budget")
    inc_url = ("https://raw.githubusercontent.com/" + REPO + "/" + ref +
               "/clients/unified/incy.json")
    return {"incy": "incy://autorouting/onadd/" + inc_url,
            "happ": happ_link}


def _replace_header(rule, key, value):
    mod = rule["responseModifications"]
    mod["headers"] = [{"key": key, "value": value}]
    mod["applyHeadersToEnd"] = True
    mod["ignoreServeJsonAtBaseSubscription"] = True


def prepare(source, ref, *, mode="preview", root=ROOT, template_names=None):
    if mode not in ("preview", "full"):
        raise ValueError("Select preview or full")
    if template_names is not None:
        if (not isinstance(template_names, dict) or
                set(template_names) != {"mihomo", "stash", "singbox"} or
                any(not isinstance(name, str) or
                    not name.strip() or len(name) > 128 or
                    any(ch in name for ch in "\\r\\n")
                    for name in template_names.values()) or
                len(set(template_names.values())) != 3):
            raise ValueError("All three distinct, installed template names required")
    clean = _validate(source)
    links = _make_links(root, ref)
    candidate = copy.deepcopy(clean)
    rules = candidate["rules"]
    _replace_header(rules[1], "autorouting", links["incy"])
    _replace_header(rules[2], "routing", links["happ"])
    rules[5]["conditions"][0]["value"] = SINGBOX_UA
    if template_names is not None:
        for key, i in (("mihomo", 3), ("stash", 4), ("singbox", 5)):
            rules[i]["responseModifications"]["subscriptionTemplate"] = template_names[key]
    if mode == "full":
        return candidate
    previews = []
    for client, index, name in PREVIEW:
        rule = copy.deepcopy(rules[index])
        rule["name"] = name
        rule["description"] = "TEST ONLY: isolated Garasu Unified response; regular subscribers unaffected"
        rule["conditions"] = [{"headerName": "user-agent",
                              "operator": "STARTS_WITH",
                              "value": "garasu-test-" + client,
                              "caseSensitive": False}]
        previews.append(rule)
    # Real eight rules remain byte-identical as JSON data, except no old
    # previews. New previews are immediately behind Browser and ahead of
    # the unchanged original INCY/Happ and all original template/fallback.
    clean["rules"] = [clean["rules"][0], *previews, *clean["rules"][1:]]
    return clean


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", help="Original private Remnawave 8-rule export JSON")
    p.add_argument("destination", help="New candidate output JSON (exclusive create)")
    p.add_argument("--ref", required=True, help="Pinned Git main commit (40 hex)")
    p.add_argument("--mode", choices=["preview", "full"], default="preview")
    p.add_argument("--mihomo-template")
    p.add_argument("--stash-template")
    p.add_argument("--singbox-template")
    args = p.parse_args()
    supplied = [args.mihomo_template, args.stash_template, args.singbox_template]
    if any(v is not None for v in supplied) and not all(v is not None for v in supplied):
        p.error("Pass all three --*-template names or none")
    names = (dict(zip(("mihomo", "stash", "singbox"), supplied))
             if all(v is not None for v in supplied) else None)
    source, target = Path(args.source), Path(args.destination)
    if source.resolve() == target.resolve():
        p.error("Cannot overwrite SRR input")
    current = json.loads(source.read_text(encoding="utf-8"))
    result = prepare(current, args.ref, mode=args.mode, template_names=names)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as output:
        output.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print("Garasu Unified", args.mode, "candidate:", len(result["rules"]),
          "rules. Offline only; panel has NOT been changed.")


if __name__ == "__main__":
    main()
