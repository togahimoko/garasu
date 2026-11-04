# Remnawave: preview for the supplied six-rule SRR export

The export supplied on 2026-11-04 contains Browser, MIHOMO, STASH,
SINGBOX, CLASH, and an unconditional XRAY_BASE64 fallback. It contains no
`responseModifications.subscriptionTemplate` fields. Therefore updating
GitHub alone does not select a Garasu template in the panel.

[`remnawave-six-rule-preview.json`](remnawave-six-rule-preview.json) is an
offline candidate generated from that export. Its six existing rules remain
unchanged and in their original order. Six additional rules immediately
after Browser respond only to `garasu-test-incy`, `garasu-test-happ`,
`garasu-test-mihomo`, `garasu-test-stash`, `garasu-test-singbox`, and
`garasu-test-xray` User-Agents.
The original XRAY_BASE64 fallback remains unconditional and last.

Before importing the preview in Remnawave, install three additional panel
templates named `Garasu Mihomo`, `Garasu Stash`, `Garasu Singbox`, and
`Garasu Xray JSON` from
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

The [full candidate](remnawave-six-rule-full.json) is available for
review, but has not been imported into the panel. It selects the three named
templates, adds dedicated Happ/INCY BASE64 responses with routing headers and
one explicit `garasu-xray-json` Xray JSON rule, and retains Browser, CLASH,
and the unconditional BASE64 fallback. To
regenerate it from the original export, run
`python3 scripts/build_srr.py original.json full.json --mode full --with-xray-json --with-mobile-routing`. See the
[installation guide](remnawave-six-rule-install.md) for the template files and
preview probe. The script writes files locally; it does not modify the panel.
