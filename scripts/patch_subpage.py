#!/usr/bin/env python3
"""Add Garasu MAX buttons to an EXPORTED Subpage Builder JSON.
Never modifies original input, server subscriptions, or Remnawave settings.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANGS = {"en": "Install Garasu MAX", "ru": "Установить Garasu MAX",
         "zh": "安装 Garasu MAX", "fr": "Installer Garasu MAX",
         "fa": "نصب Garasu MAX"}
TITLE = {k: "Garasu MAX Routing" if k != "ru" else "Маршрутизация Garasu MAX" for k in LANGS}
TEXT = {k: "Install updated Garasu routing after adding your personal VPN subscription."
        if k != "ru" else
        "После подключения подписки установите обновляемые правила Garasu одним нажатием."
        for k in LANGS}

def patch(data, links):
    platforms = data.get("platforms")
    if not isinstance(platforms, dict):
        raise ValueError("Missing Remnawave platforms")
    name_to_link = {"Shadowrocket": links.get("shadowrocket"),
                    "INCY": links.get("incy"), "Happ": links.get("happ")}
    changed = []
    for platform, settings in platforms.items():
        if not isinstance(settings, dict):
            continue
        for app in settings.get("apps", []):
            name = app.get("name")
            if name not in name_to_link or not name_to_link[name]:
                continue
            blocks = app.get("blocks")
            if not isinstance(blocks, list):
                continue
            blocks[:] = [block for block in blocks if not (
                isinstance(block, dict) and isinstance(block.get("title"), dict)
                and block["title"].get("en") == "Garasu MAX Routing"
            )]
            blocks.append({
                "title": TITLE,
                "description": TEXT,
                "svgIconKey": "CloudDownload",
                "svgIconColor": "cyan",
                "buttons": [{"type": "external", "link": name_to_link[name],
                             "text": LANGS, "svgIconKey": "ExternalLink"}],
            })
            changed.append(platform + "/" + name)
    if not changed:
        raise ValueError("No supported app cards found in Subpage Builder export")
    return data, changed

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", help="original Subpage Builder JSON")
    parser.add_argument("destination", help="NEW output file; never overwrite source")
    args = parser.parse_args()
    src, dst = Path(args.source), Path(args.destination)
    if src.resolve() == dst.resolve():
        parser.error("source and destination must differ")
    obj = json.loads(src.read_text(encoding="utf-8"))
    links = json.loads((ROOT / "install/links.json").read_text(encoding="utf-8"))
    result, changed = patch(obj, links)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Garasu routing buttons added:", ", ".join(changed))
    print("Original preserved:", src)

if __name__ == "__main__":
    main()
