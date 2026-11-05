# Garasu — единая ссылочная маршрутизация

**Одна политика Garasu, одна подписка Remnawave, разные нативные форматы.**
Все крупные наборы вынесены на GitHub, шаблоны панели остались компактными.

## Приоритеты
1. LAN, localhost, private IPv4/IPv6 → DIRECT
2. Реклама без четырёх исключённых API Ozon/Wildberries → REJECT
3. RKN, геоограниченные, YouTube, Discord, Telegram (и IP), GitHub, AI и blocked IP → VPN
4. Twitch Ads и Google Play → VPN **раньше** Twitch DIRECT и Push DIRECT
5. Apple, Microsoft, Twitch, Pinterest, игры, torrent trackers, системный Push/FCM → DIRECT
6. Российские банки, обычные RU домены и IP → DIRECT, после заблокированных исключений
7. Всё неизвестное → VPN; при отказе VPN узла не возвращаться автоматически в DIRECT

## Ссылочные наборы правил

- Mihomo и Stash: 35 бинарных MRS-провайдеров и 2 classical YAML из [release/mihomo/.mrs/](../release/mihomo/.mrs/), обновление каждые 21600 секунд. У Mihomo одна автоматическая группа Garasu, без селекторов.
- Clash/Premium: 37 удалённых **YAML** rule-providers из [release/clash/providers/](../release/clash/providers/), тоже каждые 21600 секунд. Старому Clash нельзя передавать Mihomo MRS, а оригинальное бесплатное ядро не поддерживает Premium rule-providers.
- sing-box 1.14: 37 удалённых бинарных SRS-наборов из [release/singbox/rules/](../release/singbox/rules/), кэш и обновление каждые 6 часов.
- Shadowrocket: ссылки DOMAIN-SET / RULE-SET на GitHub; личные узлы по-прежнему выдаёт отдельная подписка Remnawave.
- INCY/Happ: компактные заголовки единственного SSR и ссылки на Garasu geo/geosite.dat и geo/geoip.dat.
- Xray JSON: ссылки на бинарные категории geosite:garasu-ads, geosite:banned-ru, geoip:blocked-ru; Xray требует установки наших файлов GeoSite/GeoIP.

## Важно: холодный старт

**Удалённые наборы должны быть скачаны хотя бы раз.** Mihomo получает 35 MRS и 2 classical YAML через `proxy: DIRECT`, sing-box 1.14 получает 37 SRS через HTTP-клиент **без detour**. Выражение `detour: direct` у sing-box DNS приводило к фатальной ошибке при запуске и удалено. Изолированные холодные старты с неработающей тестовой нодой подтвердили загрузку всех 35/35 MRS, 2/2 classical YAML и 37/37 SRS из публичной ветки V2.

Если GitHub Raw недоступен напрямую и кеш пуст, правила могут не загрузиться. Интервал 21600 секунд в клиентах не гарантирует публикацию новых исходных списков — для этого требуется работающий авторизованный цикл сборки. Для проверки использовать `scripts/qa.py --cold-network`.

Публикация GitHub не обновляет уже сохранённые шаблоны в Remnawave.
Публикация обновлённых исходников и бинарных MRS/SRS выполняется `scripts/update_six_hourly.sh` после проверок; задача `automation/garasu-six-hourly.plist` имеет интервал 21600 секунд. Если Mac спит или сеть недоступна, обновление откладывается.
GitHub Actions не используются. Личные ключи серверов не хранятся в репозитории.

## Проверка

```bash
python3 scripts/sync_universal_routing.py --write
python3 scripts/sync_public_links.py --check
python3 scripts/qa.py --branch main --core /path/to/mihomo
```

QA проверяет 37 наборов и клиентские ссылки; офлайн-проверка Mihomo
использует **временную** локальную копию провайдеров. Матрица тестируется
в `tests/test_foreign_routes.py` и `tests/test_mobile_ru_matrix.py`.

[Выпуск и откат](release-checklist.md) · [Покрытие](../reports/routing-coverage.md)

## Матрица РФ (Garasu V2)

| Маршрут | Категории | Приоритет |
|---|---|---|
| DIRECT | LAN/private, банки/госуслуги, RU сервисы, Apple, Microsoft, Twitch, Pinterest, Push/FCM, Steam/Epic/Origin/Riot/EfT/Faceit, torrent trackers | После точечных RKN/geo-restricted исключений |
| PROXY | Заблокированные RU домены/IP, geo-restricted, YouTube, Discord, Telegram CIDR, GitHub, AI/Copilot, Google Play, Twitch Ads | До общего DIRECT |
| REJECT | Реклама, category-ads, win-spy | С известными Ozon/Wildberries исключениями |
| PROXY | Неизвестные ресурсы | Последнее правило |

База: [roscomvpn-routing](https://github.com/hydraponique/roscomvpn-routing),
[roscomvpn-geosite](https://github.com/hydraponique/roscomvpn-geosite) и
[DigneZzZ/routing](https://github.com/DigneZzZ/routing). DigneZzZ выбирает
для Google Play другой маршрут в некоторых профилях; Garasu использует
вариант RoscomVPN.

До проверки реального VPN-соединения активный профиль Mac не заменяется.
