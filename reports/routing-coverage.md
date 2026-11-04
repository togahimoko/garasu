# Garasu — фактическое покрытие маршрутизации

Upstream: `82d104cde92b271f545e1f61a61b1acd079e0aa7`.

**Ограничение:** статическая проверка доменов, не моделирует DNS-разрешение, IP, TUN, UDP и реальное соединение.

| Набор | Записей | Назначение | Mihomo: не так | Stash | Shadowrocket | sing-box |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| rkn-domains | 75306 | PROXY | 0 | 0 | 0 | 0 |
| youtube | 176 | PROXY | 0 | 0 | 0 | 0 |
| discord | 28 | PROXY | 0 | 0 | 0 | 0 |
| ai | 215 | PROXY | 0 | 0 | 0 | 0 |
| crypto | 96 | PROXY | 0 | 0 | 0 | 0 |
| proxy | 154 | PROXY | 0 | 0 | 0 | 0 |
| ads | 1221 | REJECT | 117 | 117 | 117 | 117 |
| games | 117 | DIRECT | 116 | 116 | 116 | 116 |
| direct | 3284 | DIRECT | 3206 | 3206 | 3111 | 3206 |

## Наборы, загружаемые, но не используемые для маршрутизации

- Mihomo: direct, games
- Stash: direct, games
- Shadowrocket: direct, games
- sing-box: direct, games

## Примеры расхождений в Mihomo

### direct — 3206 расхождений
- `1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.ip6.arpa`: PROXY (MATCH)
- `10.in-addr.arpa`: PROXY (MATCH)
- `100.100.in-addr.arpa`: PROXY (MATCH)
- `100.51.198.in-addr.arpa`: PROXY (MATCH)
- `100beatscheap.com`: PROXY (MATCH)
- `101.100.in-addr.arpa`: PROXY (MATCH)
- `102.100.in-addr.arpa`: PROXY (MATCH)
- `103.100.in-addr.arpa`: PROXY (MATCH)

### games — 116 расхождений
- `3lateral.com`: PROXY (MATCH)
- `a4e8s8k3.map2.ssl.hwcdn.net`: PROXY (MATCH)
- `artstation.com`: PROXY (MATCH)
- `artstationmedia.com`: PROXY (MATCH)
- `battlebreakers.com`: PROXY (MATCH)
- `capturingreality.com`: PROXY (MATCH)
- `client-update.queniuqe.com`: PROXY (MATCH)
- `cloudsync-prod.s3.amazonaws.com`: PROXY (MATCH)

### ads — 117 расхождений
- `a.ads2.msn.com`: PROXY (SET:rkn-domains)
- `ac3.msn.com`: PROXY (SET:rkn-domains)
- `ad.browser.qq.com`: PROXY (SET:rkn-domains)
- `ad.qq.com`: PROXY (SET:rkn-domains)
- `ad.qun.qq.com`: PROXY (SET:rkn-domains)
- `ad.weixin.qq.com`: PROXY (SET:rkn-domains)
- `adeventtracker.spotify.com`: PROXY (SET:rkn-domains)
- `adfilter.imtt.qq.com`: PROXY (SET:rkn-domains)

## Отказоустойчивость

В активном шаблоне Mihomo широкое правило `.ru → DIRECT` не связано с
успешностью загрузки полного списка RKN. Изолированный нативный тест
отдельно подтвердил: с 13 пустыми remote rule-provider'ами ядро стартует,
а суффиксное DIRECT-правило остаётся активным. Это риск обхода исключений,
но не доказательство фактической отправки конкретного сайта напрямую.

## Ограничения межклиентной эквивалентности

У INCY/Happ/Xray используются бинарные GeoSite/GeoIP, не проверяемые этим
доменным анализатором. sing-box использует `resolve` до IP-правил;
пробные доменные результаты для российских TLD нельзя считать полными.

Расхождений для проверенных нероссийских доменов между четырьмя
семействами: **95**.

Машинный отчёт: [routing-coverage.json](routing-coverage.json).
