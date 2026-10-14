# Автоматический сбор ASO-данных

## Публичные данные Google Play

`shared/store_data.py` собирает профили, результаты поиска, позиции выбранных package и свежие отзывы. Используется optional [google-play-scraper для Python](https://github.com/JoMingyu/google-play-scraper). Это наблюдение публичного web-store, а не официальный ranking API; изменения страницы могут сломать parser. Проверено 2026-10-14.

```bash
python3 -m pip install -r requirements-collection.txt
python3 shared/store_data.py profiles --package com.example.myapp --locale en-GB --country GB --output output/profiles.json
python3 shared/store_data.py search --query 'habit tracker' --locale en-GB --country GB --limit 30 --output output/search.json
python3 shared/store_data.py ranks --query 'habit tracker' --package com.example.myapp --locale en-GB --country GB --limit 30 --output output/ranks.csv
python3 shared/store_data.py reviews --package com.example.myapp --locale en-GB --country GB --limit 200 --output output/reviews.csv
```

Замените package на реальный. Без `--fixture` команды выполняют сетевое чтение. Search/ranks ограничены 30 результатами, profiles — 30 различными package, reviews — 1000 отзывами. Не используется бесконечная загрузка reviews_all. Передаются полный языковой вариант и явная страна. Каждый результат содержит источник, дату и контекст; CSV получает metadata sidecar.

Depth снимка равен числу фактически полученных результатов. Пустая выдача и поврежденный ответ — ошибка, не доказательство отсутствия приложения. Пустой rank означает «не найдено среди первых depth результатов». Снимки принимаются существующим `playkit.py ranks`, review CSV — `playkit.py reviews`. Полностью одинаковые review IDs дедуплицируются; конфликтующие версии требуют проверки актуальной записи. Timestamp отзыва может отражать особенности scraper; не подменяйте неизвестный timezone UTC.

Offline-пример с вымышленными данными:

```bash
python3 shared/store_data.py ranks --query 'habit tracker' --package com.example.habits --locale en-GB --country GB --fixture examples/data/public-play-fixture.json --output output/demo-ranks.csv
```

Fixture metadata содержит `is_fixture: true`; даже внутри rank CSV source равен `fixture/offline@fixture`. Timestamp описывает запуск примера, не историческое наблюдение магазина. Реальный source содержит parser version, поэтому смена метода/версии видна при сравнении снимков.

## AppStoreSpy Android API

`shared/appstorespy.py` реализует **22 Android операции**. Registry параметров, enum и обязательных полей проверен по [OpenAPI](https://api.appstorespy.com/v1/openapi.json) 2026-10-14; запросы локально проверяются до обращения к сервису.

| Группа | Команды |
| --- | --- |
| Профили и конкурентный анализ | app, listing, search, query, similar, summary |
| Отзывы и оценки | reviews, estimates, daily-installs, rankings |
| Разработчики | developer, developers, developer-query, developer-estimates |
| Подсказки и реальные search jobs | suggestions, search-job-create, search-jobs |
| Справочники/дополнительные данные | countries, languages, aggregates, liveops, recrawl |

```bash
python3 shared/appstorespy.py app --params examples/data/provider-app-params.json
python3 shared/appstorespy.py query --body examples/data/provider-query.json
python3 shared/appstorespy.py search-job-create --body examples/data/provider-search-job.json
```

По умолчанию выводится offline-plan с URL, параметрами и ожидаемой ценой из schema. Для выполнения добавьте `--execute` и настройте `APPSTORESPY_API_KEY` в окружении. Тариф, credits и доступ к операции принадлежат владельцу аккаунта. Актуальные цены/семантика вызовов описаны в [agentic access](https://api.appstorespy.com/agentic-access). Не используйте выполненные billed-запросы как бесплатный тест CLI.

`--params` задает query/path parameters в исходных единицах API; `--body` — типизированный POST JSON. Необходимые параметры показаны в registry `shared/appstorespy_schema.json`; поля/единицы фильтров проверяются по документации сервиса. Клиент не выполняет автоматическую конвертацию экономических фильтров или локалей между сервисами. Примеры содержат вымышленные package/данные.

Сетевой ответ обернут provenance и billing receipt. `queued`, `partial`, `no_country_data` не превращаются в успешный полный профиль. App/listing/recrawl/search-job запросы могут инициировать сбор у провайдера; результат job надо читать отдельной командой. Автоматических повторов/поллинга нет. Revenue/download estimates остаются модельными, chart rankings отличаются от search jobs, database search — от наблюдения выдачи.

Используйте `--output new-file.json` для сохранения. Существующий файл проверяется до billed вызова и не перезаписывается. API-key не входит в plan/result; редиректы credential-bearing запроса не выполняются.

## Установка скиллов

В переносимой копии те же CLI доступны как `references/shared/store_data.py` и `references/shared/appstorespy.py`. Отдельный JSON registry копируется вместе с `shared/`. Для публичного сбора optional package установите в используемый Python отдельно; собственный provider клиент работает на стандартной библиотеке.
