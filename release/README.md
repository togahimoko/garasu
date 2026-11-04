# Garasu / release

One clean release hierarchy, with app-native configuration files. No dated
directories, duplicated release trees or personal subscriber credentials.

* mihomo/config.yaml — Remnawave Mihomo template; its native compiled MRS
  data is kept in mihomo/.mrs/ (13 files with SHA256 manifest).
* stash/config.yaml — Stash template using the same MRS assets.
* incy/config.json and happ/config.json — their own native routing profiles.
* shadowrocket/config.conf — managed routing profile; server subscription separate.
* singbox/config.json — sing-box 1.14 template with Remnawave node injection.
* xray/config.json — opt-in advanced Xray virtual-host template.

The shared source lists remain under rules/ in the repository. MRS binaries are
built using release/mihomo/build.py, which consumes these source lists.

This is a staging branch. The URLs in the new templates intentionally reference
staging/release/... . When the release is validated and promoted to main, pin
those references to the approved commit or main. Changing files on GitHub does
not update Remnawave's server-stored templates.

Steal, 443, Xray, existing SRR, paying subscriptions and TUN are unchanged.
Native client import and subscription injection still require canary testing.
