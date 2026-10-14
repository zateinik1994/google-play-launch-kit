# CLI и данные

Python **3.11+**. Офлайн-команды используют только стандартную библиотеку. Запускайте из корня клона; в установленном скилле те же команды доступны через `references/shared/cli.py`.

```bash
python3 scripts/playkit.py init workspace/my-app --package com.example.myapp
python3 scripts/playkit.py validate examples/data/listings.json
python3 scripts/playkit.py keywords examples/data/keywords.csv
python3 scripts/playkit.py ranks examples/data/ranks-before.csv examples/data/ranks-after.csv
python3 scripts/playkit.py reviews examples/data/reviews.csv
python3 scripts/playkit.py ads-report examples/data/ads.csv
python3 scripts/playkit.py ads-plan examples/data/campaign.json
```

Для сохранения JSON используйте `--output путь.json` у любой команды кроме `init`. Файл результата перезаписывается, если уже существует. `init` отказывается работать в существующей папке. Коды завершения: `0` — успех, `1` — метаданные не прошли валидацию, `2` — ошибка входа/IO. Publisher API использует собственный CLI — [документация](play-api.md).

## Дополнительная автоматизация

| CLI | Назначение | Документация |
| --- | --- | --- |
| `shared/store_data.py` | Public profiles/search/ranks/reviews; offline `--fixture` | [Сбор ASO](aso-data-api.md) |
| `shared/appstorespy.py` | 22 typed Android provider операции; offline plan/явный billed `--execute` | [Сбор ASO](aso-data-api.md) |
| `shared/aso_tools.py` | Offline discover/gaps/experiment power estimate | [ASO tools](aso-tools.md) |
| `shared/play_reports.py` | GCS download и отдельные legacy/click CSV normalization/summary | [Play reports](play-reports-api.md) |
| `shared/play_release.py` | Listing/details/images/AAB/tracks; default offline, `--live` | [Publisher API](play-api.md) |
| `shared/play_safety.py` | Data safety CSV plan/официальный POST с backup | [Publisher API](play-api.md) |
| `shared/google_ads.py` | Install/action create, campaign/geo/asset reports, Google Search keyword ideas | [Google Ads API](google-ads-api.md) |
| `shared/ads_manage.py` | Snapshot/reconcile, budget/target/status plan/validate/apply | [Google Ads API](google-ads-api.md) |
| `examples/screenshots-generator/export.cjs` | Saved project→PNG/manifests/ZIP, optional Node/Playwright | [Генератор](../examples/screenshots-generator/README.md) |

Используйте `--help` каждого CLI для точных параметров. Python CLI доступны из установленного скилла под `references/shared/`. Новые collectors/planners/report outputs резервируют новый путь и **не перезаписывают** existing files; правило старого `playkit.py --output` выше остается прежним. Network reports и public collection выполняют чтение без `--live`; provider/GCS используют явный `--execute`. Сетевые изменения требуют `--live` и разрешенного scope, а не только валидного файла.

## Контракты CSV

UTF-8 (BOM допустим), стандартное quoting CSV. При запятых или переносах в тексте заключайте поле в двойные кавычки. Не удаляйте заголовки. Файлы `examples/data/*` — **вымышленные примеры**, а не исследование или реальные бенчмарки.

| Команда | Обязательные колонки | Значимые условия |
| --- | --- | --- |
| keywords | query, locale, country, source, relevance | relevance 0–3 задается человеком; volume необязателен, требует volume_source |
| ranks | observed_at, package_name, locale, country, query, rank, depth, source | ISO timestamp с timezone, rank 1..depth; пустой rank = за глубиной |
| reviews | review_id, rating, text | Уникальный review_id, rating 1–5 |
| ads-report | date, campaign_id, currency, cost, impressions, clicks, conversions, conversion_action | Одна строка campaign/day; YYYY-MM-DD, денежный cost, дробные conversions допустимы |

Дополнительные колонки разрешены, но не всегда входят в агрегат. Экспорты сервисов нужно **нормализовать** к этим контрактам: toolkit не обещает разобрать произвольный raw CSV Console/ASO-provider. Сохраняйте raw файл, период, источник, timezone и описание преобразования рядом.
Для `ads-report` используйте данные одного Ads customer на файл; сопоставление campaign ID с приложением храните рядом и фильтруйте нужные кампании до агрегации. Даты должны быть в полном формате `YYYY-MM-DD`.

## Интерпретация

`keywords` не получает выдачу или объем запросов. Источник и объем не генерируются. Кандидаты с relevance=0 сохраняются для аудита с `decision: excluded`; в итоговый shortlist и карточку они не входят. `ranks` сохраняет цензурирование наблюдения: неизвестное место не подменяется нулем; несопоставимый source/depth отделяется. `reviews` использует простой EN/RU словарь тем; пересечения и ложные совпадения требуют просмотра человеком.

`ads-report` не считает LTV и не выделяет installs из смешанного набора событий. Разные валюты/action группируются отдельно. Повтор campaign/day отклоняется, чтобы не сложить одну и ту же стоимость дважды. CPA при нуле conversions равен `null`.

`ads-plan` создает локальный brief для target CPA in-app actions, помеченный DRAFT_ONLY. Live создание поддерживается отдельным [Google Ads инструментом](google-ads-api.md) с точными API resource names. Никогда не включайте рекламный расход только потому, что шаблон прошел проверку.

## Что проверяет validator

Metadata validator проверяет JSON, набор полей, наличие текста, длину в Unicode code points, синтаксис locale и YouTube URL. Он не подтверждает поддержку locale магазином, правдивость функций, юридические права, содержание privacy policy или прохождение модерации. Editorial warnings — эвристики, а не официальная оценка Google. Окончательное принятие — Console/API и review.
