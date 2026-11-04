# Garasu — Compatibility

Garasu maintains one MAX routing policy and exports engine-specific rule sets for **any number of Remnawave subscriber nodes**. **Publication and CI checks do not prove that a particular device's VPN connection works.**

| Engine / client | Main resource | Integration |
| --- | --- | --- |
| Shadowrocket | `clients/shadowrocket.conf` | Managed routing candidate; personal node subscription and device VPN separate; app import unverified |
| INCY | `clients/incy.json` | `autorouting` candidate header or direct import link; app import unverified |
| Happ | `clients/happ.json` | `routing` candidate import with separate GeoIP/GeoSite; app import unverified |
| Mihomo, Clash Verge, FlClash, Clash-named Mihomo-compatible clients | `clients/mihomo-remnawave.yaml` | MIHOMO template with Remnawave node injection; generic `clash/1.0` uses the same template via SRR, subject to actual client core support |
| Stash | `clients/stash-remnawave.yaml` | Template with Remnawave node injection |
| Modern sing-box and compatible clients | `clients/singbox-remnawave.json` | Template using 13 remotely updated JSON rule sets |
| Xray-core advanced | `clients/xray-advanced-remnawave.json` | **Opt-in:** requires Remnawave virtual-host injection and Garasu GeoIP/GeoSite |
| Surge and Loon | `rules/surge/*.list` | Candidate integration instructions in [native routing candidates](native-routing-candidates.md); app import unverified |
| Quantumult X | `rules/quantumultx/*.list` | Candidate resource link and final-rule instructions in [native routing candidates](native-routing-candidates.md); app import unverified |
| Legacy Clash / old sing-box | Not claimed compatible | The old Clash core cannot load VLESS/REALITY nodes, regardless of a YAML wrapper; [Clash compatibility details](remnawave-clash-compat.md) |

Automatic node selection varies by client: Mihomo canary uses URLTest, Stash canary uses URLTest, sing-box stable uses a manual selector. For supported and unverified failover behavior see [multi-node reliability](multi-node-reliability.md).

## MAX routing order

1. LAN/private addresses: DIRECT.
2. Blocked Russian domains/IP, YouTube, Discord, AI, and special proxy categories: VPN.
3. Advertising/tracking domains: REJECT when the engine supports it.
4. Russian suffixes: DIRECT after blocked exceptions. Broad foreign game and service categories are excluded.
5. Other RU IPs: DIRECT after all blocked-IP exceptions.
6. Unmatched traffic: VPN.

Russian suffix fallback requires the complete validated blocked snapshot. No automatic ban on UDP/443.

## Source and update process

Source sets are updated approximately every six hours. Generated formats:

- Mihomo and Stash: `rules/*.list` (domain) / `rules/*.cidr` (IP).
- Shadowrocket: domain sets + `rules/*.list` (Shadowrocket IP format).
- Modern sing-box: `rules/singbox/*.json` (source rule-set version 3).
- Surge and Loon: `rules/surge/*.list` (policy-independent RULE-SET syntax).
- Quantumult X: `rules/quantumultx/*.list` (native filter syntax).
- Xray-family clients: `geo/geoip.dat` and `geo/geosite.dat`.

## Usage limitations

Templates must not be assigned to all subscriptions before confirming actual server response and client import. Installing a remote rule set does not automatically transfer a personal VPN server or set the client's final routing policy.

Quantumult X requires a configured proxy policy and an appropriate final rule. Surge and Loon rules need an existing policy group selected by the user. No VPN server credentials are stored here.

The Xray advanced template depends on the Remnawave virtual host model and is **not** a universal replacement for all Xray subscriptions.
