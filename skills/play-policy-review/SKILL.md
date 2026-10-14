---
name: play-policy-review
description: Review Google Play release readiness, SDK data flows and rejection evidence; validate an evidence-backed Data safety CSV and submit it through Publisher API when instructed. Distinguish syntax validation, API acceptance and policy approval.
---

# Google Play release readiness

Подготовь проверяемый аудит конкретного приложения. Следуй языку и объему запроса пользователя; локальный аудит не расширяет поручение до изменения Console, публикации или рекламного расхода.

Выбери режим по поручению: pre-submission audit, проверка конкретной policy/экрана, проверка/передача Data safety CSV или разбор rejection. При rejection сначала прочитай оригинальное уведомление, package/versionCode, тип enforcement и затронутые tracks; не начинай повторную отправку наугад.

## Материалы и актуальность

Прочитай [review guide](references/docs/play-review-guide.md). Для листинга дополнительно используй [metadata](references/knowledge/play-metadata.md) и [creatives](references/knowledge/play-creatives.md), только когда они входят в аудит.

Собери доступные app/build facts: package, versionCode, target/min SDK, form factors, merged manifest, SDK versions, data flows, billing model, account creation/deletion, reviewer access и текущие Console declarations. Используй существующие материалы и явно назови пробелы; отсутствие live Console не мешает частичному локальному аудиту.

Перепроверь изменяемые правила по официальным Google Play / Android ссылкам из guide: target API и исключения, testing gate, 16 KB compatibility dates, чувствительные permissions и региональные Billing программы. Запиши дату и область применения. Если источник не доступен, пометь актуальность `unverified`; не называй старый snapshot текущим подтвержденным правилом.

## Проверка

Сопоставь обещания листинга и disclosures с фактической release-сборкой. Проверяй SDK и merged manifest, а не только код приложения. Выбирай дополнительные policy sections по реальным функциям и аудитории: Families, UGC/AI, health/finance, location, Accessibility и другие применимые категории. Не выводи Data safety ответы только из наличия или отсутствия permission.

Если есть доступ к работающему приложению, проверь основной путь, отказ в разрешениях, login/reviewer path, покупки/restore и account deletion в применимой части. Не помещай credentials в публичные файлы. Если запуска нет, конкретно укажи какие проверки остались невыполненными.

Для подписок проверяй весь путь от listing/onboarding до paywall и management: что пользователь получает, фактически списываемую цену/период, trial → paid, доступ без покупки если он есть, локализованные условия и cancellation. Сравнивай с реальными products/offers и eligibility, а не только с нарисованным экраном. Рабочие случаи и [App access template](references/docs/play-review-guide.md#шаблон-app-access) находятся в guide.

Для сводного provided-evidence checklist и locale inventory прочитай [readiness workflow](references/docs/readiness.md). Bundled CLI работает offline и связывает записи с выбранным package/release:

```bash
python3 <skill-directory>/references/shared/readiness.py template --package com.example.app --release-reference "versionCode 42, production" --output workspace/app/readiness-evidence.json
python3 <skill-directory>/references/shared/readiness.py report --project workspace/app/project.json --listings workspace/app/listings.json --assets workspace/app/assets.json --evidence workspace/app/readiness-evidence.json --require-complete --output workspace/app/readiness.json
```

Заполняй passed только подтвержденными evidence reference и checked_at с timezone; failed/not-applicable требуют объяснения. `INCOMPLETE` показывает пробелы, `CHECKLIST_RECORDED` означает записанный checklist: программа не проверяет документы по ссылкам, реальное состояние аккаунта, policy approval или разрешение публикации. Project release_reference должен совпадать с evidence; для частичного аудита опусти недоступные listings/assets/evidence и сохрани pending checks.

Не скрывай реальные функции от рецензента, не предлагай обходы review. Исправление текста/документа в авторизованном scope выполняй без отдельного согласования; изменение поведения app, declarations или submission должно соответствовать поручению пользователя.

## Data safety CSV и API

Сначала сопоставь ответы с реальными data flows/SDK и текущим шаблоном Console. Не генерируй declaration по разрешениям manifest и не отправляй публичный sample как форму приложения. Сохрани CSV в папке выбранного приложения, отдельно от учебных examples; для live установи точный package и свежий prior CSV, экспортированный владельцем из Console.

Для API прочитай [контракт Data safety](references/docs/play-api.md#data-safety-отдельный-официальный-post) и используй [bundled CLI](references/shared/play_safety.py). `<skill-directory>` замени абсолютным путем этого скилла; пути ниже обозначают выбранную папку результата:

```bash
python3 <skill-directory>/references/shared/play_safety.py plan --package com.example.app --csv workspace/app/data-safety.csv --before-csv workspace/app/before-data-safety.csv
python3 <skill-directory>/references/shared/play_safety.py apply --package com.example.app --csv workspace/app/data-safety.csv
python3 <skill-directory>/references/shared/play_safety.py apply --package com.example.app --csv workspace/app/data-safety.csv --before-csv workspace/app/before-data-safety.csv --backup-directory workspace/app/safety-01 --live
```

Первые две команды offline и не загружают credentials. Проверка формы CSV не подтверждает полноту conditional questions или достоверность декларации. Подготовь конкретный файл, сверку ответов с evidence и существенные изменения относительно before. Используй уже данное разрешение на выбранное declaration; если его нет, закончи reviewable файл/сравнение перед запросом согласования.

Live использует `applications.dataSafety` с `safetyLabels` — **отдельный немедленный POST вне edit**. У метода нет declaration GET или validateOnly: свежесть/package prior CSV подтверждается через Console/контекст владельца. `--before-csv` и новая backup-папка обязательны; CLI сохраняет before/proposed CSV и receipt до записи. Comparison, архив и отправка используют один снимок прочитанных файлов; одинаковые CSV дают `unchanged` без credentials/POST. Он не объединяет Data safety с AAB/listing commit и не откатывает ее при ошибке релиза.

Результат `submitted` означает acceptance API, а не policy approval или видимые labels. Проверь declaration/review/public state в Console, если доступ предоставлен. При `submission-outcome-unknown`, таймауте или failed receipt после подтвержденного ответа сначала сверь состояние; повторение автоматически запрещено. Перед восстановлением нужна новая явная запись сохраненного CSV в пределах поручения и актуальный prior export.

## Если пришел rejection

Следуй [rejection workflow и шаблону ответа](references/docs/play-review-guide.md#если-получен-rejection-или-другое-enforcement). Сопоставь каждый пункт письма с воспроизводимым сценарием и текущим правилом, затем подготовь diff/evidence и повторную проверку. Различай исправление с resubmission и обоснованную appeal на ошибочное решение. Проверяй соответствующие internal/closed/open/production tracks: старый нарушающий bundle может остаться активным.

Повторный rejection не доказывает скрытую причину отказа: проверь что отправлена исправленная сборка, декларации соответствуют ей, reviewer access работает и указанные artifacts относятся к нужной версии. При недостающем объяснении подготовь предметный запрос по case ID. Ответ и appeal сохраняй как черновик; отправка выполняется только в пределах поручения владельца.

Если предоставлен API-доступ, для lifecycle нужного track используй bundled GET без создания edit:

```bash
python3 <skill-directory>/references/shared/play_release.py release-state --package com.example.app --track production --live --output workspace/app/release-state.json
```

Прочитай [контракт release-state](references/docs/play-api.md#reviewpublishing-state-без-edit), сопоставь active versionCode и сохрани source/time. IN_REVIEW, NOT_APPROVED, APPROVED_NOT_PUBLISHED и PUBLISHED различаются; последний включает partial/halted release. Максимум 20 non-obsolete summaries не является полной историей; неизвестный/unspecified state не означает approval. API не заменяет оригинальное rejection письмо, причины policy finding или проверку публичной карточки. Без `--live` получишь только offline read plan.

## Результат

Сначала перечисли confirmed blockers, затем risks и unverified checks. Каждая находка содержит:

- Доказательство: путь/строка, экран, artifact или конкретный предоставленный факт.
- Применимое правило: официальный URL, checked date, platform/category scope.
- Исправление и способ проверить его.

Используй статусы `confirmed`, `unverified`, `not-applicable`; severity `blocker`, `risk`, `improvement`. Не путай отсутствие доказательства с подтвержденным нарушением. Финал должен дать конкретную готовность к следующему шагу и оставшиеся зависимости, не обещать одобрение Google. Для submission/rejection приложи матрицу проверок, короткий owner action list, reviewer instructions без секретов и draft ответа, если он нужен; локальный pass не называй approval или опубликованным релизом.

Для Data safety приложи путь проверенного CSV, evidence gaps и точную стадию: offline-plan, unchanged, submitted, submission-rejected или submission-outcome-unknown. После live укажи backup/receipt; credentials в отчет не включай.

При установленной копии все references должны существовать локально. Если пакет поврежден и reference недоступен, сообщи точный путь и продолжи аудит по доступным официальным источникам, помечая ограничение.
