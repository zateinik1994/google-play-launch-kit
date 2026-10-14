---
name: play-metadata
description: Подготовка и локализация карточки Google Play, проверка/diff и применение main listing текста, графики, контактов, AAB и release tracks через Android Publisher API с backup и явным live режимом.
---

# Google Play metadata

Подготовь, локализуй или обнови тексты **основной** карточки Google Play. Для редакторской работы достаточно сведений о продукте; package name, credentials и доступ к Console нужны только для обращения к аккаунту. Поддерживаемый API — Android Publisher v3 `edits.listings`; поля разных iOS-ресурсов здесь не используются.

## Начало работы

Проверь выбранную пользователем папку приложения, ее README/STATUS и предыдущие метаданные, если они существуют. Определи режим: подготовка нового текста, локализация, аудит текущего текста или согласованное API-изменение. Возьми из контекста аудиторию, реальные функции, платные ограничения, рынки/языки, брендовый тон и ключевые темы. Уточняй только сведения, без которых результат станет неверным.

Прочитай [ограничения и рекомендации](references/knowledge/play-metadata.md). Если семантическое ядро уже подготовлено, используй его источники и релевантность. При отсутствии исследования не называй выбранные фразы высокочастотными: отметь их как редакторские кандидаты; отдельное исследование нужно, когда оно входит в поручение.

У Google Play нет отдельного App Store keyword field: поисковые фразы должны естественно входить в видимые пользователю тексты. Не переноси iOS-лимиты и поля в Android-файл. Не выдумывай функции приложения и доказательства эффективности.

## Текст и локализация

Для каждой целевой локали подготовь название, краткое и полное описание с одним понятным обещанием, подтверждаемым продуктом. Проверь, что первый экран полного описания объясняет ценность и условия доступа, а остальные разделы раскрывают реальные сценарии. Не забивай название и текст повторами ключей.

Локализуй сценарии, термины и коммерческие условия, а не только слова. Сохраняй бренд и правдивые ограничения; цены и доступность функций бери из сведений пользователя. Язык и страна — разные параметры: один перевод не доказывает, что приложение или подписка доступны во всех странах языка. Если качество перевода не подтверждено, обозначь необходимость языковой проверки.

Формат `Listing` — объект с языковыми тегами и полями `title`, `shortDescription`, `fullDescription`, необязательным `video`. Для каждой передаваемой локали нужны все три текстовых поля. При изменении только названия скопируй остальные из baseline: CLI использует PUT, а не частичный PATCH. Теги Play проверяй по экспорту/Console, не конвертируй вслепую iOS-коды локалей. Подробнее: [формат, локали и восстановление](references/docs/play-api.md).

Для детерминированной проверки используй bundled CLI из [references/shared/play_api.py](references/shared/play_api.py). `<skill-directory>` замени абсолютным путем к этому скиллу; примеры `workspace/app/` обозначают выбранную папку результата:

```bash
python3 <skill-directory>/references/shared/play_api.py validate --input workspace/app/listings.json
python3 <skill-directory>/references/shared/play_api.py plan --input workspace/app/listings.json --current workspace/app/before.json
```

Без baseline опусти `--current`; такой план не знает текущего состояния магазина. Локальный validator проверяет структуру и лимиты, но не достоверность обещаний, смысл перевода, права на бренд или результат модерации. Устрани его ошибки и отдельно перечитай готовый текст.

## API-обновление

Когда поручение требует аккаунт, прочитай [инструкцию API](references/docs/play-api.md) для credentials, scopes, review state и диагностики. Для нескольких приложений/аккаунтов выполняй отдельную операцию с проверенным package name и нужными ADC; локальный файл не выбирает аккаунт сам.

Учитывай, что `list` и `export` создают временный edit и делают невалидным предыдущий edit той же учетной записи. Согласуй работу с уже активным инструментом публикации, если он присутствует в контексте. Не отменяй чужой review: bundled CLI задает `ERROR_IF_IN_REVIEW`.

При доступном baseline покажи конкретный diff по полям и локалям, включая явное удаление video. Отсутствие `video` сохраняет существующее видео, а пустая строка передает удаление; локали вне файла не удаляются. Подготовка текстов сама по себе не дает разрешение на commit. Используй уже данное пользователем разрешение на конкретное изменение; если его нет, сначала закончи файл и diff, затем запроси согласование.

```bash
python3 <skill-directory>/references/shared/play_api.py export --package com.example.app --output workspace/app/before.json
python3 <skill-directory>/references/shared/play_api.py apply --package com.example.app --input workspace/app/listings.json
python3 <skill-directory>/references/shared/play_api.py apply --package com.example.app --input workspace/app/listings.json --backup workspace/app/before-live.json --live
```

`export` обращается к Google; первый `apply` — offline dry run. Live получает новый снимок, сохраняет backup **до PUT**, обновляет локали, вызывает validate и commit. Не запускай live для демонстрации. При неизвестном исходе commit проверь Console и фактические значения до повторения; новый edit не откатывает уже примененные изменения. После commit проверь review/publishing state и отображение нужной локали, если это доступно в рамках поручения. До этой проверки результат — `committed`, а не доказанная публикация.

## Результат

Верни готовый JSON или согласованное изменение, перечень локалей/полей, существенные редакторские решения и фактическую стадию: draft → local validation → server validate → commit → visible listing. Для live приложи edit ID и путь backup, для ошибки — этап и действие восстановления. При text-only поручении API-доступ не является препятствием.

Для графики/AAB/tracks используй release workflow ниже. Privacy policy URL, Data safety, custom listings/experiments и реклама относятся к другим интерфейсам; не добавляй их поля в Listing JSON.

## Графика, AAB и выпуск

Прочитай раздел assets/releases в [Publisher guide](references/docs/play-api.md). `references/shared/play_release.py` объединяет выбранные операции в одном edit: main listing, contacts/defaultLanguage, images, AAB upload и releases существующих tracks. Это отдельный config; пример без реальных артефактов — [play-release.example.json](references/examples/data/play-release.example.json).

Подготовь config и файлы с точным package/локалями/track IDs, явно выбранными status/versionCodes и долей rollout. Images поддерживают append/replace/delete/reorder по language/type; порядок задается files или полным списком current IDs. Для bundle укажи AAB и expected versionCode, затем используй `$uploaded` в release для ответа реального upload. Нужные старые версии включай в полный desired releases массив. Draft, internal/closed delivery и production completed/inProgress имеют разные последствия; не угадывай статус по названию поручения.

```bash
python3 <skill-directory>/references/shared/play_release.py plan --config release.json
python3 <skill-directory>/references/shared/play_release.py snapshot --package com.example.app --live --output before.json
python3 <skill-directory>/references/shared/play_release.py plan --config release.json --current before.json
python3 <skill-directory>/references/shared/play_release.py validate --config release.json --live --backup-directory outputs/validation-01
python3 <skill-directory>/references/shared/play_release.py apply --config release.json --live --backup-directory outputs/release-01
```

Без `--live` команды offline. Server validate ставит assets/AAB/tracks во временный edit, проверяет и удаляет его без commit; это отличается от чтения. Live apply резервирует свежие text/details/tracks и оригинальные image binaries с проверкой server hashes **до** первого upload/PUT/DELETE. Ошибка backup блокирует запись. Удаление locale резервирует ее assets; reorder повторно загружает сохраненные оригиналы в заданном порядке. Phone/tablet/icon/feature проходят canonical техническую image validation; реальное device/policy QA и серверная проверка нужны для всех assets.

Используй существующее разрешение пользователя на конкретный config/операции. До commit проверь release readiness, signing/build/SDK пригодность и Console declarations по доступным данным. Выбери новую backup-папку: существующий путь блокирует запуск до edit. Tool не обходит testing/production access, review и publishing settings. При unknown commit проверь Console и `transaction.json` до повторного запуска. `rollback.json` — готовый config нового восстановительного edit, не автоматический undo: сначала проверь план и существующее поручение на восстановление. Он явно очищает video, если его не было в исходной карточке; raw text backup требует отдельного `"video":""` для этого случая.

Результат включает backup directory, edit ID, реальный uploaded versionCode, переданные track statuses/fractions и фактический committed/validated-only/unknown status. Notes ограничены 500 Unicode code points на locale, server подтверждает поддержку. Для подтверждения delivery после commit проверь track/карточку; production не считается видимым только по ответу API. Data safety, custom listings/experiments и Google Ads используют другие интерфейсы; unsupported API endpoints не выдумывай.

Для review/publishing readback используй `release-state`: GET официального `applications.tracks.releases.list` **вне edit**. Сопоставь activeArtifacts/versionCode с отправленным AAB, сохрани source/time и точный lifecycleState:

```bash
python3 <skill-directory>/references/shared/play_release.py release-state --package com.example.app --track production --live --output release-state.json
```

Без `--live` это offline read plan. Максимум 20 non-obsolete summaries не является полной историей; пустой ответ, неизвестный/unspecified state не подтверждают approval. PUBLISHED включает partial/ halted release и не доказывает полный rollout или видимость локализованной карточки. Для pending review/publishing действий нужен реальный Console workflow; readback их не выполняет.

## Data safety из подготовленного CSV

Для поручения на запись декларации прочитай Data safety раздел [API guide](references/docs/play-api.md). `references/shared/play_safety.py` использует официальный `applications.dataSafety` вне edit. Используй подготовленный evidence-backed CSV текущего Console формата; не выводи data flows из одной permission и не заполняй ответы автоматически на глаз.

```bash
python3 <skill-directory>/references/shared/play_safety.py plan --package com.example.app --csv data-safety.csv
python3 <skill-directory>/references/shared/play_safety.py apply --package com.example.app --csv data-safety.csv --before-csv before-data-safety.csv --backup-directory outputs/safety-01 --live
```

Plan и apply без --live offline. Live требует текущий before CSV, потому что у метода нет declaration GET/validateOnly; before/proposed/receipt сохраняются до POST из того же снимка, который сравнен и отправлен. Одинаковые CSV дают unchanged без credentials/POST. Синтаксическая проверка не подтверждает conditional полноту или правдивость SDK declarations. Учитывай уже данное разрешение на конкретную запись. Acceptance называется submitted; policy review/видимость labels проверяются отдельно. При unknown outcome сначала проверь Console, не повторяй POST автоматически.
