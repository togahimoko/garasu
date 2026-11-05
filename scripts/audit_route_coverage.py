#!/usr/bin/env python3
"""Static cross-client domain policy audit (not a network/VPN probe)."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DOMAIN_SETS = ("rkn-domains", "youtube", "discord", "ai", "crypto",
               "proxy", "ads", "games", "direct")
EXPECTED = {name: ("REJECT" if name == "ads" else
                   "DIRECT" if name in ("games", "direct") else "PROXY")
            for name in DOMAIN_SETS}
SHADOW_URL = re.compile(r"/rules/([a-z0-9-]+)\.list")


def get_sets(root: Path) -> dict[str, set[str]]:
    result = {}
    for name in DOMAIN_SETS:
        values = set()
        for row in (root / "rules" / (name + ".list")).read_text().splitlines():
            line = row.strip().lower()
            if not line or line.startswith("#"):
                continue
            if not line.startswith("+.") or line.count(".") < 2:
                raise ValueError("Invalid domain in set " + name)
            values.add(line[2:])
        if name == "ads":
            exclusions = json.loads((root / "policy/universal.json").read_text())["ad_exempt_domains"]
            if not set(exclusions) <= values:
                raise ValueError("Stale advertising exceptions")
            values -= set(exclusions)
        result[name] = values
    return result


def suffixes(name: str):
    parts = name.lower().rstrip(".").split(".")
    return (".".join(parts[i:]) for i in range(len(parts)))


def matches(name: str, entries: set[str]) -> bool:
    return any(x in entries for x in suffixes(name))


def target(tag: str) -> str:
    if tag.lower() == "direct":
        return "DIRECT"
    if tag in ("REJECT", "REJECT-DROP"):
        return "REJECT"
    if tag in ("Garasu", "PROXY", "→ Remnawave"):
        return "PROXY"
    raise ValueError("Unsupported route target: " + tag)


def yaml_route(domain: str, rules: list[str],
               data: dict[str, set[str]]) -> tuple[str, str]:
    for raw in rules:
        parts = raw.split(",")
        kind = parts[0]
        if kind == "DOMAIN-SUFFIX" and parts[1] in suffixes(domain):
            return target(parts[2]), "SUFFIX:" + parts[1]
        if kind == "RULE-SET" and parts[1] in data and matches(domain, data[parts[1]]):
            return target(parts[2]), "SET:" + parts[1]
        if kind in ("MATCH", "FINAL"):
            return target(parts[1]), kind
    raise ValueError("No fallback rule: " + domain)


def shadow_rules(root: Path) -> list[str]:
    """Normalize all 35 separate remote Shadowrocket providers for static audit."""
    from scripts.sync_universal_routing import PROVIDERS_BASE, provider_sets, load_policy
    expected=provider_sets(load_policy(root))
    entries=[row.strip() for row in
             (root/"release/shadowrocket/config.conf").read_text().split("[Rule]",1)[1].splitlines()
             if row.strip() and not row.lstrip().startswith("#")]
    rules,found=[],[]
    for line in entries:
        parts=line.split(",")
        if parts[0]=="DOMAIN-SET":
            host,action=parts[1],parts[2]
            if not host.startswith(PROVIDERS_BASE) or not host.endswith(".txt"):
                raise ValueError("Unexpected Shadowrocket domain provider")
            name=host.removeprefix(PROVIDERS_BASE).removesuffix(".txt")
            if name not in expected or expected[name][0]!="domain":
                raise ValueError("Invalid Shadowrocket domain category "+name)
            rules.append("RULE-SET,"+name+","+
                         ("REJECT" if action=="REJECT" else
                          "DIRECT" if action=="DIRECT" else "Garasu"))
            found.append(name)
        elif parts[0]=="RULE-SET":
            import re
            hit=re.search(r"/(?:rules|release/shadowrocket/providers)/(rkn-ips|proxy-ips|ru-ips|direct-ips|telegram-ips|ru-geoblock-patterns|github-patterns)\.list$",parts[1])
            if not hit:raise ValueError("Unexpected remote Shadowrocket IP source: "+parts[1])
            name=hit.group(1)
            if name not in expected and name!="ru-ips":
                raise ValueError("Unexpected Shadowrocket IP category "+name)
            action=parts[2]
            rules.append("RULE-SET,"+name+","+
                         ("DIRECT" if action=="DIRECT" else "Garasu"))
            found.append(name)
        elif line.startswith("FINAL,"):
            rules.append("MATCH,Garasu")
        else:
            rules.append(line)
    if set(found)!=set(expected) or len(found)!=len(expected):
        raise ValueError("Shadowrocket missing/duplicated providers: "+repr(set(expected)-set(found)))
    if rules.index("RULE-SET,rkn-domains,Garasu") >= rules.index("DOMAIN-SUFFIX,ru,DIRECT"):
        raise ValueError("Shadowrocket RU DIRECT bypasses RKN")
    return rules


def singbox_route(domain: str, items: list[dict],
                  data: dict[str, set[str]]) -> tuple[str, str]:
    """Domain-only approximation. Resolve/IP rules require native tests."""
    for item in items:
        action = item.get("action", "route")
        if action == "resolve" or item.get("ip_cidr") or item.get("ip_is_private"):
            continue
        if item.get("protocol") == "dns":
            continue
        reason = ""
        if item.get("domain_suffix") and any(s in suffixes(domain)
                                             for s in item["domain_suffix"]):
            reason = "SUFFIX"
        for src in item.get("rule_set", []):
            name = src.removeprefix("garasu-")
            if name in data and matches(domain, data[name]):
                reason = "SET:" + name
                break
        if not reason:
            continue
        return ("REJECT" if action == "reject" else
                target(item["outbound"])), reason
    return "PROXY", "FINAL"


def audit(root: Path) -> dict:
    data = get_sets(root)
    mihomo = yaml.safe_load((root / "release/mihomo/config.yaml").read_text())
    stash = yaml.safe_load((root / "release/stash/config.yaml").read_text())
    clash = yaml.safe_load((root / "release/clash/config.yaml").read_text())
    sing = json.loads((root / "release/singbox/config.json").read_text())
    source = json.loads((root / "install/manifest.json").read_text())
    configs = {"Mihomo": mihomo["rules"], "Stash": stash["rules"],
               "Clash": clash["rules"], "Shadowrocket": shadow_rules(root)}
    used = {}
    for name, rules in configs.items():
        used[name] = sorted({line.split(",")[1] for line in rules
                             if line.startswith("RULE-SET,") and
                             line.split(",")[1] in data})
    used["sing-box"] = sorted({name.removeprefix("garasu-")
                               for item in sing["route"]["rules"]
                               for name in item.get("rule_set", [])
                               if name.removeprefix("garasu-") in data})
    clients = ("Mihomo", "Stash", "Clash", "Shadowrocket", "sing-box")
    def route(client: str, name: str) -> tuple[str, str]:
        if client == "sing-box":
            return singbox_route(name, sing["route"]["rules"], data)
        return yaml_route(name, configs[client], data)
    entries = {}
    for category, domains in data.items():
        outcome = {}
        for client in clients:
            counter = Counter()
            reasons = Counter()
            samples = []
            for domain in sorted(domains):
                action, reason = route(client, domain)
                counter[action] += 1
                if action != EXPECTED[category]:
                    reasons[reason] += 1
                    if len(samples) < 10:
                        samples.append({"domain": domain, "actual": action,
                                        "matched": reason})
            outcome[client] = {"actions": dict(counter),
                               "deviations": sum(reasons.values()),
                               "reasons": dict(reasons),
                               "samples": samples}
        entries[category] = {"count": len(domains),
                             "declared_action": EXPECTED[category],
                             "clients": outcome}
    comparisons = []
    sample = set()
    for category in ("rkn-domains", "direct", "games", "ads", "proxy", "youtube"):
        sample.update(data[category])
    for name in sorted(sample):
        if name.endswith((".ru", ".su", ".xn--p1ai")):
            continue  # sing-box may resolve first, then match an IP.
        actions = {client: route(client, name)[0] for client in clients}
        if len(set(actions.values())) > 1:
            comparisons.append({"domain": name, "actions": actions})
    return {
        "schema_version": 1,
        "upstream_revision": source["upstream_revision"],
        "scope": "static domain-only first-match, excluding resolved IP, process, DNS state, QUIC, TUN and runtime availability",
        "included": used,
        "unused": {name: sorted(set(data) - set(values)) for name, values in used.items()},
        "domains": entries,
        "non_ru_disagreements": len(comparisons),
        "non_ru_examples": comparisons[:16],
        "ru_direct_without_provider_guard": (
            "DOMAIN-SUFFIX,ru,DIRECT" in mihomo["rules"]
            and mihomo["rule-providers"]["rkn-domains"]["type"] == "http"),
    }


def markdown(result: dict) -> str:
    header = [
        "# Garasu — фактическое покрытие маршрутизации",
        "",
        "Upstream: `" + result["upstream_revision"] + "`.",
        "",
        "**Ограничение:** статическая проверка доменов, не моделирует DNS-разрешение, IP, TUN, UDP и реальное соединение.",
        "",
        "| Набор | Записей | Назначение | Mihomo: не так | Stash | Clash | Shadowrocket | sing-box |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, item in result["domains"].items():
        header.append("| " + name + " | " + str(item["count"]) + " | " +
                      item["declared_action"] + " | " + " | ".join(
                          str(item["clients"][client]["deviations"]) for client in
                          ("Mihomo", "Stash", "Clash", "Shadowrocket", "sing-box")) + " |")
    header.extend(["", "## Наборы, загружаемые, но не используемые для маршрутизации", ""])
    for client, names in result["unused"].items():
        header.append("- " + client + ": " + (", ".join(names) or "—"))
    header += ["", "## Примеры расхождений в Mihomo", ""]
    for category in ("direct", "games", "ads"):
        info = result["domains"][category]["clients"]["Mihomo"]
        header.append("### " + category + " — " + str(info["deviations"]) + " расхождений")
        for item in info["samples"][:8]:
            header.append("- `" + item["domain"] + "`: " +
                          item["actual"] + " (" + item["matched"] + ")")
        header.append("")
    header.extend([
        "## Отказоустойчивость",
        "",
        "В Garasu российские домены и IP идут напрямую только ПОСЛЕ",
        "удалённых списков RKN-исключений, относящихся к DIRECT.",
        "Холодный старт требует успешной загрузки либо кэша всех провайдеров.",
        "При недоступном GitHub без кэша маршрутизация не считается проверенной.",
        "На мобильных INCY/Happ используется согласованная пара GeoSite/GeoIP;",
        "её доступность и работу на конкретном устройстве необходимо проверять.",
        "",
        "## Ограничения межклиентной эквивалентности",
        "",
        "У INCY/Happ/Xray используются бинарные GeoSite/GeoIP, не проверяемые этим",
        "доменным анализатором. sing-box использует `resolve` до IP-правил;",
        "пробные доменные результаты для российских TLD нельзя считать полными.",
        "",
        "Расхождений для проверенных нероссийских доменов между четырьмя",
        "семействами: **" + str(result["non_ru_disagreements"]) + "**.",
        "",
        "Машинный отчёт: [routing-coverage.json](routing-coverage.json).",
        "",
    ])
    return "\n".join(header)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--write", action="store_true")
    group.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = audit(args.root.resolve())
    outputs = {"reports/routing-coverage.json": json.dumps(result, indent=2, ensure_ascii=False) + "\n",
               "reports/routing-coverage.md": markdown(result)}
    for filename, contents in outputs.items():
        path = args.root.resolve() / filename
        if args.write:
            path.write_text(contents, encoding="utf-8")
            print("CREATED", filename)
        elif args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != contents:
                raise ValueError("Stale routing audit: " + filename)
            print("VERIFIED", filename)
        else:
            print("PREVIEW", filename, len(contents))
    print("DOMAIN_CATEGORIES", len(result["domains"]),
          "CROSS_CLIENT_DIFFERENCES", result["non_ru_disagreements"])


if __name__ == "__main__":
    main()
