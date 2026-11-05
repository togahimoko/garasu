# Garasu

**Маршрутизация для VPN-клиентов на базе Remnawave.** Нативные шаблоны, единые наборы правил и воспроизводимые проверки — без хранения личных VPN-ключей в репозитории.

## Как это работает

Remnawave выдаёт пользователю **его собственные серверы** и подходящий формат подписки. Garasu задаёт правила для Mihomo, Stash, sing-box, INCY, Happ, Shadowrocket и Xray.

Для Mihomo предусмотрена одна автоматическая группа **Garasu** (`url-test`). При одной ноде используется она, при нескольких автоматически выбирается доступная. Ручных переключателей по сайтам нет.

**Garasu использует одну политику раздельной маршрутизации по принципу RoscomVPN:** локальная сеть и обычные российские сервисы — DIRECT; заблокированные российские ресурсы и весь остальной зарубежный трафик — VPN; реклама — REJECT. В Mihomo/Stash/sing-box/Shadowrocket крупные списки загружаются по ссылкам GitHub, кешируются после загрузки. Первый запуск без доступных источников правил не считается проверенным. Для INCY/Happ используется наш GeoSite/GeoIP. Никаких Lite/Full. [Правила, ограничения и проверки](docs/universal-routing.md).

## Что находится в репозитории

| Каталог | Назначение |
| --- | --- |
| [release/](release/) | Нативные шаблоны клиентов и правила выдачи Remnawave |
| [release/mihomo/.mrs/](release/mihomo/.mrs/) | 13 бинарных MRS и манифест SHA-256 |
| [release/clash/](release/clash/) | Отдельный Clash/Premium YAML и 10 удалённых YAML-наборов (21600 с) |
| [release/providers/](release/providers/) | 10 исходных текстовых списков для компиляции MRS |
| [release/singbox/rules/](release/singbox/rules/) | 10 бинарных SRS и исходные JSON для sing-box |
| [rules/](rules/) | Исходные домены, CIDR и экспортные форматы |
| [geo/](geo/) | GeoIP и GeoSite для Xray-совместимых клиентов |
| [scripts/](scripts/) | Обновление источников, сборка, диагностика и аудит |
| [tests/](tests/) | Контрактные проверки конфигураций, маршрутов и выдачи |
| [clients/](clients/) · [install/](install/) | Совместимость со старыми опубликованными ссылками |
| [reports/](reports/) | Отчёты проверки наборов правил |

## Пять шаблонов подписки

| Тип в интерфейсе | Канонический файл |
| --- | --- |
| Xray JSON | [release/xray/config.json](release/xray/config.json) |
| Mihomo | [release/mihomo/config.yaml](release/mihomo/config.yaml) |
| Stash | [release/stash/config.yaml](release/stash/config.yaml) |
| Singbox | [release/singbox/config.json](release/singbox/config.json) |
| Clash | [release/clash/config.yaml](release/clash/config.yaml) |

У каждого типа отдельный файл. Одна автоматическая группа Garasu для доступных нод в Clash/Mihomo/Stash/Singbox; крупные правила хранятся только в удалённых наборах. **Classic Clash Premium** использует YAML-провайдеры; формат MRS и VLESS/REALITY — для Mihomo. Xray JSON использует локальную пару GeoSite/GeoIP: автоматическое скачивание этих файлов самим JSON-конфигом не обеспечивается.

## Проверка качества

**Одна команда** запускает полный офлайн-контроль: 62 файла манифеста, 20 ссылочных наборов, 13 MRS, контракт SSR, тесты и сканирование секретов.

```bash
python3 -m pip install 'PyYAML>=6,<7'
python3 scripts/qa.py --branch main
```

С установленным Mihomo проверяются воспроизводимая пересборка MRS и четыре нативные конфигурации с синтетическими узлами:

```bash
python3 scripts/qa.py --branch main --core /path/to/mihomo
```

При изменении списков сначала пересобрать источники и бинарные наборы: `scripts/sync_universal_routing.py --write`, затем `scripts/build_binary_assets.py --write` с путями к двум ядрам; после этого запустить полный QA.

Отдельно проверяется **реальный холодный запуск без работающего VPN**: Mihomo и sing-box запускаются с тестовой недоступной нодой и должны независимо скачать 10/10 MRS и 10/10 SRS:

```bash
python3 scripts/qa.py --branch main --core /path/to/mihomo --singbox-core /path/to/sing-box --cold-network
```

Обычный QA работает без интернета; `--cold-network` — необязательная сетевая проверка. Интервал 21600 секунд означает повторную загрузку опубликованных файлов клиентом, а не гарантию регулярной публикации свежих списков.

После публикации — сравнение с публичным GitHub Raw:

```bash
python3 scripts/probe_release_assets.py --branch main
```

Эти команды не используют личные подписки и не изменяют VPN-серверы. [Подробный чек-лист](docs/release-checklist.md).

## Выпуск и безопасность

**`main` — опубликованные проверенные файлы. `dev` — разработка.** Удалённые MRS/SRS загружаются клиентами с интервалом **21600 секунд (6 часов)**. Для публикации новых исходников и бинарных наборов без GitHub Actions добавлены `scripts/update_six_hourly.sh` и macOS `launchd` с таким же интервалом. Расписание исполняется, только когда Mac работает.

Пароли, UUID пользователей, закрытые ключи REALITY и реальные подписки не должны попадать в GitHub. Уже опубликованные пути в `clients/` и `install/` сохраняются для совместимости.

## Документация

- [Порядок выпуска](docs/release-checklist.md): контроль качества, публикация и откат.
- [Участие в проекте](CONTRIBUTING.md): требования к изменениям.
- [Безопасность](SECURITY.md): работа с ключами и сообщение об уязвимости.
- [GitHub Issues](https://github.com/togahimoko/garasu/issues/new/choose): структурированные отчёты без личных данных.
- [Настройки GitHub](docs/github-maintenance.md): защита main, права и проверка метаданных.
[Архитектура](docs/architecture.md) · [Эксплуатация и выпуск](docs/operations.md) · [Технический аудит](docs/audit.md) · [Источники данных](SOURCES.md)

**[Исследование маршрутизации в РФ](docs/russia-routing-audit.md)** — риски холодного запуска, приоритеты DIRECT/PROXY/REJECT, DNS, полнота наборов и сравнение клиентских форматов.


## Единый профиль Garasu

[Политика universal](policy/universal.json) · [Генератор восьми клиентских конфигураций](scripts/sync_universal_routing.py) · [Нативный smoke-тест](scripts/smoke_universal_mihomo.py). Перед выпуском обязательно проверять импорт каждого клиента и реальную выдачу Remnawave.
