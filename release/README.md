# Релизные профили Garasu

Ветка `main` содержит стабильные исходники релизных конфигураций. Подписки и персональные VLESS-узлы выдаются **Remnawave**, а не хранятся в GitHub.

| Клиент | Шаблон |
| --- | --- |
| Mihomo / Clash Verge | [mihomo/config.yaml](mihomo/config.yaml) |
| Clash (классический) | [clash/config.yaml](clash/config.yaml) |
| Stash | [stash/config.yaml](stash/config.yaml) |
| sing-box | [singbox/config.json](singbox/config.json) |
| INCY | [incy/config.json](incy/config.json) |
| Happ | [happ/config.json](happ/config.json) |
| Shadowrocket | [shadowrocket/config.conf](shadowrocket/config.conf) |
| Xray JSON | [xray/config.json](xray/config.json) — необязательный |
| Remnawave SSR | [remnawave/](remnawave/) |

Mihomo и Stash получают 10 бинарных [MRS](mihomo/.mrs/) с обновлением каждые **6 часов**; sing-box получает 10 бинарных [SRS](singbox/rules/) каждые **6 часов**. Shadowrocket использует удалённые DOMAIN-SET/RULE-SET, INCY/Happ и Xray — [Garasu GeoSite/GeoIP](../geo/). Крупные списки не встраиваются в конфигурации.

**Не применять SSR вслепую:** сначала сверить наличие шаблонов, тип клиента и права на узлы в Remnawave. Коммит на GitHub не меняет живую конфигурацию сервера.

Документы: [архитектура](../docs/architecture.md) · [эксплуатация](../docs/operations.md) · [аудит](../docs/audit.md).

Классический **Clash** использует 37 отдельных YAML-провайдеров из [clash/providers/](clash/providers/) каждые 21600 секунд: MRS не поддерживается старым ядром. Установка одного маршрута Garasu не делает оригинальный Clash совместимым с VLESS/REALITY; для них используйте Mihomo.\n