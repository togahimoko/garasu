# Garasu Routing Canary — controlled test only

This directory contains **opt-in test candidates**, not replacement production
subscriptions. Existing `clients/*.yaml` and `clients/*.conf` must remain unchanged.
The test must preserve each subscriber's personal Remnawave node credentials.

## What changed

- Mihomo: RKN/domain/IP exceptions before Russian TLD and RU IP fallback;
  rule-provider downloads request `Garasu Auto`; DIRECT DNS uses system DNS.
- Stash: same RKN-before-RU priority and explicit `ru-ips` CIDR source.
- Shadowrocket: same priority and explicit remote RU IP rules; its managed
  `update-url` points to this *canary* file instead of production.
- sing-box 1.14+: explicit HTTP client for downloading remote rules over a
  selected proxy, with RU domain/IP exceptions after RKN.
- Default catch-all remains PROXY. There is **no automatic Moscow→Czech
  chaining** in these files, and no live server-side routing changes.

## Candidate files

| Client | Canary file |
|---|---|
| Mihomo / Clash Verge | `clients/canary/mihomo-remnawave.yaml` |
| Stash | `clients/canary/stash-remnawave.yaml` |
| Shadowrocket | `clients/canary/shadowrocket.conf` |
| sing-box 1.14+ | `clients/canary/singbox-remnawave-1.14.json` |

For testing Remnawave, **create new templates** with distinct names such as
`Garasu Canary Mihomo` and `Garasu Canary Stash`; do not overwrite or assign
the active production templates. Test selection must be limited to a dedicated
subscriber and must not match real customer User-Agent values. Preserve
Browser and XRAY_BASE64 fallback handling.

## Required acceptance matrix

For every actual client, test with a new installation (empty provider cache)
and after one successful update:
1. Personal subscription returns expected nodes and the original node expiry.
2. Rules download successfully from the client's network without a prior
   warmed cache. If a rule fetch fails, verify there is no unintended direct
   access to restricted destinations.
3. YouTube, Discord, ChatGPT and a specifically RKN-listed Russian domain
   use the expected PROXY route.
4. Russian banking, public services and normal `.ru` sites use DIRECT,
   including connections via RU IP without a recognized hostname.
5. DNS resolution, IPv6 handling, LAN access and the effect of blocking
   external DNS/UDP are checked separately.
6. With the exit node unavailable, no user credentials leak in fallback logs.
7. Disable the canary response and verify the existing production subscription
   still imports and operates with the prior config.

Test from a Russian residential ISP, a separate mobile operator and an
unrestricted external network where possible. A GitHub Actions runner cannot
substitute for those networks.

## Status and limitations

The GitHub check parses generated synthetic configs with real Mihomo and
sing-box binaries. Stash YAML is checked by a Mihomo-compatible parser.
Shadowrocket requires a real iOS device. None of those checks proves TCP
connectivity to a personal VLESS/REALITY server or a correct Remnawave
subscription response.

**Never switch all customers to canary automatically.**
