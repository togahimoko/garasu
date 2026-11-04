# Remnawave: единый рабочий профиль Garasu

Единственный Subscription Response Rules: **[srr.json](srr.json)**. Тестового SSR и Lite/Full-версий нет. Правила хранятся по URL на GitHub, а не внутри шаблонов.

## Одна подписка, нативные форматы

- Mihomo / Clash Verge Rev — MIHOMO и шаблон Default: [config.yaml](../mihomo/config.yaml).
- Stash — STASH и шаблон Default: [config.yaml](../stash/config.yaml).
- sing-box / Karing — SINGBOX и шаблон Default: [config.json](../singbox/config.json).
- INCY — XRAY_BASE64 с личными нодами и заголовком autorouting для [конфигурации](../incy/config.json).
- Happ — XRAY_BASE64 с личными нодами и компактным заголовком routing для [конфигурации](../happ/config.json).
- Shadowrocket — XRAY_BASE64 с личными нодами, отдельный [managed-config](../shadowrocket/config.conf) для правил. Единый автоматический импорт нод и правил не подтверждён.
- Неизвестный User-Agent — XRAY_BASE64. Дополнительный XRAY_JSON отключён до установки отдельного шаблона в панели.

## Внедрение и откат

1. Сохранить текущий SSR и установленные шаблоны. Не изменять ноды, тарифы, права доступа и серверы.
2. Сверить шаблоны Default для MIHOMO/STASH/SINGBOX с файлами release/.
3. Сверить на существующей авторизованной подписке реальные User-Agent, форматы, routing/autorouting и персональные узлы.
4. После реального импорта и проверки применить один srr.json; при проблеме восстановить исходные настройки.

**Публикация GitHub не заменяет шаблоны Remnawave.** Офлайн-тесты не гарантируют работу на российских операторах.
