# Релизные профили Garasu

Ветка `main` содержит стабильные исходники релизных конфигураций. Подписки и персональные VLESS-узлы выдаются **Remnawave**, а не хранятся в GitHub.

| Клиент | Шаблон |
| --- | --- |
| Mihomo / Clash Verge | [mihomo/config.yaml](mihomo/config.yaml) |
| Stash | [stash/config.yaml](stash/config.yaml) |
| sing-box | [singbox/config.json](singbox/config.json) |
| INCY | [incy/config.json](incy/config.json) |
| Happ | [happ/config.json](happ/config.json) |
| Shadowrocket | [shadowrocket/config.conf](shadowrocket/config.conf) |
| Xray JSON | [xray/config.json](xray/config.json) — необязательный |
| Remnawave SSR | [remnawave/](remnawave/) |

Mihomo и Stash используют встроенные inline-наборы RKN/RU, чтобы первый запуск не зависел от сети. [13 бинарных MRS](mihomo/.mrs/) остаются опубликованными воспроизводимыми артефактами для совместимости. Shadowrocket и sing-box также используют встроенную маршрутизацию; INCY/Happ и Xray — [Garasu GeoSite/GeoIP](../geo/).

**Не применять SSR вслепую:** сначала сверить наличие шаблонов, тип клиента и права на узлы в Remnawave. Коммит на GitHub не меняет живую конфигурацию сервера.

Документы: [архитектура](../docs/architecture.md) · [эксплуатация](../docs/operations.md) · [аудит](../docs/audit.md).
