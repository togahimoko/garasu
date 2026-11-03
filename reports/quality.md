# Garasu MAX — качество наборов правил

Отчёт формируется из одной проверенной версии данных.
Пересечения не удаляются: конкретные PROXY-правила имеют приоритет
перед общими DIRECT-суффиксами. Это диагностические показатели.

Идентификатор снимка: b54c463fb0dbfc3283ee67a80edb68edec0a99894ac342b7bd4a1f6d55c7437f

| Доменные категории | Записей |
|---|---:|
| rkn-domains | 21989 |
| youtube | 176 |
| discord | 28 |
| ai | 215 |
| crypto | 96 |
| proxy | 154 |
| ads | 1221 |
| games | 117 |
| direct | 3283 |

| IP-категории | Всего | IPv4 | IPv6 |
|---|---:|---:|---:|
| rkn-ips | 1141 | 1141 | 0 |
| proxy-ips | 6 | 6 | 0 |
| direct-ips | 28 | 16 | 12 |
| ru-ips | 25157 | 12987 | 12170 |

## Правила с разными действиями

| PROXY | Общий DIRECT | Количество | Примеры |
|---|---|---:|---|
| rkn-domains | games | 3 | blaper.artstation.com / artstation.com, digitalfly.artstation.com / artstation.com, tr.rbxcdn.com / rbxcdn.com |
| rkn-domains | direct | 58 | alko-scherbinka.at.ua / at.ua, antago.at.ua / at.ua, anwap.ru.com / ru.com |
| ai | direct | 7 | coderabbit.gallery.vsassets.io / vsassets.io, copilot.microsoft.com / microsoft.com, openaiapi-site.azureedge.net / azureedge.net |
| proxy | direct | 25 | ads.twitch.tv / twitch.tv, copilotprodattachments.blob.core.windows.net / windows.net, gql.twitch.tv / twitch.tv |

## IP-исключения

| Приоритет | Количество |
|---|---:|
| rkn-ips -> direct-ips | 0 |
| rkn-ips -> ru-ips | 1141 |
| proxy-ips -> direct-ips | 0 |
| proxy-ips -> ru-ips | 6 |

## Точные конфликты доменов

Точных совпадений между категориями с разными действиями нет.

Расширенный машинный отчёт: quality.json.
