#!/usr/bin/env python3
"""Build offline Remnawave response-rules candidates. Never changes the live panel."""
import argparse
import base64
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = {"MIHOMO": "Garasu Mihomo", "STASH": "Garasu Stash", "SINGBOX": "Garasu Singbox"}
LEGACY_SINGBOX_UA = "^sfa|sfi|sfm|sft|karing|singbox"
SINGBOX_UA = "^(?:sfa|sfi|sfm|sft|karing|singbox)"


def _clash_rule(rule):
    """Identify only the generic Clash rule, never Clash Verge/Mihomo."""
    if rule.get("responseType") not in ("CLASH", "MIHOMO"):
        return False
    conditions = rule.get("conditions", [])
    if len(conditions) != 1 or conditions[0].get("headerName", "").lower() != "user-agent":
        return False
    condition = conditions[0]
    operator, value = condition.get("operator"), condition.get("value", "").lower()
    return ((operator == "REGEX" and value in ("^clash", r"^clash(?:/|$)"))
            or (operator == "STARTS_WITH" and value in ("clash", "clash/")))
TEST_AGENTS = {"incy": "garasu-test-incy", "happ": "garasu-test-happ",
               "mihomo": "garasu-test-mihomo", "stash": "garasu-test-stash",
               "singbox": "garasu-test-singbox"}
PREVIEW_NAMES = {"Garasu INCY preview", "Garasu Happ preview", "Garasu Mihomo preview",
                 "Garasu Stash preview", "Garasu Singbox preview",
                 "Garasu Xray JSON preview"}
XRAY_RULE_NAME = "Garasu Xray JSON opt-in"


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
        if _clash_rule(rule):
            continue  # A Clash compatibility rule may also have responseType MIHOMO.
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
    # The six-rule panel uses one XRAY_BASE64 fallback for INCY and Happ.
    # Dedicated client rules are optional, but core templates are required.
    missing = {k.lower() for k in TEMPLATES} - set(result)
    if missing:
        raise ValueError("Missing existing client rules: " + ", ".join(sorted(missing)))
    return result


def _full(current, links, *, include_xray=False, include_mobile=False,
          clash_mihomo_compat=False):
    if not isinstance(current, dict) or current.get("version") != "1":
        raise ValueError("Not a supported Remnawave SRR export")
    raw = current.get("rules")
    if not isinstance(raw, list) or len(raw) < 6:
        raise ValueError("Expected at least six SRR rules")
    rules = [r for r in raw if r.get("name") not in PREVIEW_NAMES
             and r.get("name") != XRAY_RULE_NAME]
    if not rules or rules[0].get("responseType") != "BROWSER":
        raise ValueError("First rule must remain BROWSER")
    if rules[-1].get("responseType") != "XRAY_BASE64" or rules[-1].get("conditions"):
        raise ValueError("Last rule must remain unconditional XRAY_BASE64")
    _validate_links(links)
    result = copy.deepcopy(current)
    result["rules"] = copy.deepcopy(rules)
    targets = _target_rules(result["rules"])
    if include_mobile:
        for key, value in (("incy", "incy/"), ("happ", "happ")):
            if key not in targets:
                result["rules"].insert(-1, {
                    "name": "Garasu " + key.upper() + " routing",
                    "description": "Personal XRAY_BASE64 nodes with Garasu routing header",
                    "enabled": True,
                    "operator": "AND",
                    "conditions": [{"headerName": "user-agent",
                                    "operator": "STARTS_WITH",
                                    "value": value, "caseSensitive": False}],
                    "responseType": "XRAY_BASE64",
                })
        targets = _target_rules(result["rules"])
    for key, label, header_name in [("incy", "INCY + Garasu MAX", "autorouting"),
                                    ("happ", "Happ + Garasu MAX", "routing")]:
        # Do not attach client-specific headers to a shared unconditional fallback.
        if key not in targets:
            continue
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
    singbox_conditions = targets["singbox"].get("conditions", [])
    if (len(singbox_conditions) == 1 and
            singbox_conditions[0].get("operator") == "REGEX" and
            singbox_conditions[0].get("value") == LEGACY_SINGBOX_UA):
        singbox_conditions[0]["value"] = SINGBOX_UA
    if clash_mihomo_compat:
        clash_rules = [rule for rule in result["rules"] if _clash_rule(rule)]
        if len(clash_rules) != 1:
            raise ValueError("Expected exactly one generic Clash rule")
        clash = clash_rules[0]
        clash["responseType"] = "MIHOMO"
        clash["conditions"] = [{
            "headerName": "user-agent", "operator": "REGEX",
            "value": r"^clash(?:/|$)", "caseSensitive": False,
        }]
        clash.setdefault("responseModifications", {})["subscriptionTemplate"] = TEMPLATES["MIHOMO"]
        clash["description"] = (
            "Mihomo-compatible Garasu YAML for Clash-named modern cores; "
            "legacy Clash does not support VLESS/REALITY"
        )
    if include_xray:
        result["rules"].insert(-1, {
            "name": XRAY_RULE_NAME,
            "description": "Explicit Xray JSON opt-in; ordinary clients keep XRAY_BASE64 fallback",
            "enabled": True,
            "operator": "AND",
            "conditions": [{"headerName": "user-agent", "operator": "STARTS_WITH",
                            "value": "garasu-xray-json", "caseSensitive": False}],
            "responseType": "XRAY_JSON",
            "responseModifications": {"subscriptionTemplate": "Garasu Xray JSON"},
        })
    return result


def patch(current, links, mode="test", *, include_xray=False,
          include_mobile=False, clash_mihomo_compat=False):
    """test: real client UAs remain unchanged; full: switch five client rules."""
    if mode not in ("test", "full"):
        raise ValueError("Choose test or full")
    if mode == "test" and clash_mihomo_compat:
        raise ValueError("Clash live UA remapping requires full mode; preview stays isolated")
    full = _full(current, links, include_xray=include_xray,
                 include_mobile=include_mobile,
                 clash_mihomo_compat=clash_mihomo_compat)
    if mode == "full":
        return full
    orig = copy.deepcopy(current)
    orig["rules"] = [r for r in orig["rules"] if r.get("name") not in PREVIEW_NAMES
                     and r.get("name") != XRAY_RULE_NAME]
    targets = _target_rules(full["rules"])
    previews = []
    labels = {"incy": "Garasu INCY preview", "happ": "Garasu Happ preview",
              "mihomo": "Garasu Mihomo preview", "stash": "Garasu Stash preview",
              "singbox": "Garasu Singbox preview"}
    for key, agent in TEST_AGENTS.items():
        if key in targets:
            rule = copy.deepcopy(targets[key])
        elif key in ("incy", "happ"):
            # Clone the fallback only for a test User-Agent; live fallback stays intact.
            rule = copy.deepcopy(full["rules"][-1])
            header_name = "autorouting" if key == "incy" else "routing"
            mod = rule.setdefault("responseModifications", {})
            mod["headers"] = [{"key": header_name, "value": links[key]}]
            mod["applyHeadersToEnd"] = True
            mod["ignoreServeJsonAtBaseSubscription"] = True
        else:
            raise ValueError("Missing client rule for " + key)
        rule["name"] = labels[key]
        rule["description"] = "TEST ONLY: matches custom diagnostic User-Agent; existing customer rules unchanged"
        rule["conditions"] = [{"headerName": "user-agent", "operator": "STARTS_WITH",
                               "value": agent, "caseSensitive": False}]
        previews.append(rule)
    if include_xray:
        rule = copy.deepcopy(full["rules"][-2])
        rule["name"] = "Garasu Xray JSON preview"
        rule["description"] = "TEST ONLY: explicit Xray JSON response"
        rule["conditions"][0]["value"] = "garasu-test-xray"
        previews.append(rule)
    orig["rules"] = orig["rules"][:1] + previews + orig["rules"][1:]
    return orig


def main():
    p = argparse.ArgumentParser()
    p.add_argument("source", help="Current Remnawave SRR export JSON")
    p.add_argument("destination", help="New output path; original never overwritten")
    p.add_argument("--mode", choices=["test", "full"], default="test")
    p.add_argument("--with-xray-json", action="store_true",
                   help="add an explicit Xray JSON rule before BASE64 fallback")
    p.add_argument("--with-mobile-routing", action="store_true",
                   help="add dedicated INCY and Happ routing headers before BASE64 fallback")
    p.add_argument("--clash-mihomo-compat", action="store_true",
                   help="serve the existing Garasu Mihomo template to generic clash/1.0 clients (full only)")
    a = p.parse_args()
    source, dest = Path(a.source), Path(a.destination)
    if source.resolve() == dest.resolve():
        p.error("Input and output paths must differ")
    current = json.loads(source.read_text(encoding="utf-8"))
    links = json.loads((ROOT / "install/links.json").read_text(encoding="utf-8"))
    result = patch(current, links, mode=a.mode,
                   include_xray=a.with_xray_json,
                   include_mobile=a.with_mobile_routing,
                   clash_mihomo_compat=a.clash_mihomo_compat)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Garasu mode=" + a.mode, "rules=" + str(len(result["rules"])))
    print("Offline only. Remnawave was NOT modified.")


if __name__ == "__main__":
    main()
