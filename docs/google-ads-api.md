# Optional Google Ads REST CLI

`shared/google_ads.py` создает Android App campaigns для install volume/tCPI или in-app action/tCPA и выгружает campaign, geo и asset reports. Создание всегда оставляет **Campaign, AdGroup и AdGroupAd в состоянии PAUSED**. `shared/ads_manage.py` читает/сверяет существующие кампании и применяет явный план budgets, target costs и ENABLED/PAUSED выбранных serving entities. Изменения по умолчанию offline; `--live` включает server validate/create/update.

Скрипт использует официальные `GoogleAdsService.Search` и `GoogleAdsService.Mutate`, JSON-поля REST и реальные ресурсы Google Ads. Это отдельный API и отдельные разрешения: доступ к Google Play Console не дает доступ к Google Ads.

## Доступ и версия

Для набора используйте Python 3.11+, сетевые команды требуют дополнительную зависимость:

```bash
python3 -m pip install "google-auth[requests]>=2"
```

Нужны Google Ads API, developer token с подходящим access level и учетная запись с доступом к выбранному Ads customer. Credentials загружаются через ADC со scope `https://www.googleapis.com/auth/adwords`. Для service account можно задать `GOOGLE_APPLICATION_CREDENTIALS`; его email должен иметь нужный доступ в Google Ads. User ADC должны быть заранее получены с OAuth scope `adwords`: уже выданные credentials с другим scope не расширяются автоматически. См. [OAuth overview](https://developers.google.com/google-ads/api/docs/oauth/overview) и [service account workflow](https://developers.google.com/google-ads/api/docs/oauth/service-accounts).

Передайте developer token через `GOOGLE_ADS_DEVELOPER_TOKEN`, а при доступе через manager account — его ID через `GOOGLE_ADS_LOGIN_CUSTOMER_ID`. Client customer передается отдельным `--customer`; CLI принимает 10 цифр с дефисами или без. Credentials и токены не входят в конфиги, планы, CSV и receipts.

Для каждой команды требуется явный `--api-version`, например `v25`, соответствующий доступной версии Google. Скрипт не выбирает версию сам и не переключается на другую при ошибке. Перед работой сверьте [supported versions и sunset dates](https://developers.google.com/google-ads/api/docs/sunset-dates). Схема ниже проверена по v25 14 октября 2026 года; будущие версии могут требовать изменений.

## Конфигурация кампании

Пример: [examples/data/google-ads-create.json](../examples/data/google-ads-create.json). Это демонстрационные ID, package name и суммы; замените их своими значениями.

Файл задает название, Android package, валюту аккаунта, `daily_budget_micros`, списки ресурсов стран и языков, 1–5 headlines и 1–5 descriptions. `goal: in-app-action` требует `target_cpa_micros` и существующую `conversion_action`; `goal: install-volume` требует `target_cpi_micros` и не принимает action/CPA-поля. Примеры: [action](../examples/data/google-ads-create.json), [installs](../examples/data/google-ads-install.json). Для совместимости старый config без goal означает прежний in-app-action; новые файлы явно задают goal.

Используются полные имена: `customers/1234567890/conversionActions/987654321`, `geoTargetConstants/2840`, `languageConstants/1000`. CLI не угадывает conversion action по названию и не создает tracking. Для action-цели выбранное событие должно измерять нужное действие приложения и быть пригодным для оптимизации.

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

Campaign использует `MULTI_CHANNEL`, subtype `APP_CAMPAIGN`, store `GOOGLE_APP_STORE`. Для action это `OPTIMIZE_IN_APP_CONVERSIONS_TARGET_CONVERSION_COST` с `selectiveOptimization.conversionActions`; для installs — `OPTIMIZE_INSTALLS_TARGET_INSTALL_COST`. В обоих API-ресурсах стоимость задается `targetCpa.targetCpaMicros`: бизнес-смысл CPI/CPA определяет goal, CLI не меняет его скрыто. App engagement, pre-registration, maximize/value/tROAS требуют другого create-конфига/eligibility и данным create не переключаются. См. [матрицу App campaign goals](https://developers.google.com/google-ads/api/docs/app-campaigns/create-campaign) и [структуру ad group / AppAd](https://developers.google.com/google-ads/api/docs/app-campaigns/create-ad-group).

Созданные **Campaign, AdGroup и AdGroupAd все PAUSED**. Для запуска проверьте tracking, targeting, бюджет, assets/policies и подготовьте отдельный status-план через `ads_manage` ниже. `ENABLED` может начать рекламный расход; создание PAUSED не дает автоматического разрешения включать рекламу. Статусы описаны в [campaign statuses](https://support.google.com/google-ads/answer/1722138).

Receipt с resource names сохраняется в новый файл; по умолчанию в `outputs/google-ads-created-<unique>.json`. Существующий файл не перезаписывается до создания. Receipt включает UTC `attemptedAt`, полный не содержащий secrets `requestedConfig` и `configSha256`, чтобы восстановить конкретный запрос даже после изменения исходного файла. Digest — свидетельство для сверки, не API idempotency key.

Перед проверкой записывается `validation-pending`, перед create — `creation-pending`; при успехе сохраняются подтвержденные имена. Ошибки фиксируются как `validation-failed`, `creation-rejected` или `creation-outcome-unknown`. Pending-файл после прерывания сам по себе не доказывает создание. Если сохранение receipt после подтвержденного успеха не удалось, resource names и конфигурация все равно выводятся в stdout.

При сетевой ошибке, HTTP 408/5xx или неполном ответе create результат может быть неизвестен. Не повторяйте live-команду автоматически: temporary IDs действуют только внутри запроса и не обеспечивают идемпотентность. Проверьте кампании и change history, чтобы не создать дубликат. CLI выводит это ограничение и не делает повторов. Ошибка сохранения receipt после успеха также не отменяет созданные ресурсы.

Для сверки сравните customer, время попытки, package, имя и параметры из receipt с ресурсами/change history в Ads; одно совпавшее имя недостаточно. Если ресурсы найдены, сохраните реальные resource names и состояние, затем продолжайте работу с существующим экземпляром. `create` не чинит существующие кампании и не служит способом обновить текст или бюджет.

Подтвержденный create возвращает resource names. Для read-back перед включением выполните `ads_manage snapshot`: он получает package, goal, bid/strategy, budget и child statuses. Geo options, полную billing/serving eligibility и policy context сверьте в Console. Назовите, какая часть подтверждена mutate, а какая повторным чтением.

## Snapshot, reconciliation и изменения существующих кампаний

```bash
python3 -m shared.ads_manage snapshot --customer 1234567890 --api-version v25 --package com.example.focus --output outputs/current.json
python3 -m shared.ads_manage reconcile --customer 1234567890 --api-version v25 --package com.example.focus --expected outputs/current.json --output outputs/reconciliation.json
python3 -m shared.ads_manage plan --current outputs/current.json --config my-update.json --output outputs/change-plan.json
python3 -m shared.ads_manage validate --plan outputs/change-plan.json --live
python3 -m shared.ads_manage apply --plan outputs/change-plan.json
python3 -m shared.ads_manage apply --plan outputs/change-plan.json --receipt outputs/changed.json --live
```

`snapshot` и `reconcile` — network reads; второй возвращает drift и новый `current`. `plan`, `validate/apply` без `--live` не загружают credentials. Snapshot включает currency/timezone/conversion customer, кампании выбранного Android package, strategy/goal/target costs, budget ownership/reference count, ad groups/ads и approval status. Removed ресурсы доступны для истории, но не изменяются. Примеры offline-данных: [snapshot](../examples/data/google-ads-snapshot.json), [budget/CPA update](../examples/data/google-ads-update.json), [activation](../examples/data/google-ads-activate.json).

Typed update config содержит ровно `package_name`, `currency`, `changes`. Каждая change указывает `campaign_id` и необходимые поля:

```json
{
  "package_name": "com.example.focus",
  "currency": "USD",
  "changes": [{
    "campaign_id": "77",
    "daily_budget_micros": 60000000,
    "target_cpa_micros": 6000000,
    "status": "ENABLED",
    "ad_group_resources": ["customers/1234567890/adGroups/99"],
    "ad_group_ad_resources": ["customers/1234567890/adGroupAds/99~111"]
  }]
}
```

Budget/target/status независимы: передавайте лишь поля порученного изменения. Для install goal используйте `target_cpi_micros`; CPA/CPI сверяется с существующим goal и `TARGET_CPA` strategy, переключения strategy/event нет. Status `ENABLED` или `PAUSED` применяется к campaign и **явно перечисленным** children; невыбранные ресурсы не меняются. Activation требует выбранные группы и минимум одно выбранное ad каждой группы. Уже ENABLED descendants, которые начнут показы после включения родителя, тоже должны входить в план: иначе activation блокируется. Для campaign-only pause оба списка могут быть пустыми. Нужны реальные resource names из snapshot, а не имена кампаний.

Plan содержит from→to diff, REST operations с точными update masks, config/precondition digests. Для budget update клиент требует `explicitlyShared=false` и `referenceCount=1`; чужой package/customer, shared/unverified budgets и removed entities блокируются. Операции одного ресурса объединяются, unknown config-поля отвергаются. Бюджет меняется как абсолютная сумма, target — на уровне campaign, а не keyword bid. Поддерживаемые поля: [Campaign](https://developers.google.com/google-ads/api/fields/v25/campaign), [CampaignBudget](https://developers.google.com/google-ads/api/fields/v25/campaign_budget).

Snapshot дополнительно сверяет customer/resource IDs, app/store и связи campaign→ad group→ad. Неполная или противоречивая связь — ошибка чтения, а не разрешение включить ресурс. Read-запросы не являются единым транзакционным snapshot: если ресурс появился между ними, повторите сверку перед построением плана. Mutate подтверждает и resourceName, и соответствующий result type; неверный ответ оставляет явный unknown outcome без автоматического повтора.

Live apply читает свежий snapshot, сравнивает параметры выбранных campaigns/children с preconditions, выполняет validateOnly, повторно проверяет current и лишь затем отправляет atomic mutate. Drift после planning/validate останавливает работу до изменения. Google Ads не предоставляет compare-and-swap для этих query/update, поэтому короткая гонка после финального read остается возможной; не запускайте параллельных writers.

Receipt резервируется до изменения и сохраняет current/requestedConfig/time/hash. Состояния: `validation-pending` → `mutation-pending` → `mutated-readback-pending` → `updated-verified`. После mutate выполняется snapshot/read-back каждого выбранного поля. Mismatch дает `mutated-readback-mismatch` и exit 1; отказ чтения — `mutated-readback-failed`, а не повтор записи. Неизвестный mutate — `mutation-outcome-unknown`, definitive rejection — `mutation-rejected`. No-op дает `unchanged`. Ошибка диска до `mutation-pending` блокирует write, после подтвержденного mutate не отменяет его; stage выводится в stdout. Новый snapshot и сравнение с receipt нужны перед повтором неизвестного исхода.

## Выгрузка выбранной conversion action

```bash
python3 -m shared.google_ads report \
  --customer 1234567890 --api-version v25 \
  --start-date 2026-10-01 --end-date 2026-10-10 \
  --package com.example.focus \
  --conversion-action customers/1234567890/conversionActions/987654321 \
  --output outputs/google-ads-report.csv
```

`report` — сетевое чтение, которое ничего не изменяет. Он получает App campaigns, включая engagement/pre-registration и исторические removed campaigns, за включительный диапазон дат аккаунта. Поддерживается pagination `GoogleAdsService.Search`; `pageSize` не задается. См. [Search REST](https://developers.google.com/google-ads/api/rest/common/search).

`--package` фильтрует оба GAQL-запроса по Android app ID/store, `--campaign-id` можно повторять для выбранных campaigns. Без фильтров выгружаются все App campaigns customer; не приписывайте их одному приложению. Settings берите из snapshot, geo/assets — из отдельных report-команд.

`segments.date` интерпретируется в timezone Ads account ([Customer.time_zone](https://developers.google.com/google-ads/api/reference/rpc/v25/Customer#time_zone)). CSV сопровождается `<file>.csv.metadata.json`: source/customer/version, UTC fetch, account currency/timezone/conversion customer, period/filters/action, counting/lookback/primary settings и metric semantics. Account response должен подтвердить выбранный customer ID. Для cross-account action настройки читаются у owning customer; единственная строка проверяется по полному resourceName, а не просто числу строк. Если action не найдена, `conversionSettingsVerified=false`; другая/неоднозначная action — protocol error. Дополните бизнес-смысл event, известный lag и cohort context; metadata не доказывает корректность production SDK или оптимизацию кампании по этой action.

CSV и sidecar сначала полностью формируются во временной папке рядом с результатом. Sidecar публикуется раньше CSV, оба файла создаются исключительно без перезаписи; ошибка публикации CSV удаляет sidecar этого запуска. Неудачная сериализация не оставляет частичный CSV. При аварийном завершении процесса возможен одинокий sidecar; проверьте файлы и выберите новый путь, не трактуйте его как успешную выгрузку. Файловая система должна поддерживать локальные hard links.

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

## Geo и asset reports

```bash
python3 -m shared.google_ads geo-report --customer 1234567890 --api-version v25 --package com.example.focus --start-date 2026-10-01 --end-date 2026-10-10 --conversion-action customers/1234567890/conversionActions/987654321 --output outputs/geo.json
python3 -m shared.google_ads asset-report --customer 1234567890 --api-version v25 --package com.example.focus --start-date 2026-10-01 --end-date 2026-10-10 --conversion-action customers/1234567890/conversionActions/987654321 --output outputs/assets.json
```

Это JSON с `metadata`, `deliveryRows`, `conversionRows` и предупреждением об агрегации. Delivery содержит целые `costMicros`, impressions/clicks; conversion rows — одну action и fractional conversions. Два отдельных GAQL-запроса исключают повторение delivery при segmentation по actions. Сохранены исходные REST resource fields; это другой формат, не вход `ads-report` CSV-анализатора.

Geo использует [geographic_view](https://developers.google.com/google-ads/api/fields/v25/geographic_view): campaign/date/country criterion/location type. LOCATION_OF_PRESENCE и AREA_OF_INTEREST различаются — country нельзя автоматически назвать физической страной пользователя. Assets используют [ad_group_ad_asset_view](https://developers.google.com/google-ads/api/fields/v25/ad_group_ad_asset_view): asset/ad linkage, field type, enabled link, label, текст/YouTube ID и metrics. Этот view поддерживает App Ads. Один показ может содержать несколько assets: не суммируйте link metrics как независимый spend или причинный вклад. Label относится к текущему linkage, а не доказывает эффект материала за каждый исторический день.

Сервер может не вернуть zero rows или недоступные данным типом кампании metrics. Не подменяйте отсутствие данных нулевой эффективностью; campaign totals остаются контрольной суммой, а eligibility/definitions сверяются с current API. Geo/asset reports используют те же package/campaign filters и source/timezone/action metadata.

## Keyword ideas: внешний сигнал Google Search

```bash
python3 -m shared.google_ads keyword-ideas --customer 1234567890 --api-version v25 --config examples/data/google-search-keyword-ideas.json --output outputs/search-keyword-ideas.json
```

Network read использует `KeywordPlanIdeaService.GenerateKeywordIdeas`, не создает keyword plan или serving campaign. Config содержит 1–20 `seeds`, один `language_resource` и 1–10 `country_resources`; клиент проверяет активные Country geo constants и язык, затем получает все страницы. Network закреплен `GOOGLE_SEARCH`, adult ideas исключены. Нужны те же Ads credentials/developer token; отсутствие доступа или quota — явная ошибка, не выдуманная оценка спроса. Методы/ограничения: [Generate keyword ideas](https://developers.google.com/google-ads/api/docs/keyword-planning/generate-keyword-ideas).

JSON хранит account currency/timezone, дату/version/request и исходные `text`, `closeVariants`, `keywordIdeaMetrics` (historical monthly searches, competition, bid percentiles при доступности). Bid values — micros валюты аккаунта. Данные явно помечены `surface: GOOGLE_SEARCH`, `isGooglePlayPopularity: false`: это внешний поисковый сигнал, **не объем запросов Google Play, позиция приложения или Apple Search Popularity**. Близкие варианты могут группироваться; missing metrics остаются неизвестными. Проверяйте релевантность продукту и сопоставляйте с реальной Play выдачей/конверсией, не ранжируйте ASO автоматически только по Search volume.

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

App campaigns не предоставляют ASA keyword bidding/EXACT-BROAD control. Набор автоматизирует два acquisition create goals, чтение/сверку, budget/target/status updates и три вида reports. Billing, импорт conversion actions, audience lists, создание image/video assets, переключение strategy/goal и MMP SDK не реализованы этими командами: для них нужны соответствующие отдельные API workflows. Локальный план проверяет форму/ownership, remote validateOnly — правила API; лишь реальный аккаунт подтверждает eligibility. Live-вызовы на реальном аккаунте не выполнялись.

```bash
python3 -m unittest discover -s tests -p 'test_google_ads.py' -v
python3 -m unittest discover -s tests -p 'test_ads_manage.py' -v
```

Offline-тесты проверяют REST shape, ссылочную целостность временных IDs, PAUSED на всех трех уровнях, порядок validate/create, атомарность, неизвестный исход, pagination и нормализацию CSV. Коды завершения: `0` — успех, `2` — локальный ввод/файлы, `1` — API/credentials/неопределенный результат.
