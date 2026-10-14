---
name: google-ads-launch
description: Подготовить и проверить Google Ads App campaign для Android, а при явном поручении создать через API кампанию в статусе PAUSED с заданным бюджетом и целью.
---

# Запуск Google Ads для Android

Прочитай [механику и готовность](references/knowledge/google-ads-app-campaigns.md). App campaigns автоматизируют таргетинг и комбинации assets; ASO-запросы помогают формулировать ценность, но не превращаются в ASA exact-keyword ad groups.

## Начало сессии

Прочитай README/STATUS, campaign plan и журнал последнего изменения выбранного приложения, если они есть. Установи, нужен ли только план, remote validateOnly, создание PAUSED или включение уже созданной кампании. Последнее bundled CLI не выполняет. Проверь текущие кампании/receipts: повторное создание с тем же именем не идемпотентно.

Найди в материалах package name и Play URL, страны, языки, клиентский customer ID, валюту/timezone аккаунта, цель, средний дневной бюджет, событие конверсии, assets и условия теста. Для API дополнительно нужны существующий conversion resource, country/language resources и поддерживаемая версия. Уточняй лишь отсутствующие сведения, меняющие план; для консультации не требуй credentials.

## Готовность и выбор цели

Проверь decision gates из базы знаний: app и paywall доступны в целевых странах; событие измеряет нужное действие; экономика или согласованный исследовательский бюджет известны; assets и локализованный листинг готовы; владелец и stop condition определены.

Для action-кампании запиши источник события (Play/Firebase/GA4/MMP), точное имя/action resource, приложение-владелец, primary/secondary роль, counting, окна атрибуции и задержку. Test event в SDK сам по себе не доказывает корректный импорт в Ads. Не подменяй purchase событием first_open ради большей статистики без объяснения связи с ценностью. tCPA оценивается по выбранному действию, не автоматически по install или подписке.

Планируй цель по текущему состоянию продукта. Bundled API-create поддерживает только **привлечение новых пользователей → in-app action → target CPA**. Install-volume tCPI, engagement, pre-registration, maximize conversions и tROAS можно описать в плане, но исполнение требует другого поддерживаемого маршрута. Не преобразуй пользовательскую цель молча в поддерживаемую.

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

Прочитай [поддерживаемый контракт, доступ и receipts](references/docs/google-ads-api.md). Используй отдельный API-config из [google-ads-create.json](references/examples/data/google-ads-create.json): реальные resource names, суммы в **целых micros**, явная декларация `contains_eu_political_advertising: false`. Не добавляй credentials или planning-only поля вроде общего cap в API JSON. Package/resource IDs примера вымышлены.

```bash
python3 <skill-directory>/references/shared/google_ads.py plan --customer 1234567890 --api-version v25 --config workspace/app/campaign-api.json
python3 <skill-directory>/references/shared/google_ads.py validate --customer 1234567890 --api-version v25 --config workspace/app/campaign-api.json --live
python3 <skill-directory>/references/shared/google_ads.py create --customer 1234567890 --api-version v25 --config workspace/app/campaign-api.json --receipt workspace/app/created.json --live
```

Выбери поддерживаемую версию по официальной таблице из API-инструкции; `v25` в примере не обещает вечную совместимость. Offline plan не требует ключей. Remote validateOnly проверяет валюту, страны и операции, но не создает кампанию и не подтверждает measurement или policy approval. Создание повторно выполняет validateOnly, затем один atomic mutate.

Перед creation проверь существующее разрешение на конкретный аккаунт и подготовленный план. Если его нет, сначала закончи проверяемый config/план и запроси разрешение; не спрашивай повторно при уже данном поручении. Этот репозиторий сам по себе не разрешает расходы. Campaign, AdGroup и AdGroupAd создаются **PAUSED**. Receipt сохраняет resource names; это создание, а не запуск. Включение выполняется отдельно владельцем или явно уполномоченной интеграцией.

Если исход create неизвестен или остался `creation-pending`, сначала проверь наличие ресурсов и change history в Ads. Имя кампании и временные IDs не защищают от дубликатов. Не повторяй live вслепую; не создавай второй экземпляр, чтобы починить статус или текст первого. Изменение существующих ресурсов этим CLI не реализовано.

## Проверка и результат

После подтвержденного создания сохрани receipt и API-config, запиши customer/campaign ID, package, action, валюту, версии и дату. Сверь созданные настройки в Ads, если доступен интерфейс/другая разрешенная интеграция: bundled create возвращает mutate resource names, а не отдельную повторную проверку статусов.

До включения владелец проверяет три статуса, billing/eligibility, событие, эффективные geo options, язык, assets/policies и контроль расхода. Если пользователь уже разрешил запуск, применяй это поручение доступным поддерживаемым маршрутом; отсутствие ENABLED-команды явно обозначь как ограничение инструмента.

Верни план, пробелы readiness, config/receipt, точную стадию и следующую оценку с учетом learning/conversion lag. Журнал фактического изменения содержит дату, ресурсы, значения, основание, разрешенный scope и результат. Не называй draft или validateOnly созданной кампанией, а PAUSED — работающей рекламой.
