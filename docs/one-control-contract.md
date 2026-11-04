# Garasu One Control — staging contract (2026-11-04)

**NOT LIVE.** All candidate templates are in clients/one-control/. Production SRR, Remnawave templates, Steal:443, paid users and Xray are unchanged.

## One-policy UX by native client

| Client | Visible policy | Behind the scenes |
| --- | --- | --- |
| Mihomo / Clash Verge / FlClash | Garasu | Hidden Garasu Auto URL-test, includes all subscriber nodes |
| Stash | Garasu | Single native url-test group, empty-pool REJECT |
| sing-box 1.14 | Remnawave-injected virtual group | Automatic URL-test, placeholder tag remains "→ Remnawave" for injection compatibility |
| INCY / Happ | Routing profile named Garasu | Native domain/IP routing JSON, app-specific server selection |
| Shadowrocket | Native PROXY target | Managed routing; personal node subscription separately |
| Xray advanced | Virtual-host proxy | Optional Xray JSON; no universal auto-failover claim |

A single YAML file cannot control different cores. A single Remnawave subscription endpoint can select separate native templates via response rules. UI visibility and automatic node failover are limited by each app.

## Shared behavior

1. LAN/private and local domains direct. Do not intercept local network.
2. Russian blocked exceptions, YouTube, Discord, Telegram and other explicit proxy lists: VPN.
3. Ads: REJECT where supported.
4. Russian domains/IPs DIRECT after blocked exceptions, using existing published Garasu rules. Incomplete blocked lists can make broad RU DIRECT too permissive. The separate Unified v1 strict policy is still pending full blocked-snapshot cold-start verification.
5. Unmatched traffic: VPN, **never** silent foreign DIRECT fallback.
6. Do not force TUN state, UDP/443 blocking or IPv6 hijacking in a Remnawave subscription.
7. Preserve all Remnawave node injection markers and personal subscription entitlements.

## Specific changes compared with existing production

- Mihomo: Garasu Auto hidden. Rule-providers fetch over DIRECT rather than requiring the same potentially broken VPN; this breaks the bootstrap cycle. Failed DIRECT GitHub requests still need cached rule sets; no universal mirror fallback is claimed. Only Garasu is visible.
- Stash: single native Garasu URL-test group preserved, with REJECT when zero subscribers' nodes are injected.
- INCY/Happ: identical routing policies named Garasu; personal node delivery remains Remnawave's job.
- Shadowrocket: native PROXY routing, not a complete VLESS subscription. Managed update URL points to the staging branch only. Switch to an immutable promoted release before production rollout.
- sing-box: switch one injected selector to urltest, move rule-set HTTP fetching and DNS bootstrap to direct, and delete contradictory private-IP-to-VPN rules. Keep the Remnawave injection placeholder tag; a literal Garasu UI label is not proven.
- Xray advanced: delete contradictory route sending private-IP answers over VPN. Virtual host injection required; not a replacement for XRAY_BASE64.

## Canary release checklist (must precede any live switch)

1. Run: python3 -m unittest tests.test_one_control_contract
2. Generate Mihomo subscriptions with synthetic 0, 1, 2 and 5 nodes and validate with real Mihomo core. Bare template with Remnawave anchors is not a standalone subscription.
3. Generate sing-box 1.14 profiles with actual Remnawave injection. Confirm URL-test and native sing-box check; zero-node output must be rejected, not converted into DIRECT.
4. Create NEW Remnawave template names, test with a dedicated canary subscriber and manually identifiable client UA. Do not change existing response rules yet.
5. Test cold cache, rule downloads when VPN is down, DNS, node failover, IPv4/IPv6, Wi-Fi/mobile switching and effective routing in each actual app.
6. Verify no cross-subscriber node leakage and keep full production template + SRR backups for rollback.
7. Only after tests succeed, promote with staged SRR. GitHub files do not automatically update Remnawave's stored templates.
8. No GitHub Actions, automatic deployments, changes to Steal, port 443, existing nodes or paid customers.

## Diagnostic separation

The Steal server accepted the same VLESS/REALITY profile through temporary SSH transport during earlier tests, while the normal ISP path intermittently timed out. A routing template cannot guarantee delivery when the underlying TCP path is filtered or broken.

## References

- Remnawave Mihomo injection: https://docs.rw/guides/templates/mihomo/
- Remnawave format and SRR: https://docs.rw/learn-en/templates/
- Stash native hidden groups: https://stash.wiki/en/proxy-protocols/proxy-groups
- INCY autorouting: https://docs.incy.cc/en/autorouting/
- sing-box configuration: https://sing-box.sagernet.org/configuration/
