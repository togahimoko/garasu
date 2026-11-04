# Готовые файлы для Remnawave

Меню «Шаблоны» на скриншоте показывает **типы**. Внутри четырёх нужных типов
создайте новые записи с точными названиями ниже. Содержимое каждой записи
уже подготовлено в репозитории:

| Раздел панели | Название новой записи | Содержимое |
| --- | --- | --- |
| Mihomo | `Garasu Mihomo` | [clients/mihomo-remnawave.yaml](../clients/mihomo-remnawave.yaml) |
| Stash | `Garasu Stash` | [clients/stash-remnawave.yaml](../clients/stash-remnawave.yaml) |
| Singbox | `Garasu Singbox` | [clients/singbox-remnawave-1.14.json](../clients/singbox-remnawave-1.14.json) |
| Xray JSON | `Garasu Xray JSON` | [clients/xray-json-garasu-remnawave.json](../clients/xray-json-garasu-remnawave.json) |

Скопируйте **содержимое** файла в редактор соответствующего типа панели.
Это шаблоны: Remnawave добавляет в них персональные узлы при ответе на
подписку. У них нет собственной персональной ссылки. Четыре названия должны
совпасть с `responseModifications.subscriptionTemplate` в SRR побуквенно;
для Xray JSON действует то же правило.
Клиентские списки в этих шаблонах обновляются с GitHub с интервалом 6 часов;
проверка доступности GitHub Raw из ваших сетей остаётся обязательной.

После сохранения шаблонов используйте
[тестовые правила ответов](remnawave-six-rule-preview.json). Они содержат
исходные шесть правил без изменений и шесть правил для специальных
User-Agent. Проверить форму ответа тестовой подписки можно локально:

```bash
read -rs GARASU_SUBSCRIPTION_URL
export GARASU_SUBSCRIPTION_URL
python3 scripts/probe_subscription_delivery.py --clients preview_mihomo preview_stash preview_singbox preview_incy preview_happ preview_xray
unset GARASU_SUBSCRIPTION_URL
```

Проба сообщает только код ответа и распознанный формат; она не выводит
ссылку или персональные узлы. После теста импорта и маршрутов в реальных
приложениях подготовлен [полный вариант шести правил](remnawave-six-rule-full.json).
Он переключает Mihomo, Stash и Singbox на три названных шаблона, исправляет
совпадение sing-box User-Agent и добавляет **отдельное** правило Xray JSON
только для User-Agent `garasu-xray-json`. Дополнительные правила Happ и INCY
выдают персональные узлы в формате XRAY_BASE64 **вместе с** заголовками
`routing` и `autorouting`, которые передают маршруты Garasu. Browser, CLASH и
безусловный XRAY_BASE64 fallback сохранены. Это файл для импорта в раздел «Правила ответов»,
а не замена содержимого отдельного клиентского шаблона.

Новый Xray JSON шаблон сохраняет DNS, FakeDNS и дополнительные входы из
предоставленного примера, добавляет приоритет исключений Garasu и поле
`geodata.cron` с интервалом 6 часов. Сам Xray core не выполняет это обновление:
его должен поддерживать конкретный клиент. Проверен Xray 26.10.21 с синтетическим узлом;
нативное приложение и установленную версию панели ещё надо проверить.
Клиенты, которые не отправляют явный Xray JSON User-Agent, по-прежнему
попадают в обычный `XRAY_BASE64` fallback. У раздела «Clash» своё правило `CLASH`;
оно сохранено и ждёт отдельной проверки совместимости с конкретным клиентом.

Файлы в GitHub не создают записи в вашей частной панели автоматически.
До переключения сохраните экспорт нынешних правил и исходных шаблонов для
восстановления. Адрес панели и доступ к ней в этой среде отсутствуют.
