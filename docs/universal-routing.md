# Garasu — единая ссылочная маршрутизация

**Одна политика Garasu, одна подписка Remnawave, разные нативные форматы.**
Все крупные наборы вынесены на GitHub, шаблоны панели остались компактными.

## Приоритеты
1. LAN, localhost, private IPv4/IPv6 → DIRECT
2. Реклама без четырёх исключённых API Ozon/Wildberries → REJECT
3. RKN, YouTube, Discord, AI, crypto, proxy и заблокированные IP → VPN
4. Обычные российские домены и IP → DIRECT
5. Всё остальное, включая зарубежный трафик → VPN

## Ссылочные наборы правил

- Mihomo и Stash: 10 удалённых бинарных MRS-провайдеров из [release/mihomo/.mrs/](../release/mihomo/.mrs/), обновление каждые 21600 секунд. У Mihomo одна автоматическая группа Garasu, без селекторов.
- Clash/Premium: 10 удалённых **YAML** rule-providers из [release/clash/providers/](../release/clash/providers/), тоже каждые 21600 секунд. Старому Clash нельзя передавать Mihomo MRS, а оригинальное бесплатное ядро не поддерживает Premium rule-providers.
- sing-box 1.14: 10 удалённых бинарных SRS-наборов из [release/singbox/rules/](../release/singbox/rules/), кэш и обновление каждые 6 часов.
- Shadowrocket: ссылки DOMAIN-SET / RULE-SET на GitHub; личные узлы по-прежнему выдаёт отдельная подписка Remnawave.
- INCY/Happ: компактные заголовки единственного SSR и ссылки на Garasu geo/geosite.dat и geo/geoip.dat.
- Xray JSON: ссылки на бинарные категории geosite:garasu-ads, geosite:banned-ru, geoip:blocked-ru; Xray требует установки наших файлов GeoSite/GeoIP.

## Важно: холодный старт

**Удалённые наборы должны быть скачаны хотя бы раз.** После удачной загрузки
кеш уменьшает зависимость от GitHub, но первый импорт при недоступном GitHub
или VPN может не получить нужные правила. Нельзя обещать корректный
RU DIRECT до получения RKN-исключений. Отдельно проверяются импорт,
загрузка всех rule-sets, кеш, DNS, подключение личных узлов и недоступность GitHub.

Публикация GitHub не обновляет уже сохранённые шаблоны в Remnawave.
Публикация обновлённых исходников и бинарных MRS/SRS выполняется `scripts/update_six_hourly.sh` после проверок; задача `automation/garasu-six-hourly.plist` имеет интервал 21600 секунд. Если Mac спит или сеть недоступна, обновление откладывается.
GitHub Actions не используются. Личные ключи серверов не хранятся в репозитории.

## Проверка

```bash
python3 scripts/sync_universal_routing.py --write
python3 scripts/sync_public_links.py --check
python3 scripts/qa.py --branch main --core /path/to/mihomo
```

QA проверяет содержимое 20 rule-set файлов и клиентские ссылки, а
для офлайн-проверки Mihomo использует **временную** локальную копию
содержимого провайдеров, не меняя опубликованную конфигурацию.

[Выпуск и откат](release-checklist.md) · [Покрытие](../reports/routing-coverage.md)
