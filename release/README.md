# Release

Native configuration files for Remnawave subscriptions.

| Client | Configuration |
| --- | --- |
| Mihomo | [mihomo/config.yaml](mihomo/config.yaml) |
| Stash | [stash/config.yaml](stash/config.yaml) |
| sing-box | [singbox/config.json](singbox/config.json) |
| INCY | [incy/config.json](incy/config.json) |
| Happ | [happ/config.json](happ/config.json) |
| Shadowrocket | [shadowrocket/config.conf](shadowrocket/config.conf) |
| Xray (opt-in) | [xray/config.json](xray/config.json) |
| Remnawave | [remnawave/srr.json](remnawave/srr.json) and [remnawave/srr-test.json](remnawave/srr-test.json) |

Binary rule assets: [mihomo/.mrs/](mihomo/.mrs/). The same domain/IP MRS data is used by Mihomo and compatible Stash releases. Other clients use their native rule formats in `rules/` or `geo/`.

Remnawave must inject each subscriber's own nodes. Public templates contain no personal subscription credentials. A GitHub commit does not install templates into the Remnawave panel.

See [architecture](../docs/architecture.md) and [operations](../docs/operations.md) before deploying.
