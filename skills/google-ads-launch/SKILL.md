---
name: google-ads-launch
description: Подготовить и проверить Google Ads App campaign для Android, а при явном поручении создать через API кампанию в статусе PAUSED с заданным бюджетом и целью.
---

# Запуск Google Ads для Android

Прочитай [механику и готовность](references/knowledge/google-ads-app-campaigns.md). App campaigns автоматизируют таргетинг и комбинации assets; ASO-запросы помогают формулировать ценность, но не превращаются в ASA exact-keyword ad groups.

## План

Найди в материалах или уточни package name, страны, языки, валюту аккаунта, средний дневной бюджет, цель и событие конверсии. Для action-кампании нужны проверенное событие и экономика допустимого CPA; не придумывай LTV. Запиши лимит эксперимента и условие остановки. Средний дневной бюджет не гарантирует жесткий дневной предел расходов.

Подготовь JSON с `package_name,countries,languages,currency,daily_budget,target_cpa,conversion_action,headlines,descriptions`. Это человекочитаемый brief для in-app action tCPA, а не универсальный объект Ads API.

```bash
python3 <путь-скилла>/references/shared/cli.py ads-plan campaign.json --output campaign-plan.json
```

## Создание через API

Когда нужен API, прочитай [поддерживаемый контракт](references/docs/google-ads-api.md). Используй отдельный API-config с реальными resource names целей/географии/языка. Offline plan не требует ключей. Remote validateOnly проверяет запрос, но не создает кампанию. Live create создает **PAUSED** campaign; не обходит настройки аккаунта или текущие eligibility rules.
В установленном скилле запускай `python3 <путь-скилла>/references/shared/google_ads.py` вместо `python3 -m shared.google_ads` из документации. Самостоятельный пример конфига: [google-ads-create.json](references/examples/data/google-ads-create.json); демонстрационные ID нужно заменить.

Перед remote creation проверь существующее разрешение пользователя на конкретный аккаунт/бюджет и подготовленный план. Если такого разрешения нет, покажи конкретный план и запроси его; не спрашивай повторно при уже данном разрешении. Этот репозиторий сам по себе не разрешает расходы. Включение кампании выполняется отдельно владельцем или явно уполномоченной интеграцией; инструмент не включает статус ENABLED.

Результат: план, состояние tracking, assets, версии API/идентификаторы созданных ресурсов или точная причина, почему создание не выполнено. Не выдавай локальный draft или validateOnly за живую кампанию. При неизвестном результате create не повторяй операцию вслепую: сначала проверь наличие кампании в Ads.
