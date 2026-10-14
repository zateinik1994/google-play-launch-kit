# Загрузка и нормализация Play reports

`shared/play_reports.py` загружает CSV из report bucket разработчика через [Cloud Storage Objects.get](https://docs.cloud.google.com/storage/docs/json_api/v1/objects/get), нормализует метрики и считает дневные агрегаты. Доступ требует ADC со scope `devstorage.read_only` и разрешений выбранного Play report bucket.

```bash
python3 shared/play_reports.py download --bucket pubsite_prod_123456789 --package com.example.myapp --month 202610 --breakdown traffic_source --output output/download-plan.json
python3 shared/play_reports.py download --bucket pubsite_prod_123456789 --package com.example.myapp --month 202610 --breakdown traffic_source --output output/raw.csv --execute
```

Замените bucket/package своими значениями. Без `--execute` создается локальный план; credentials не загружаются. Поддерживаются стандартные legacy Store performance objects с breakdown country/traffic_source и произвольный явно заданный `--object` из вашего report bucket. См. [официальные пути и формат CSV](https://support.google.com/googleplay/android-developer/answer/6135870?hl=en).

Выбранный объект сохраняется без преобразования вместе с sidecar: source, bucket/object и время получения. Копия не перезаписывается. Загрузка ограничена 64 MB и не повторяется автоматически; credential-bearing redirects отклоняются.

```bash
python3 shared/play_reports.py normalize --input examples/data/play-performance.csv --package com.example.habits --output output/performance.json
python3 shared/play_reports.py summary --input output/performance.json --output output/performance-summary.json
```

UTF-8/BOM и UTF-16/BOM распознаются; при необходимости задайте `--encoding`. Для переведенных или иначе названных колонок передайте `--mapping` JSON вида `{"date":"Дата","package_name":"Название пакета","visitors":"Посетители","acquisitions":"Привлечения"}`. Пустые счетчики сохраняются неизвестными. Ошибочный package, дубликаты и сдвинутые CSV-строки не агрегируются.

Каждый исходный столбец может соответствовать только одному normalized field: нельзя получить visits и acquisitions из одной колонки. Metadata сохраняет SHA256 исходных bytes, encoding, заголовки и фактический mapping; CLI добавляет путь исходника и время нормализации. Сохраните downloaded sidecar/описание Console filters рядом: один хеш не подтверждает источник или полноту выгрузки.

Нормализованный ряд сохраняет date, package, country, language, store_listing, install_state, device_form_factor, traffic_source, search_term, utm_source, utm_campaign и metric_family. Summary разделяет все эти измерения. Отрицательные/дробные/нечисловые counts, неверная дата/package и duplicate context отклоняются даже при чтении вручную подготовленного JSON.

## Семантика

Нормализатор отделяет `legacy-acquisitions` и `click-intent`. При смешанных колонках нужен явный `--family`; скрипт не склеивает временные ряды разных определений. Click export может поступить из Console; используйте доступные фактические колонки и [текущую справку метрик](https://support.google.com/googleplay/android-developer/answer/9859173?hl=en). Стандартный GCS path не обещает новый click-based отчет.

Для clicks выберите один показатель: `summary --action install_clicks|open_clicks|pre_registration_clicks`. Summary считает **visitor-days/action-days** и отношение дневных счетчиков внутри одного контекста; это не weekly/monthly deduplicated unique users и не повторение Console cohort-rate. Неполные счетчики дают неизвестный итог. Не складывайте разные breakdown reports, total и дочерние строки или actions одной аудитории.

Search terms описывают трафик **вашего** listing. Это измеренное discovery, не общий объем запросов магазина. Источник/фильтры/период и определения метрик сохраняйте вместе с результатом. Для paid/organic сравнения используйте совместимую атрибуцию, а не простое вычитание Ads conversions.
