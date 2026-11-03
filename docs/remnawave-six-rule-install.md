# Готовые файлы для Remnawave

Меню «Шаблоны» на скриншоте показывает **типы**. Внутри трёх нужных типов
создайте новые записи с точными названиями ниже. Содержимое каждой записи
уже подготовлено в репозитории:

| Раздел панели | Название новой записи | Содержимое |
| --- | --- | --- |
| Mihomo | `Garasu Mihomo` | [clients/mihomo-remnawave.yaml](../clients/mihomo-remnawave.yaml) |
| Stash | `Garasu Stash` | [clients/stash-remnawave.yaml](../clients/stash-remnawave.yaml) |
| Singbox | `Garasu Singbox` | [clients/singbox-remnawave-1.14.json](../clients/singbox-remnawave-1.14.json) |

Скопируйте **содержимое** файла в редактор соответствующего типа панели.
Это шаблоны: Remnawave добавляет в них персональные узлы при ответе на
подписку. У них нет собственной персональной ссылки. Три названия должны
совпасть с `responseModifications.subscriptionTemplate` в SRR побуквенно.
Клиентские списки в этих шаблонах обновляются с GitHub с интервалом 6 часов;
проверка доступности GitHub Raw из ваших сетей остаётся обязательной.

После сохранения шаблонов используйте
[тестовые правила ответов](remnawave-six-rule-preview.json). Они содержат
исходные шесть правил без изменений и пять правил для специальных
User-Agent. Проверить форму ответа тестовой подписки можно локально:

```bash
read -rs GARASU_SUBSCRIPTION_URL
export GARASU_SUBSCRIPTION_URL
python3 scripts/probe_subscription_delivery.py --clients preview_mihomo preview_stash preview_singbox preview_incy preview_happ
unset GARASU_SUBSCRIPTION_URL
```

Проба сообщает только код ответа и распознанный формат; она не выводит
ссылку или персональные узлы. После теста импорта и маршрутов в реальных
приложениях подготовлен [полный вариант шести правил](remnawave-six-rule-full.json).
Он переключает Mihomo, Stash и Singbox на три названных шаблона, исправляет
совпадение sing-box User-Agent и сохраняет Browser, CLASH и безусловный
XRAY_BASE64 fallback. Это файл для импорта в раздел «Правила ответов»,
а не замена содержимого отдельного клиентского шаблона.

Для раздела «Xray JSON» есть [отдельный шаблон](../clients/xray-advanced-remnawave.json).
Предоставленный SRR выдаёт `XRAY_BASE64` через резервное правило, поэтому
сам по себе он не выбирает Xray JSON. У раздела «Clash» своё правило `CLASH`;
оно сохранено и ждёт отдельной проверки совместимости с конкретным клиентом.

Файлы в GitHub не создают записи в вашей частной панели автоматически.
До переключения сохраните экспорт нынешних правил и исходных шаблонов для
восстановления. Адрес панели и доступ к ней в этой среде отсутствуют.
