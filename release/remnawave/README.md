# Garasu — правила ответов (Subscription Response Rules)

Один готовый файл для импорта: **[srr.json](srr.json)**. Правила проверяются в указанном порядке; первое совпадение определяет формат. Тестовых/Lite/Full-наборов нет.

## Пять шаблонов из меню

| User-Agent / запрос | Тип ответа | Шаблон в меню | Файл Garasu |
| --- | --- | --- | --- |
| Mihomo, Clash Verge Rev, FlClash, Koala Clash | `MIHOMO` | Mihomo → `Default` | [config.yaml](../mihomo/config.yaml) |
| Stash | `STASH` | Stash → `Default` | [config.yaml](../stash/config.yaml) |
| sing-box / Karing / SFA / SFI | `SINGBOX` | Singbox → `Default` | [config.json](../singbox/config.json) |
| Classic Clash / ClashX / Clash Premium | `CLASH` | Clash → `Default` | [config.yaml](../clash/config.yaml) |
| `garasu-xray-json/`, `xray/`, `xray-core/` (явный запрос) | `XRAY_JSON` | Xray JSON → `Default` | [config.json](../xray/config.json) |

**Важно:** `responseType` определяет формат, но не загружает шаблон из GitHub. Файлы Garasu нужно установить как `Default` **в соответствующих пяти разделах шаблонов**. Имя `Default` относится к каждому типу отдельно. Xray JSON включён для явных Xray-запросов, чтобы не ломать v2rayN/v2rayNG и другие приложения, ожидающие Base64; правило при явном запросе использует Xray JSON `Default` вместо шаблона хоста.

## Сохранённые отдельные ответы

- Браузер (заголовок `Accept: text/html`) → `BROWSER`, всегда первым.
- INCY → `XRAY_BASE64` и `autorouting` со ссылкой на [профиль маршрутов](../incy/config.json).
- Happ → `XRAY_BASE64` и существующий компактный `routing` (содержимое генерируется из [Happ](../happ/config.json)).
- Shadowrocket → `XRAY_BASE64`; отдельный [managed-config](../shadowrocket/config.conf) для маршрутов. Автоматический одновременный импорт нод и маршрутов не подтверждён.
- Неизвестное приложение (в том числе v2rayN без явного Xray JSON User-Agent) → `XRAY_BASE64`, последнее безусловное правило.

Между приложениями не должно быть случайных пересечений User-Agent: современный Clash Verge направляется к Mihomo, а `clash/`, `ClashX/`, `clash-premium/` — к Clash. Не надо принудительно переключать обычный Clash на формат Mihomo. Все оригинальные заголовки мобильной маршрутизации сохраняются.

## Проверка и применение

Сохраните существующий набор правил. Установите файлы Garasu как шаблоны `Default` в каждом из пяти типов, затем импортируйте **один** [srr.json](srr.json) в «Правила ответов». Проверьте соответствие User-Agent и ответа на действительной подписке: `MIHOMO`, `STASH`, `SINGBOX`, `CLASH`, `XRAY_JSON` (явный запрос), `BROWSER`, `XRAY_BASE64`, а также заголовки INCY/Happ. Только после успешного импорта можно считать маршрутизацию доступной устройствам.

Выпуск GitHub **не обновляет шаблоны и правила, уже сохранённые в интерфейсе**. Локальные тесты проверяют JSON, порядок и соответствие форматов, но не доказывают успешную загрузку личной подписки и VPN-трафика.
