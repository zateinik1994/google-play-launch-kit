---
name: google-ads-monitoring
description: Проанализировать показатели Android App campaigns из Google Ads API или нормализованного CSV, оценить атрибуцию и предложить изменения бюджета, цели и assets.
---

# Мониторинг Google Ads App campaigns

Прочитай [рекламные decision gates](references/knowledge/google-ads-app-campaigns.md) и [определения метрик](references/knowledge/play-metrics.md). Установи период, timezone, валюту, кампанию, выбранный conversion action и conversion lag. Не называй `all_conversions` установками без проверки состава событий.

## Входные данные

Для чтения API используй [API-инструмент](references/docs/google-ads-api.md). Для офлайн-разбора подготовь CSV:
В установленном скилле API-команды запускай через `python3 <путь-скилла>/references/shared/google_ads.py`; `python3 -m shared.google_ads` из инструкции относится к корню клона.

`date,campaign_id,currency,cost,impressions,clicks,conversions,conversion_action`

Одна строка campaign/day с одним выбранным action. `cost` — денежная сумма в валюте аккаунта, не `cost_micros`; конверсии могут быть дробными. Нельзя суммировать повторенные delivery metrics из отчета, разбитого по нескольким conversion actions: сначала получи campaign/day delivery отдельно и присоедини нужную цель.

```bash
python3 <путь-скилла>/references/shared/cli.py ads-report reports/ads.csv --output reports/ads-summary.json
```

CLI считает CTR/CPC/cost per selected conversion; он не меняет ставки или бюджеты. Отсутствие конверсий дает неизвестный CPA, а не нулевой CPA.

## Решения

Проверь событие и задержку до оценки эффективности. Затем сравни CPA с допустимой экономикой и качеством cohort (activation, retention, фактическая выручка после возвратов). Не объединяй разные currencies, conversion actions или несопоставимые периоды.

Отдельно оцени assets и learning status в Ads. Низкий label одного asset — повод для проверяемого обновления, не доказательство причинного вклада. Google Play organic и Ads conversions имеют разные атрибуции; не вычисляй organic простым вычитанием Ads из всех Play installs.

Подготовь журнал решений: evidence, предлагаемая настройка, ожидаемый эффект, предел риска, время следующей оценки. Применяй live изменения только в пределах данного поручения и возможностей доступной интеграции. Если нужны повторные проверки, расписание создавай только по запросу пользователя.
