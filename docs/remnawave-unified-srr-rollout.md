# Garasu Unified — safe Remnawave SRR migration

**Scope:** the eight-rule Subscription Response Rules (SRR) export. Changes are generated offline. Neither GitHub nor this tool can update the live Remnawave panel.

## What is wrong in the existing panel export

The original INCY response points at clients/incy.json and still allows broad foreign DIRECT. Happ embeds the same old Garasu MAX routing JSON in its routing header. The three server-side template references (Garasu Mihomo, Garasu Stash, Garasu Singbox) are only *names*: merging new GitHub files did not update those template contents in Remnawave. The original sing-box User-Agent regex has an unanchored alternation (`^sfa|sfi|sfm|sft|karing|singbox`).

## Staging procedure

1. **Keep a complete backup of the original eight-rule SRR JSON**, and copies of the three existing template bodies. Do not paste a private subscription URL, node UUID or API token into GitHub.
2. In Remnawave, create **three additional templates** (do not overwrite the currently served ones):
   - **Garasu Unified Mihomo** from `clients/unified/mihomo-remnawave.yaml` (template type MIHOMO)
   - **Garasu Unified Stash** from `clients/unified/stash-remnawave.yaml` (template type STASH)
   - **Garasu Unified Singbox** from `clients/unified/singbox-remnawave-1.14.json` (template type SINGBOX)
   
   Use the verified repository contents at commit `2fb95bafa8e674b232187c6cdcd39aefd6131465`, not a moving link. The experimental `mihomo-ru-tld-verified.yaml` is **not** the default template.
3. Use the offline converter on a local SRR export file:
   
   ```bash
   python3 scripts/prepare_unified_srr.py existing-srr.json garasu-preview.json \
     --mode preview \
     --ref 2fb95bafa8e674b232187c6cdcd39aefd6131465 \
     --mihomo-template "Garasu Unified Mihomo" \
     --stash-template "Garasu Unified Stash" \
     --singbox-template "Garasu Unified Singbox"
   ```
   
   The **preview** keeps the eight original customer rules completely unchanged and inserts five special rules after Browser. Only test clients presenting the UAs `garasu-test-incy`, `garasu-test-happ`, `garasu-test-mihomo`, `garasu-test-stash`, and `garasu-test-singbox` match the new policies. The test UA prefix must be supplied by an actual client or a controlled test request.
4. Import the preview into Remnawave through its own UI only after verifying it is valid for the installed version. Test with a dedicated test account and check actual generated responses, node injection, update status, and whether client import supports the required routing header. Then inspect VPN routing on actual devices. The GitHub unit fixtures are not panel integration tests.
5. Generate the **full** switch only after those tests pass:
   
   ```bash
   python3 scripts/prepare_unified_srr.py existing-srr.json garasu-full.json \
     --mode full \
     --ref 2fb95bafa8e674b232187c6cdcd39aefd6131465 \
     --mihomo-template "Garasu Unified Mihomo" \
     --stash-template "Garasu Unified Stash" \
     --singbox-template "Garasu Unified Singbox"
   ```
   
   Full mode preserves all eight rule types, the existing user-agent conditions (except corrected sing-box regex), Browser and the unconditional XRAY_BASE64 fallback, and switches INCY and Happ routing headers plus the three named templates. It changes **routing only**: all personal nodes remain supplied by Remnawave. No user credentials enter this public repository.
6. If anything fails, immediately **restore the original SRR export** (and keep the original three named templates untouched). This rolls back the SRR routing switch; devices may cache imported profiles and need a refresh/reimport.

## Important limitations

- The full candidate refers to the **new three names**. If those template records do not exist in Remnawave, **do not import it**. The converter cannot validate server-side template existence.
- The dedicated `CLASH` response rule remains unchanged and does not automatically become unified Mihomo. A separate panel-compatible Clash fallback or native test is necessary before claiming every client migrated.
- INCY uses an immutable link to `clients/unified/incy.json`. Happ embeds the exact same unified policy as base64 in its routing header. Their native import behavior is **not confirmed** by Python tests.
- This does not prove subscription-domain availability, SNI reachability or DNS behavior from Russian ISPs. Test panel response status and client refresh separately.
- Never overwrite an existing source file with the generated JSON. The CLI creates destination with exclusive mode and refuses to overwrite.
