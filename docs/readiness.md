# Локали и чеклист подготовки к выпуску

`shared/readiness.py` адаптирует полезные задачи исходных localization/launch-checklist утилит: показывает отсутствующие локали и собирает свидетельства проверки конкретного Android release. Он работает offline на стандартной библиотеке. Выручка рынка, стоимость перевода, compliance score и срок одобрения не прогнозируются.

```bash
python3 shared/readiness.py report --project config/project.example.json --listings examples/data/listings.json --output output/readiness.json
python3 shared/readiness.py template --package com.example.myapp --release-reference 'versionCode 42; build SHA256 recorded in QA log' --output output/evidence.json
```

Первая команда использует вымышленные факты. Для своего приложения передайте project JSON с `package_name`, `locales`, `countries`, `features`, `monetization`; optional `release_reference` идентифицирует именно подготовленный build/release. Пустые scope/факты и отсутствие listings оставляют проверки pending. Неверные типы/коды и повторенные locale/country отклоняются; синтаксис не подтверждает поддержку Google Play.

Для инвентаризации графики добавьте `--assets /absolute/path/assets-manifest.json` из [студии](../examples/screenshots-generator/README.md). Матрица каждой целевой locale содержит состояние текста, количество screenshot assets **по device/profile**, feature graphics, default-source fallbacks и отсутствие alt text. Portrait/landscape — альтернативные наборы; не складывайте их в одну upload sequence. Byte validation выполняется отдельным image validator, визуальный язык — просмотром actual UI. Локали вне project scope перечисляются отдельно. Страны не превращаются автоматически в язык карточки.

## Свидетельства проверок

Template содержит package/release и девять checks: product truth, privacy/Data safety, permissions/SDK, build/signing/target, testing/release eligibility, reviewer access, Billing, account deletion и visual/localization QA. Конкретные требования и applicability проверяйте по [review guide](play-review-guide.md) и текущей Console; список не является полным каталогом policies.

Для каждой реально выполненной проверки заполните:

```json
{"status":"passed","reference":"QA log / Console record / secure document reference","checked_at":"2026-10-14T12:00:00Z","note":"What was checked for this release"}
```

`passed` требует reference и timestamp с timezone. `failed` и `not-applicable` требуют объяснения в note; `pending` оставляйте до проверки. Не сохраняйте тестовые пароли, ключи или персональные данные: reference указывает на защищенный источник без его содержимого. Toolkit не открывает эти ссылки и не удостоверяет правдивость записей. Не меняйте pending в passed только ради завершения списка.

```bash
python3 shared/readiness.py report --project /absolute/path/project.json --listings /absolute/path/listings.json --assets /absolute/path/assets-manifest.json --evidence /absolute/path/evidence.json --release-reference 'versionCode 42; build SHA256 recorded in QA log' --output output/release-checklist.json
```

Evidence другого package/release отвергается. Reference должен совпадать с проектом или явным аргументом; новый build требует новой актуальной проверки. Результат содержит отдельные local checks и provided evidence statuses. `INCOMPLETE` показывает невыполненные записи; `CHECKLIST_RECORDED` означает, что структура и scope заполнены, а проверки отмечены в предоставленных свидетельствах. Это не submission, policy compliance, approval или разрешение публиковать.

Все output paths должны быть новыми. Обычный report возвращает exit `0`, когда файл создан, даже если список INCOMPLETE. Для проверки полноты записей используйте `--require-complete`: incomplete дает exit `1`; ошибки ввода/файлов — `2`. Template сам ничего не проверяет.

В переносимом скилле команда доступна как `<путь-скилла>/references/shared/readiness.py`.
