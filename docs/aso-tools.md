# Offline ASO-инструменты

`shared/aso_tools.py` работает на стандартной библиотеке Python 3.11+. Он получает кандидаты из конкурентных текстов, проверяет покрытие фраз в листингах и рассчитывает приблизительную потребность эксперимента в трафике. Команды не обращаются к магазину и не меняют Console. Результат сохраняется в новый JSON; existing output не перезаписывается.

## Кандидаты и покрытие текста

```bash
python3 shared/store_data.py profiles --package com.example.habits --locale en-GB --country GB --fixture examples/data/public-play-fixture.json --output output/demo-profiles.json
python3 shared/aso_tools.py discover --profiles output/demo-profiles.json --seed 'habit tracker' --limit 50 --output output/demo-candidates.json
python3 shared/aso_tools.py gaps --keywords output/demo-candidates.json --listings examples/data/listings.json --output output/demo-gaps.json
```

Пример полностью вымышленный. В реальном исследовании используйте collected profiles из [сборщика](aso-data-api.md) или список нормализованных объектов с уникальным `package_name` и полями `title`, `shortDescription`, `fullDescription`.

`discover` выделяет фразы длиной 1–3 token и считает число документов, где они встречаются, а не число повторов слова. Seeds получают приоритет включения. EN/RU stopwords — ограниченный фильтр; языки без разделения на слова требуют другого метода. `volume: null` и `needs_product_fit_review: true` сохраняются: список нужно проверить и разметить по продукту до использования в карточке.

`gaps` принимает JSON-array keywords либо объект с `keywords` и валидированный locale→Listing JSON. Сравнение использует Unicode casefold и точную последовательность tokens без stemming. `locale` кандидата ограничивает проверку этой локалью; кандидат без locale проверяется во всех. `relevance: 0`/`decision: excluded` сохраняют исключение. `text_gap` означает отсутствие фразы в этих текстах, не отсутствие индексации, свободную нишу или прогноз позиции. Поле `needs_product_fit_review` остается в результате.

## План мощности эксперимента

```bash
python3 shared/aso_tools.py experiment --baseline-rate 0.08 --mde-relative 0.15 --daily-visitors 1000 --confidence 0.95 --power 0.8 --variants 1 --traffic-fraction 0.8 --min-days 7 --output output/experiment-plan.json
```

Значения — математический пример. `baseline-rate` — доля выбранного совместимого действия; `mde-relative: 0.15` означает рост 8%→9.2%, не +15 процентных пунктов. `daily-visitors` — пригодный для эксперимента поток; `traffic-fraction` — доля этого потока, направляемая в эксперимент. Число вариантов 1–2, control добавляется автоматически.

Расчет: normal approximation независимых двух пропорций, двусторонняя проверка, равное распределение, Bonferroni для нескольких сравнений с control. Выход содержит `visitors_per_arm`, `total_visitors`, `estimated_days`, assumptions и `state: PLANNING_ESTIMATE`. Малый baseline/эффект, зависимые визиты и нестабильный трафик могут требовать другого дизайна. Общая методика сравнения: [NIST, difference of proportions](https://www.itl.nist.gov/div898/software/dataplot/refman2/auxillar/diffprop.htm).

Оценка не повторяет экспериментальный движок Google, не подтверждает Console eligibility и не создает эксперимент. Задайте гипотезу и правило readout до запуска по [шаблону](experiment-template.md). Точные settings и результаты проверяются в [Store listing experiments](https://support.google.com/googleplay/android-developer/answer/12053285?hl=en); расчет не объявляет winner и не разрешает применение варианта.

В установленном скилле замените `shared/aso_tools.py` на `<путь-скилла>/references/shared/aso_tools.py`. Коды завершения: `0` — сохранено, `2` — вход/файлы.
