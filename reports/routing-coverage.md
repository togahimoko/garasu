# Garasu — фактическое покрытие маршрутизации

Upstream: `82d104cde92b271f545e1f61a61b1acd079e0aa7`.

**Ограничение:** статическая проверка доменов, не моделирует DNS-разрешение, IP, TUN, UDP и реальное соединение.

| Набор | Записей | Назначение | Mihomo: не так | Stash | Clash | Shadowrocket | sing-box |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| rkn-domains | 75306 | PROXY | 4 | 4 | 4 | 4 | 4 |
| youtube | 176 | PROXY | 0 | 0 | 0 | 0 | 0 |
| discord | 28 | PROXY | 0 | 0 | 0 | 0 | 0 |
| ai | 215 | PROXY | 0 | 0 | 0 | 0 | 0 |
| crypto | 96 | PROXY | 0 | 0 | 0 | 0 | 0 |
| proxy | 154 | PROXY | 0 | 0 | 0 | 0 | 0 |
| ads | 1217 | REJECT | 0 | 0 | 0 | 0 | 0 |
| games | 117 | DIRECT | 116 | 116 | 116 | 116 | 116 |
| direct | 3284 | DIRECT | 3110 | 3110 | 3110 | 3110 | 3110 |

## Наборы, загружаемые, но не используемые для маршрутизации

- Mihomo: direct, games
- Stash: direct, games
- Clash: direct, games
- Shadowrocket: direct, games
- sing-box: direct, games

## Примеры расхождений в Mihomo

### direct — 3110 расхождений
- `100beatscheap.com`: PROXY (MATCH)
- `12diasdepresentesdeitunes.com`: PROXY (MATCH)
- `12diasderegalosdeitunes.cl`: PROXY (MATCH)
- `12diasderegalosdeitunes.co`: PROXY (MATCH)
- `12diasderegalosdeitunes.co.cr`: PROXY (MATCH)
- `12diasderegalosdeitunes.co.ni`: PROXY (MATCH)
- `12diasderegalosdeitunes.co.ve`: PROXY (MATCH)
- `12diasderegalosdeitunes.com`: PROXY (MATCH)

### games — 116 расхождений
- `3lateral.com`: PROXY (MATCH)
- `a4e8s8k3.map2.ssl.hwcdn.net`: PROXY (MATCH)
- `artstation.com`: PROXY (MATCH)
- `artstationmedia.com`: PROXY (MATCH)
- `battlebreakers.com`: PROXY (MATCH)
- `capturingreality.com`: PROXY (MATCH)
- `client-update.queniuqe.com`: PROXY (MATCH)
- `cloudsync-prod.s3.amazonaws.com`: PROXY (MATCH)

### ads — 0 расхождений

## Отказоустойчивость

В Garasu российские домены и IP идут напрямую только ПОСЛЕ
удалённых списков RKN-исключений, относящихся к DIRECT.
Холодный старт требует успешной загрузки либо кэша всех провайдеров.
При недоступном GitHub без кэша маршрутизация не считается проверенной.
На мобильных INCY/Happ используется согласованная пара GeoSite/GeoIP;
её доступность и работу на конкретном устройстве необходимо проверять.

## Ограничения межклиентной эквивалентности

У INCY/Happ/Xray используются бинарные GeoSite/GeoIP, не проверяемые этим
доменным анализатором. sing-box использует `resolve` до IP-правил;
пробные доменные результаты для российских TLD нельзя считать полными.

Расхождений для проверенных нероссийских доменов между четырьмя
семействами: **0**.

Машинный отчёт: [routing-coverage.json](routing-coverage.json).
