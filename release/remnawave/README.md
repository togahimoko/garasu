# Remnawave Garasu SRR (staging)

- srr.json: full response rules for Mihomo, Stash, sing-box, INCY, Happ,
  Shadowrocket, Xray JSON opt-in and general Base64 fallback.
- srr-canary.json: a minimal dedicated test User-Agent route added before the
  original production export; all existing customer response conditions stay
  unchanged.
- Mihomo template body: ../mihomo/config.yaml.
- Stash template: ../stash/config.yaml.
- Sing-box template: ../singbox/config.json.
- INCY and Happ native routing: ../incy/config.json and ../happ/config.json.

The response rule template names Garasu / Garasu Stash / Garasu Singbox
must match actual Remnawave template record names. The SRR JSON does not read
YAML directly from GitHub; template bodies must be installed separately through
the Remnawave Templates editor, and then assigned via these response rules.

INCY autorouting points to the staging hosted JSON. Happ routing is embedded
as Base64. Shadowrocket XRAY_BASE64 returns personal nodes and does not
automatically import the managed Shadowrocket routing file.

DO NOT paste the full srr.json into production until each native client has
been tested with personal subscription access, and a backup of current SRR is
stored. No live subscriptions or SSR rules have been modified by this commit.

For a non-disruptive test, create a **new** MIHOMO template named `Garasu` and import release/mihomo/config.yaml. Current production `Garasu Mihomo` remains unchanged until you activate and verify the new SSR mapping.
