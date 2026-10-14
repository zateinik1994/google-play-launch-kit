---
name: google-ads-monitoring
description: Проанализировать показатели Android App campaigns из Google Ads API или нормализованного CSV, оценить атрибуцию и предложить изменения бюджета, цели и assets.
---

# Мониторинг Google Ads App campaigns

Проанализируй результат кампаний и, если это входит в поручение, подготовь конкретный план изменения. Прочитай [рекламные decision gates](references/knowledge/google-ads-app-campaigns.md) и [определения метрик](references/knowledge/play-metrics.md). Keyword CPT/EXACT/BROAD/ASA impression share gates в App campaigns не применяются.

## Начало сессии и сверка

Прочитай README/STATUS выбранного приложения, campaign config/receipt и журнал последних изменений, если они есть. Установи customer/campaign IDs, package, страны/языки, timezone/валюту аккаунта, цель и **один выбранный conversion action**. Проверь дату запуска/последней существенной правки, learning state, conversion lag и предел расхода теста. Известные сведения повторно не запрашивай.

Локальный план не доказывает текущие настройки Ads. Когда доступен аккаунт, сверь реальные статусы, budget, tCPA/стратегию, event, targeting и assets с проектом. Bundled `report` выгружает metrics, а не settings/change history: для этой сверки используй Console или доступную разрешенную интеграцию. Разницу между сохраненной конфигурацией и текущим кабинетом отрази перед рекомендацией.

## Входные данные

Для API прочитай [доступ, report и семантику conversions](references/docs/google-ads-api.md). Выбери полный период в timezone **Ads account**, завершив его вчерашним днем, если пользователь не задал другое окно. Семь полных дней полезны для оперативной сверки, но не универсальны для оценки: учитывай learning, цикл оплаты и lag; свежие дни покажи как предварительные. При неизвестной timezone не называй окно точно сопоставимым.

```bash
python3 <skill-directory>/references/shared/google_ads.py report --customer 1234567890 --api-version v25 --start-date 2026-10-01 --end-date 2026-10-10 --conversion-action customers/1234567890/conversionActions/987654321 --output workspace/app/reports/ads.csv
```

`<skill-directory>` — абсолютный путь этого скилла, `workspace/app/` — выбранная папка приложения. ID и версия в примере требуют замены/проверки. Report читает все App campaigns customer, включая engagement/pre-registration и removed. Не считай чужую кампанию этого аккаунта частью выбранного приложения: отфильтруй нужные campaign IDs по проверенным settings и сохрани исходный CSV. Фильтр campaign/package bundled report не реализует.

Для offline-разбора используй API CSV или нормализованный экспорт:

`date,campaign_id,currency,cost,impressions,clicks,conversions,conversion_action`

Одна строка campaign/day с одним выбранным action. `cost` — полная денежная сумма кампании в валюте аккаунта, не `cost_micros` и не расход, распределенный только на выбранное событие. Conversions могут быть дробными. Нельзя суммировать повторенные delivery metrics из отчетов по нескольким actions: сначала получи campaign/day delivery отдельно и присоедини нужную цель. Не называй `all_conversions` установками без проверки состава событий.

Рядом с выгрузкой запиши происхождение, customer/app/campaign IDs, timezone, включительные даты, время fetch, action definition, attribution/counting и известную задержку. Сам CSV эти сведения полностью не содержит. Нет asset/geo/cohort breakdown — укажи пробел, а не вычисляй его из агрегатов.

```bash
python3 <skill-directory>/references/shared/cli.py ads-report workspace/app/reports/ads.csv --output workspace/app/reports/ads-summary.json
```

CLI считает spend, impressions, clicks, conversions, CTR, CPC и cost per selected conversion. CTR возвращается долей: `0.05` = 5%. CPA при отсутствии conversions — `null`, а не ноль. `days_observed` отражает строки с данными, не гарантирует полноту календарного окна. Пустой отчет и ноль conversions не доказывают отсутствия пользователей: проверь выбор action, его metric eligibility, передачу события, active dates и lag.

## Проверка измерения и экономики

Сначала сверь событие и задержку. `metrics.conversions` — не все Firebase-события и не уникальные пользователи; вторичная action может отсутствовать в этой metric. Нормальные conversions относятся к дате рекламного взаимодействия, а cohort/payments часто к дате события. Для сравнения с GA4/MMP/backend выровняй attribution model/window, timezone, идентификаторы и дедупликацию. Несовпадение не исправляй молчаливой заменой Ads-чисел.

Покажи таблицу по кампаниям: период и свежесть, расход/валюта, выбранное действие, conversions, CPA, допустимый CPA, measurement/learning ограничения. Допустимый CPA бери из проверенной экономики или согласованного теста. Если данных нет, обозначь сумму риска и неизвестную окупаемость. При подписках добавь trials→paid/retention/refunds лишь из реальных cohorts, при IAP — маржу покупок; generic action CPA не равен стоимости платящего пользователя.

## Решения

Применяй [gates анализа и изменений](references/knowledge/google-ads-app-campaigns.md): measurement error или достижение разрешенного предела потерь требуют отдельного действия; незрелый период — дополнительного наблюдения; пригодный период с плохой экономикой — диагностики продукта/event/assets/target; хорошая экономика — ограниченного теста масштабирования. Нулевые показы не означают, что надо повышать bid каждые два часа: сначала проверь serving eligibility, статусы, target, бюджет и learning.

Не объединяй currencies, actions, цели или несопоставимые периоды. Сравни текущие настройки с последним изменением, а не только CPA вчера/сегодня. Для существенных правок задавай новую дату оценки с учетом lag и learning; не меняй одновременно цель, бюджет и все assets без причины, делающей такой эксперимент интерпретируемым.

Отдельно оцени assets и learning status в Ads, если эти данные доступны. Asset performance label — относительный сигнал, не причинный вклад и не основание приписать одному тексту весь CPA кампании. Google Play organic и Ads conversions имеют разные атрибуции; не вычисляй organic простым вычитанием Ads из Play installs и не обещай повышение органического ранга от рекламы.

## План, исполнение и журнал

Если пользователь просит только отчет, закончи данными и ограничениями. Если просит рекомендации, приложи конкретный план: resource ID/настройка, старое→новое значение, evidence, ожидаемый эффект, предел риска, stop condition и время следующей оценки. Не добавляй обязательную паузу между анализом и рекомендациями, когда пользователь уже попросил оба.

Bundled CLI **не обновляет** budgets, tCPA, статусы и assets существующих кампаний. Подготовь reviewable план для Console/доступной интеграции; не создавай заменяющую кампанию вместо изменения старой. Применяй live только в пределах уже данного поручения и возможностей интеграции. Если разрешения на конкретное изменение нет, закончи план перед запросом согласования. После изменения перечитай фактические settings и запиши дату, ресурсы, старое→новое, evidence и результат; failed/unknown outcome обозначь отдельно.

Результат — исходный CSV, сводка, контекст измерения, существенные пробелы и запрошенный план/журнал. Следующую проверку предложи по сроку созревания данных; автоматическое расписание создавай лишь по запросу пользователя.
