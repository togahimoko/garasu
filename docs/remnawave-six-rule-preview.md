# Remnawave: preview for the supplied six-rule SRR export

The export supplied on 2026-11-04 contains Browser, MIHOMO, STASH,
SINGBOX, CLASH, and an unconditional XRAY_BASE64 fallback. It contains no
`responseModifications.subscriptionTemplate` fields. Therefore updating
GitHub alone does not select a Garasu template in the panel.

[`remnawave-six-rule-preview.json`](remnawave-six-rule-preview.json) is an
offline candidate generated from that export. Its six existing rules remain
unchanged and in their original order. Five additional rules immediately
after Browser respond only to `garasu-test-incy`, `garasu-test-happ`,
`garasu-test-mihomo`, `garasu-test-stash`, and `garasu-test-singbox` User-Agents.
The original XRAY_BASE64 fallback remains unconditional and last.

Before importing the preview in Remnawave, install three additional panel
templates named `Garasu Mihomo`, `Garasu Stash`, and `Garasu Singbox` from
the corresponding current `clients/` files. Confirm their names and formats
in the installed panel. Otherwise the preview rules that reference them may
return an error. Save a complete panel export for rollback. Use a dedicated
test subscription and verify its response format, inserted personal nodes,
rule downloads, and route decisions on each actual device. Do not use a
private subscription URL in this public repository.

The old sing-box regex `^sfa|sfi|sfm|sft|karing|singbox` also matches text
inside unrelated User-Agents such as `foo-karing`. The offline full-mode
builder corrects it to `^(?:sfa|sfi|sfm|sft|karing|singbox)`. The preview
keeps all existing conditions exactly as they are. The `CLASH` rule is also
left unchanged; plain Clash and Clash Verge can receive different response
types because Mihomo precedes CLASH in the supplied order.

The full six-rule candidate is deliberately not published as the active
panel configuration. Generate it from the original export after the preview
works with `python3 scripts/build_srr.py original.json full.json --mode full`.
That candidate selects the three named templates and retains Browser, CLASH,
and the unconditional fallback. The script writes files locally; it does not
modify the Remnawave panel.
