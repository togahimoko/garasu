# Garasu Routing — MAX

Маршрутизация **Garasu** для Shadowrocket, Happ, INCY и Mihomo / Clash Verge. VPN-серверы, тарифы, UUID и ключи **не размещаются** в этом публичном репозитории: их выдаёт Remnawave.

## Система

- `clients/shadowrocket.conf`: отдельная подписка на правила Shadowrocket; персональные серверы импортируются отдельно.
- `clients/incy.json`: автообновляемая маршрутизация INCY через `incy://autorouting/onadd/https://raw.githubusercontent.com/togahimoko/garasu/main/clients/incy.json`.
- `clients/happ.json`: полный профиль Happ; GeoIP/GeoSite загружаются из Garasu. Сам JSON Happ получает при импорте или обновлении персональной подписки, **не** по URL autorouting.
- `clients/mihomo-remnawave.yaml`: шаблон Remnawave для Mihomo / Clash Verge. В нём Remnawave подставляет узлы пользователей.
- `rules/` и `geo/`: автоматически собираемые публичные датасеты.
- `install/links.json`: установочные ссылки.
- `scripts/refresh.py`: сборка, проверка и публикация только целого валидного набора данных.
- `.github/workflows/refresh.yml`: план каждые 6 часов + ручной запуск.

## Маршрутизация

1. Локальные адреса — напрямую.
2. Блокировки РКН, YouTube, Discord, AI, Telegram, GitHub и зарубежные ресурсы — VPN.
3. Известные рекламные и трекинговые домены — REJECT.
4. Российские доступные сервисы, банки, госсервисы и некоторые игры — напрямую.
5. Всё неизвестное — VPN.

Нет глобального UDP/443 REJECT и нет принудительного DIRECT для всех `*.ru`, который мог бы сломать обход блокировок.

## Ввод в эксплуатацию

1. Открыть [Actions](https://github.com/togahimoko/garasu/actions) и запустить **Garasu — refresh routing**.
2. Если GitHub выдаёт ошибку `Resource not accessible by integration` при push, включить в Settings → Actions → General → Workflow permissions → **Read and write permissions**.
3. Проверить наличие `rules/*.list`, `rules/*.cidr`, `geo/*.dat`, `install/manifest.json` и успешный run.
4. Проверить прямые HTTPS-адреса с iPhone и устройства пользователя в РФ. GitHub Raw не всегда доступен из РФ; при необходимости потребуется собственное HTTPS-зеркало.
5. Только после тестов добавить ссылки в Remnawave Subpage Builder. **Не заменять текущие Subscription Response Rules без отдельного тестирования.**

Файл `docs/remnawave.md` содержит инструкции для каждого клиента.

## Ограничения

- GitHub Actions — периодический сборщик, а не круглосуточный монитор; GitHub может задержать scheduled-задания.
- INCY умеет автоматически обновлять сам профиль и геобазы.
- У Happ обновление полного JSON-профиля привязано к повторному импорту/обновлению подписки; GeoIP/GeoSite могут обновляться отдельно.
- Shadowrocket и Mihomo обновляют конфигурацию/списки по настройкам клиента.
- Успешная сборка не гарантирует работоспособность VPN-ноды и не заменяет тест в конкретном приложении.

## Источники

Списки, исходные права и происхождение см. в `SOURCES.md`. **Garasu — бренд собственных конфигураций и их доставки; источники открыто указаны.** Не включайте в репозиторий токены подписок, конфиги нод и приватные данные пользователей.
