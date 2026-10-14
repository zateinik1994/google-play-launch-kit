---
name: google-ads-launch
description: Подготовить, проверить и создать Google Ads App campaign для Android с install tCPI или in-app action tCPA; сверить аккаунт и при поручении включить выбранные campaign/ad group/ad через проверяемый API-план.
---

# Запуск Google Ads для Android

Прочитай [механику и готовность](references/knowledge/google-ads-app-campaigns.md). App campaigns автоматизируют таргетинг и комбинации assets; ASO-запросы помогают формулировать ценность, но не превращаются в ASA exact-keyword ad groups.

## Начало сессии

Прочитай README/STATUS, campaign plan и журнал последнего изменения выбранного приложения, если они есть. Установи режим: план, remote validateOnly, создание PAUSED или включение существующей кампании. Проверь current через `ads_manage snapshot` и receipts: повторное создание с тем же именем не идемпотентно, а включение выполняется отдельным явным планом статусов.

Найди в материалах package name и Play URL, страны, языки, клиентский customer ID, валюту/timezone аккаунта, цель, средний дневной бюджет, событие конверсии, assets и условия теста. Для API дополнительно нужны существующий conversion resource, country/language resources и поддерживаемая версия. Уточняй лишь отсутствующие сведения, меняющие план; для консультации не требуй credentials.

## Готовность и выбор цели

Проверь decision gates из базы знаний: app и paywall доступны в целевых странах; событие измеряет нужное действие; экономика или согласованный исследовательский бюджет известны; assets и локализованный листинг готовы; владелец и stop condition определены.

Для action-кампании запиши источник события (Play/Firebase/GA4/MMP), точное имя/action resource, приложение-владелец, primary/secondary роль, counting, окна атрибуции и задержку. Test event в SDK сам по себе не доказывает корректный импорт в Ads. Не подменяй purchase событием first_open ради большей статистики без объяснения связи с ценностью. tCPA оценивается по выбранному действию, не автоматически по install или подписке.

Планируй цель по состоянию продукта. Bundled API-create поддерживает **install-volume/tCPI** и **in-app-action/tCPA**. Укажи `goal` явно; не подменяй CPI стоимостью action. Engagement, pre-registration, maximize/value/tROAS требуют другой eligibility/конфигурации и не выбираются этим create автоматически. Для install goal объясни, как качественные installs будут проверяться; для action goal нужны проверенные tracking/economics.

## План и материалы

Обоснуй target CPA через фактическую маржу/конверсию или честно выделенный эксперимент. Не придумывай LTV. Сохрани валюту, средний дневной бюджет, срок оценки, общий предел потерь, владельца остановки и допустимые изменения. Средний дневной бюджет не гарантирует жесткий дневной cap; общий лимит эксперимента не исполняется этим CLI. Укажи, как владелец будет наблюдать расход и остановит показы.

Выделяй кампании/группы по цели и существенным отличиям экономики, языка или creative theme, когда это помогает измерению. Не дроби малый бюджет на множество кампаний по каждому ASO-ключу. Раздели независимые headlines/descriptions, чтобы комбинации сохраняли смысл; app screenshots/feature graphic не заменяют отдельную проверку рекламных assets.

Зафиксируй baseline до платного теста: spend/action CPA существующих кампаний, acquisition/conversion rate из Play в одинаковом country/locale-контексте, activation и качество cohorts при наличии. Источники могут иметь разные определения; Ads installs нельзя просто вычесть из Play totals и назвать остаток органикой.

Для поддерживаемой action tCPA-цели подготовь человекочитаемый brief с `package_name,countries,languages,currency,daily_budget,target_cpa,conversion_action,headlines,descriptions`. Пример: [campaign.json](references/examples/data/campaign.json). Это формат планировщика, а не универсальный объект Ads API:

```bash
python3 <skill-directory>/references/shared/cli.py ads-plan workspace/app/campaign.json --output workspace/app/campaign-plan.json
```

`<skill-directory>` — абсолютный путь этого скилла, `workspace/app/` — выбранная папка результата. Для другой цели подготовь отдельный brief: этот планировщик всегда описывает in-app action tCPA.

## Создание через API

Прочитай [поддерживаемый контракт, доступ и receipts](references/docs/google-ads-api.md). Используй отдельный API-config из [action](references/examples/data/google-ads-create.json) или [installs](references/examples/data/google-ads-install.json): реальные resource names, суммы в **целых micros**, явная декларация `contains_eu_political_advertising: false`. Install config требует `target_cpi_micros`, action — `target_cpa_micros` и conversion resource. Не добавляй credentials или planning-only cap в API JSON. Package/resource IDs примеров вымышлены.

```bash
python3 <skill-directory>/references/shared/google_ads.py plan --customer 1234567890 --api-version v25 --config workspace/app/campaign-api.json
python3 <skill-directory>/references/shared/google_ads.py validate --customer 1234567890 --api-version v25 --config workspace/app/campaign-api.json --live
python3 <skill-directory>/references/shared/google_ads.py create --customer 1234567890 --api-version v25 --config workspace/app/campaign-api.json --receipt workspace/app/created.json --live
```

Выбери поддерживаемую версию по официальной таблице из API-инструкции; `v25` в примере не обещает вечную совместимость. Offline plan не требует ключей. Remote validateOnly проверяет валюту, страны и операции, но не создает кампанию и не подтверждает measurement или policy approval. Создание повторно выполняет validateOnly, затем один atomic mutate.

Перед creation проверь разрешение на конкретный аккаунт/план. Если его нет, закончи проверяемый config/план и запроси разрешение; повторно уже данное поручение не согласовывай. Campaign, AdGroup и AdGroupAd создаются **PAUSED**. Receipt сохраняет resource names; это создание, а не запуск. Включение ниже требует порученного scope расходов.

Если исход create неизвестен или остался `creation-pending`, сначала проверь наличие ресурсов через snapshot и change history в Ads. Имя/temporary IDs не защищают от дубликатов. Не повторяй live вслепую; существующие budgets/targets/status меняй через `ads_manage`, а не созданием второго экземпляра.

## Сверка и включение

Сохрани current и подготовь typed status-config с package/currency, campaign ID и конкретными `ad_group_resources`/`ad_group_ad_resources` из snapshot. Используй [пример activation](references/examples/data/google-ads-activate.json), заменив все IDs. `ENABLED` применяется лишь к campaign и явно выбранным children; PAUSED-материалы вне плана не включаются. Readiness, control расхода и стоп-условие должны уже быть определены.

```bash
python3 <skill-directory>/references/shared/ads_manage.py snapshot --customer 1234567890 --api-version v25 --package com.example.focus --output workspace/app/current.json
python3 <skill-directory>/references/shared/ads_manage.py plan --current workspace/app/current.json --config workspace/app/activate.json --output workspace/app/activate-plan.json
python3 <skill-directory>/references/shared/ads_manage.py validate --plan workspace/app/activate-plan.json --live
python3 <skill-directory>/references/shared/ads_manage.py apply --plan workspace/app/activate-plan.json --receipt workspace/app/activated.json --live
```

Первый вызов — read, plan — offline; validate/apply без `--live` также offline. Live apply проверяет preconditions до и после validateOnly, пишет receipt до mutate и проверяет поля read-back. Drift требует нового плана; неизвестный исход — сверки состояния перед повтором. Permission на PAUSED create сам по себе не разрешает ENABLED/увеличение бюджета. При уже данном разрешении запуска используй этот маршрут без повторного согласования.

## Проверка и результат

После создания сохрани receipt и API-config, запиши customer/campaign ID, package, goal/action, валюту, версии и дату. Snapshot подтверждает серверные settings/child statuses; create сам возвращает mutate resource names. После запуска укажи receipt/read-back result и фактический serving state, если он доступен: ENABLED сам по себе не гарантирует показы.

До включения проверь billing/eligibility, событие, эффективные geo options, язык, assets/policies и контроль расхода; snapshot не заменяет продуктовые readiness gates. Общий cap эксперимента не равен среднему дневному бюджету; остановку можно исполнить отдельным PAUSED-планом в пределах поручения.

Верни план, пробелы readiness, config/receipt, точную стадию и следующую оценку с учетом learning/conversion lag. Журнал фактического изменения содержит дату, ресурсы, значения, основание, разрешенный scope и результат. Не называй draft или validateOnly созданной кампанией, а PAUSED — работающей рекламой.
