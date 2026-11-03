#!/usr/bin/env python3
"""Prepare safe, credential-free configs for validation by real client cores.

The produced configs are not installable subscriptions. No service credentials
are loaded, and no live Remnawave configuration is ever changed.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil
import yaml

ROOT = Path(__file__).resolve().parents[1]


def prepare_mihomo(template, out, node_count=1):
    """Emulate 1..32 Remnawave subscribers' nodes without real credentials."""
    if not isinstance(node_count, int) or not 1 <= node_count <= 32:
        raise ValueError("node_count must be in 1..32")
    doc = yaml.safe_load((ROOT / template).read_text(encoding="utf-8"))
    if "proxies" not in doc or doc["proxies"] is not None:
        raise ValueError("Missing Remnawave top-level injection marker")
    names = [
        "garasu-ci-node" if node_count == 1 else "garasu-ci-node-" + str(i + 1)
        for i in range(node_count)
    ]
    doc["proxies"] = [
        {"name": name, "type": "http", "server": "127.0.0.1",
         "port": 1080 + i, "udp": False}
        for i, name in enumerate(names)
    ]
    for group in doc["proxy-groups"]:
        group.pop("remnawave", None)
        if group.get("proxies") is None:
            # Stash uses an injected direct membership list. Mihomo's
            # Garasu Auto is populated dynamically by include-all=true.
            group["proxies"] = names if group["name"] == "Garasu" else []
    assert doc["proxy-groups"]
    assert all(not isinstance(x.get("proxies"), type(None))
               for x in doc["proxy-groups"])
    # Use committed local providers to test parsing without network fluctuations.
    for name, provider in doc["rule-providers"].items():
        remote = provider["url"].split("/rules/", 1)[-1]
        source = ROOT / "rules" / remote
        if not source.exists():
            raise ValueError("Rule provider missing: " + remote)
        dst = out / "providers" / (name + source.suffix)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dst)
        provider["type"] = "file"
        provider["path"] = str(dst)
        provider.pop("url", None)
        provider.pop("interval", None)
        provider.pop("proxy", None)
    result = out / (Path(template).stem + ".ci.yaml")
    result.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return result


def prepare_singbox(template, out):
    doc = json.loads((ROOT / template).read_text(encoding="utf-8"))
    selectors = [x for x in doc["outbounds"] if x.get("type") == "selector"]
    if len(selectors) != 1 or selectors[0].get("outbounds") is not None:
        raise ValueError("Unexpected Remnawave sing-box node injection marker")
    selectors[0]["outbounds"] = ["garasu-ci-node"]
    doc["outbounds"].append({
        "type": "http",
        "tag": "garasu-ci-node",
        "server": "127.0.0.1",
        "server_port": 1080,
    })
    for provider in doc["route"]["rule_set"]:
        source = ROOT / "rules" / "singbox" / (
            provider["tag"].removeprefix("garasu-") + ".json"
        )
        if not source.exists():
            raise ValueError("Missing remote source rule set: " + str(source))
        provider["type"] = "local"
        provider["path"] = str(source)
        provider.pop("url", None)
        provider.pop("update_interval", None)
        provider.pop("http_client", None)
    output = out / (Path(template).stem + ".ci.json")
    output.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def prepare_xray(template, out):
    """Simulate documented Remnawave proxy-outbound injection for core parsing."""
    doc = json.loads((ROOT / template).read_text(encoding="utf-8"))
    remnawave = doc.pop("remnawave", None)
    if not remnawave or not remnawave.get("addVirtualHostAsOutbound"):
        raise ValueError("Xray template is not configured for virtual host injection")
    if any(item.get("tag") == "proxy" for item in doc.get("outbounds", [])):
        raise ValueError("Xray core fixture would shadow existing proxy outbound")
    # A no-network freedom outbound replaces an actual user node for -test.
    doc["outbounds"].append({"tag": "proxy", "protocol": "freedom"})
    output = out / (Path(template).stem + ".ci.json")
    output.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output-dir", required=True)
    a = p.parse_args()
    out = Path(a.output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    outputs = [
        prepare_mihomo("clients/mihomo-remnawave.yaml", out),
        prepare_mihomo("clients/stash-remnawave.yaml", out),
        prepare_singbox("clients/singbox-remnawave.json", out),
        prepare_singbox("clients/singbox-remnawave-1.14.json", out),
        prepare_xray("clients/xray-advanced-remnawave.json", out),
    ]
    for file in outputs:
        print(file)


if __name__ == "__main__":
    main()
