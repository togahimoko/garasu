# Garasu MRS — compiled native rule sets

These are **real binary Mihomo MRS assets**, compiled with Mihomo Meta v1.19.33.
They are not renamed text lists. Mihomo and modern Stash support MRS for
`behavior: domain` and `behavior: ipcidr` only.

## Source and integrity

- Source: `rules/*.list` (domain) and `rules/*.cidr` (IP-CIDR).
- Source revision: `c7c17d2d5d57d2f50aa63a90b85abdaede36fa68`.
- Exact file sizes and SHA256 hashes: [manifest.json](manifest.json).
- Native conversion: `mihomo convert-ruleset domain|ipcidr text INPUT OUTPUT.mrs`.
- Total binary size of all 13 assets: **762,413 bytes**.
- Verified: all 13 downloaded successfully from this branch, SHA256 verified,
  recompiled to identical hashes, and loaded as HTTP rule-providers by a separate
  Mihomo 1.19.33 process (not a paying subscriber's VPN session).
- In that runtime the RKN domain list exposed 75,306 rules and the RKN IP list
  exposed 25,391 rules.

## Update procedure (deliberately manual for staging)

1. Review updated source lists and keep a consistent committed source revision.
2. Run `python3 scripts/build_mrs.py --core /path/to/mihomo --output /tmp/garasu-next-mrs --source-commit <revision>`
   from the repository root.
3. Validate the emitted manifest SHA256 values and run a native Mihomo runtime
   test with a temporary home directory, **never a live user's configuration**.
4. Publish the complete binary set and manifest as one coherent release.
5. Change the candidate profile URLs only after release files are reachable.
6. Test Remnawave injection and import on a dedicated canary subscriber.

**Important:** Updating a `.list` or `.cidr` source does not automatically
update its compiled `.mrs`. No GitHub Actions, VPS cron or live rollout was
configured for this staging revision. Do not advertise it as an automatically
regenerated binary release yet.

Other engines (INCY, Happ/Xray, sing-box, Shadowrocket, Surge, Quantumult X)
consume **their own native formats**, not Mihomo MRS. The client generator or
subscription response must select the appropriate native policy.

References:
- Mihomo providers: https://wiki.metacubex.one/en/config/rule-providers/
- Stash rule sets: https://stash.wiki/en/rules/rule-set
