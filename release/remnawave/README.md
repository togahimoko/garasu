# Subscription Response Rules

`srr.json` is the complete client-format selection policy. `srr-test.json` adds a dedicated test User-Agent for the new Mihomo template without deliberately changing normal client mappings.

## Template names

- MIHOMO: `Garasu` — `../mihomo/config.yaml`
- STASH: `Garasu Stash` — `../stash/config.yaml`
- SINGBOX: `Garasu Singbox` — `../singbox/config.json`
- XRAY_JSON opt-in: `Garasu Xray JSON` — where explicitly supported.

These records must be created separately in Remnawave. The SSR only **selects** existing named templates and does not fetch their contents from GitHub.

## Other clients

INCY receives personal XRAY_BASE64 nodes and an `autorouting` header pointing to `../incy/config.json`. Happ receives personal nodes plus embedded native routing. Shadowrocket receives personal XRAY_BASE64 nodes; its managed routing file must be imported separately.

## Activation

Export the actual active SSR and all template bodies first. Test `srr-test.json` with a dedicated subscription and User-Agent `garasu-test-mihomo/1.0`. Compare its normal-client rules with the real current configuration: the test file originated from a repository export and may differ from panel state. Verify every client type and a fallback before applying the full SSR. Restore the backed-up SSR and templates on failure.

Do not overwrite templates used by paying customers for a test. No server ports, nodes or Xray settings need changing.
