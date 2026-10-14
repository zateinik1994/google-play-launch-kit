# Optional Google Ads REST CLI

`shared/google_ads.py` реализует два сценария: выгрузку показателей App campaigns для одной выбранной conversion action и создание Android App campaign с целью in-app action и target CPA. Создание всегда оставляет **Campaign, AdGroup и AdGroupAd в состоянии PAUSED**. Активации в CLI нет.

Скрипт использует официальные `GoogleAdsService.Search` и `GoogleAdsService.Mutate`, JSON-поля REST и реальные ресурсы Google Ads. Это отдельный API и отдельные разрешения: доступ к Google Play Console не дает доступ к Google Ads.

## Доступ и версия

Offline-команды требуют Python 3.10+, сетевые — дополнительную зависимость:

```bash
python3 -m pip install "google-auth[requests]>=2"
```

Нужны Google Ads API, developer token с подходящим access level и учетная запись с доступом к выбранному Ads customer. Credentials загружаются через ADC со scope `https://www.googleapis.com/auth/adwords`. Для service account можно задать `GOOGLE_APPLICATION_CREDENTIALS`; его email должен иметь нужный доступ в Google Ads. User ADC должны быть заранее получены с OAuth scope `adwords`: уже выданные credentials с другим scope не расширяются автоматически. См. [OAuth overview](https://developers.google.com/google-ads/api/docs/oauth/overview) и [service account workflow](https://developers.google.com/google-ads/api/docs/oauth/service-accounts).

Передайте developer token через `GOOGLE_ADS_DEVELOPER_TOKEN`, а при доступе через manager account — его ID через `GOOGLE_ADS_LOGIN_CUSTOMER_ID`. Client customer передается отдельным `--customer`; CLI принимает 10 цифр с дефисами или без. Credentials и токены не входят в конфиги, планы, CSV и receipts.

Для каждой команды требуется явный `--api-version`, например `v25`, соответствующий доступной версии Google. Скрипт не выбирает версию сам и не переключается на другую при ошибке. Перед работой сверьте [supported versions и sunset dates](https://developers.google.com/google-ads/api/docs/sunset-dates). Схема ниже проверена по v25 14 октября 2026 года; будущие версии могут требовать изменений.

## Конфигурация кампании

Пример: [examples/data/google-ads-create.json](../examples/data/google-ads-create.json). Это демонстрационные ID, package name и суммы; замените их своими значениями.

Файл задает название, Android package, валюту аккаунта, `daily_budget_micros`, `target_cpa_micros`, существующую `conversion_action`, списки ресурсов стран и языков, 1–5 headlines и 1–5 descriptions. Используются полные имена: `customers/1234567890/conversionActions/987654321`, `geoTargetConstants/2840`, `languageConstants/1000`. CLI не угадывает conversion action по названию и не создает tracking. Выбранное действие должно уже измерять нужное событие приложения и быть пригодным для оптимизации кампании.

Этот API-config отличается от `shared.cli ads-plan` brief: там суммы в единицах валюты, страны/языки — человекочитаемые коды, action может быть описанием события. В API-config преобразуйте суммы в целые micros, выберите настоящие ресурсы и задайте имя/declaration; простое переименование ключей не проверяет country/language IDs или событие. Планировщик `ads-plan` не выполняет такое преобразование.

До создания зафиксируйте в папке приложения customer, package, timezone, событие и его counting/attribution settings, состояние импорта, источник CPA-экономики, сроки, общий предел эксперимента и владельца остановки. Эти planning-only сведения не добавляйте в API JSON: неизвестные поля отвергаются. CLI не реализует end date, lifetime budget или автоматическое прекращение расхода по общему cap.

Бюджет и target CPA — целые числа в micros валюты аккаунта: `5000000` означает 5 единиц указанной валюты. Перед remote validate клиент читает реальную валюту customer и отказывается работать при несовпадении. Дневной бюджет Google Ads — средний дневной бюджет, а не универсальный жесткий лимит каждого дня. См. [CampaignBudget](https://developers.google.com/google-ads/api/reference/rpc/v25/CampaignBudget).

Локальная проверка текста использует пределы 30 для headlines и 90 для descriptions, учитывает широкие CJK-символы как два и запрещает управляющие символы. Проверка Google может учитывать дополнительные условия и политики. Язык текста должен соответствовать таргетингу: CLI не переводит assets. См. [App campaign asset requirements](https://support.google.com/google-ads/answer/17091671).

`contains_eu_political_advertising: false` — явная декларация владельца. Этот сценарий поддерживает только такие кампании; значение не подставляется автоматически.

## План и validateOnly

```bash
python3 -m shared.google_ads plan \
  --customer 1234567890 --api-version v25 \
  --config examples/data/google-ads-create.json

python3 -m shared.google_ads validate \
  --customer 1234567890 --api-version v25 \
  --config my-campaign.json --live
```

`plan`, `validate` без `--live` и `create` без `--live` работают полностью offline. Они возвращают `status: offline-plan` и готовый REST payload с `validateOnly: true`, но не обращаются к Google.

`validate --live` читает валюту аккаунта, проверяет, что geo resources существуют, активны и имеют `targetType: Country`, затем вызывает `googleAds:mutate` с `validateOnly: true`. Этот запрос проверяет операции и не создает ресурсы. Успешный ответ дает `status: validated-only`; он не означает policy approval или достижимость заданного CPA. Поведение [validateOnly](https://developers.google.com/google-ads/api/docs/mutating/bulk-mutate) определяет Google.

Существование и compatibility conversion/language resources проверяет серверный mutate. Bundled validate не читает настройки события, не сверяет его с unit economics и не подтверждает, что реальные пользователи передают событие. Через Console проверьте resource owner (в том числе manager при cross-account tracking), приложение и source, status, primary/secondary роль, counting, lookback windows и отсутствие дублей. Для App campaigns используется `selectiveOptimization`, а не обычный `CampaignConversionGoal`; описание первичных/вторичных действий и исключений находится в [Conversion goals](https://developers.google.com/google-ads/api/docs/conversions/goals/overview).

Ресурсы стран задают campaign location criteria. CLI не выставляет `geoTargetTypeSetting`: совместимость advanced location options с выбранной App campaign должна быть проверена для используемой версии, а фактическая семантика остается API default. Нельзя считать список стран гарантией исключительно физического присутствия пользователя в стране. Перед ручным запуском проверьте effective location options в Google Ads; общая модель описана в [location targeting](https://developers.google.com/google-ads/api/docs/targeting/location-targeting).

## Создание приостановленной кампании

```bash
python3 -m shared.google_ads create \
  --customer 1234567890 --api-version v25 \
  --config my-campaign.json \
  --receipt outputs/my-campaign-created.json --live
```

CLI сначала выполняет remote validateOnly. Только после успеха отправляет один atomic mutate с `partialFailure: false` и `validateOnly: false`: отдельный нешаренный budget → campaign → country/language criteria → ad group → AppAd с inline text assets. Используются уникальные временные IDs `-1`, `-2`, `-3`, определенные до ссылок на них. При отклонении любой операции весь create не применяется. См. [atomic bulk mutates](https://developers.google.com/google-ads/api/docs/mutating/bulk-mutate).

Campaign использует `MULTI_CHANNEL`, subtype `APP_CAMPAIGN`, store `GOOGLE_APP_STORE`, `targetCpa`, goal `OPTIMIZE_IN_APP_CONVERSIONS_TARGET_CONVERSION_COST` и `selectiveOptimization.conversionActions`. Это привлечение новых пользователей с оптимизацией по указанному in-app action. App engagement для уже установивших приложение, tROAS и другие стратегии этим create не реализованы. Сценарий основан на [официальной матрице App campaign goals](https://developers.google.com/google-ads/api/docs/app-campaigns/create-campaign) и [структуре ad group / AppAd](https://developers.google.com/google-ads/api/docs/app-campaigns/create-ad-group).

Созданные **Campaign, AdGroup и AdGroupAd все PAUSED**: они не показывают рекламу и не начинают расходовать бюджет, пока остаются приостановленными. Существующие активные кампании аккаунта продолжают жить независимо от этого инструмента. Для будущего запуска владелец должен проверить tracking, targeting, бюджет, assets и policies, затем самостоятельно включить все три сущности в Google Ads. CLI не включает их и не меняет уже существующие кампании. Значения статусов описаны в [campaign statuses](https://support.google.com/google-ads/answer/1722138).

Receipt с resource names сохраняется в новый файл; по умолчанию в `outputs/google-ads-created-<unique>.json`. Существующий файл не перезаписывается до создания. Receipt включает UTC `attemptedAt`, полный не содержащий secrets `requestedConfig` и `configSha256`, чтобы восстановить конкретный запрос даже после изменения исходного файла. Digest — свидетельство для сверки, не API idempotency key.

Перед проверкой записывается `validation-pending`, перед create — `creation-pending`; при успехе сохраняются подтвержденные имена. Ошибки фиксируются как `validation-failed`, `creation-rejected` или `creation-outcome-unknown`. Pending-файл после прерывания сам по себе не доказывает создание. Если сохранение receipt после подтвержденного успеха не удалось, resource names и конфигурация все равно выводятся в stdout.

При сетевой ошибке, HTTP 408/5xx или неполном ответе create результат может быть неизвестен. Не повторяйте live-команду автоматически: temporary IDs действуют только внутри запроса и не обеспечивают идемпотентность. Проверьте кампании и change history, чтобы не создать дубликат. CLI выводит это ограничение и не делает повторов. Ошибка сохранения receipt после успеха также не отменяет созданные ресурсы.

Для сверки сравните customer, время попытки, package, имя и параметры из receipt с ресурсами/change history в Ads; одно совпавшее имя недостаточно. Если ресурсы найдены, сохраните реальные resource names и состояние, затем продолжайте работу с существующим экземпляром. `create` не чинит существующие кампании и не служит способом обновить текст или бюджет.

Подтвержденный mutate возвращает resource names. CLI не выполняет отдельный read-back settings после создания; если нужен проверенный handoff перед включением, сверьте в Console campaign/ad group/ad statuses, budget/tCPA, action, geo/languages и effective eligibility. Назовите, какая часть подтверждена API-ответом, а какая повторным чтением.

## Выгрузка выбранной conversion action

```bash
python3 -m shared.google_ads report \
  --customer 1234567890 --api-version v25 \
  --start-date 2026-10-01 --end-date 2026-10-10 \
  --conversion-action customers/1234567890/conversionActions/987654321 \
  --output outputs/google-ads-report.csv
```

`report` — сетевое чтение, которое ничего не изменяет. Он получает App campaigns, включая engagement/pre-registration и исторические removed campaigns, за включительный диапазон дат аккаунта. Поддерживается pagination `GoogleAdsService.Search`; `pageSize` не задается. См. [Search REST](https://developers.google.com/google-ads/api/rest/common/search).

Нет фильтра package/campaign ID: report включает все App campaigns выбранного customer. Для анализа конкретного приложения сначала установите его campaign IDs по Console/проверенным settings и отфильтруйте CSV, сохранив оригинал. GAQL-выгрузка не содержит names, subtype, budget, learning state, geo или assets; их нельзя вывести из campaign/day totals.

`segments.date` нужно интерпретировать в timezone Ads account; идентификатор timezone задан в [Customer.time_zone](https://developers.google.com/google-ads/api/reference/rpc/v25/Customer#time_zone). Клиент не экспортирует timezone/action settings; сохраните рядом контекст: customer/package/campaign IDs, timezone, включительные даты, время fetch, selected action и определение события, источник, attribution/counting/lag. CSV без этого контекста пригоден для арифметики, но не для доказанной сопоставимости с Play/GA4/MMP.

CSV совместим с локальным анализатором:

```text
date,campaign_id,currency,cost,impressions,clicks,conversions,conversion_action
```

Первый GAQL-запрос получает полные cost/impressions/clicks кампании по дням. Второй получает `metrics.conversions`, сегментированные и отфильтрованные по одной указанной `segments.conversion_action`. Результаты соединяются по дате, campaign ID и валюте. Это не распределение расходов между действиями: каждый CSV содержит полный расход кампании и только выбранную конверсию. Не суммируйте расходы из нескольких отчетов разных действий за один период.

`cost_micros` точно преобразуется в единицы валюты; дробные conversions сохраняются. Нулевые conversion rows API может не возвращать — строка расхода остается с `conversions: 0`. Conversion-only rows сохраняются с нулем расходов. Дубликаты, некорректные числа и чужая conversion action вызывают ошибку вместо повторного подсчета. Пустой отчет содержит только заголовок.

`metrics.conversions` учитывает действия, входящие в conversions metric; это не `all_conversions`, не уникальные пользователи и не число всех событий Firebase. Даты обычных conversion metrics связаны с рекламным взаимодействием, а не с conversion date. Данные могут уточняться с задержкой; два read-запроса не являются транзакционным снимком. См. [conversion reporting](https://developers.google.com/google-ads/api/docs/conversions/reporting).

Вторичная/неподходящая action, неверный ресурс, новый аккаунт или conversion lag могут дать ноль выбранных conversions при ненулевых событиях в аналитике. CLI не переключается автоматически на `all_conversions`: это изменило бы смысл отчета. Пустой отчет также не является доказательством, что пользователи не пришли. Проверяйте event/import, eligible metrics, активные даты и свежесть перед расчетом окупаемости. Campaign spend может относиться к нескольким целям, поэтому selected-action CPA не равен CPA уникального плательщика без соответствующего определения.

Для локального анализа:

```bash
python3 -m shared.cli ads-report outputs/google-ads-report.csv --output outputs/google-ads-summary.json
```

Сводка содержит CTR долей (`0.05` = 5%), CPC и cost per selected conversion. При отсутствии conversions CPA равен `null`. `days_observed` — число строк с данными, а не гарантированная полнота календарного периода. Отдельные reports разных actions анализируйте отдельно: их полные расходы нельзя складывать.

## Диагностика

| Состояние | Проверка |
| --- | --- |
| Developer token/access/OAuth error | Token access level, user/service account, `adwords` scope, login manager и client customer; Play Console credentials не достаточны. |
| Несовпадение currency или invalid geo resource | Валюта реального Ads account, resource type/status и страна; micros остаются в валюте аккаунта, не конвертируются CLI. |
| Conversion action rejected | Owning conversion customer, нужное приложение/событие, status и compatibility выбранной цели. Не создавайте случайную action ради обхода validate. |
| Validation rejected | Исправьте local config; validateOnly не создал кампанию. |
| `creation-pending` / unknown outcome | Сверьте receipt с Ads/change history перед повтором. |
| Создано PAUSED, delivery = 0 | Это ожидаемо до отдельного включения; для включенной кампании проверяйте policies, eligibility, billing, statuses и targeting. |
| Report = 0 conversions | Выбранная metric/action, import, dates/timezone, lag; не считайте CPA нулевым. |
| Receipt/CSV save failed | Проверьте локальный путь/диск. Сохранение файла не откатывает подтвержденный create; используйте подтвержденные IDs из stdout. |

## Ограничения и проверка

Нет activation, управления существующими кампаниями, billing, импортирования conversion actions, audience lists, изображений/видео, keyword bidding и внешних MMP-интеграций. Локальный план проверяет форму запроса, remote validateOnly — правила API; лишь реальный аккаунт подтверждает доступность пакета, ресурсов и кампании. Live-вызовы на реальном аккаунте не выполнялись.

```bash
python3 -m unittest discover -s tests -p 'test_google_ads.py' -v
```

Offline-тесты проверяют REST shape, ссылочную целостность временных IDs, PAUSED на всех трех уровнях, порядок validate/create, атомарность, неизвестный исход, pagination и нормализацию CSV. Коды завершения: `0` — успех, `2` — локальный ввод/файлы, `1` — API/credentials/неопределенный результат.
