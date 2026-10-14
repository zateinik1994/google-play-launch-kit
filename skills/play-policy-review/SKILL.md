---
name: play-policy-review
description: Review Android app release readiness for Google Play using its actual build, listing, declarations, SDK data flows, reviewer access, and applicable policies. Use for a Play policy audit or preparation for submission; report unverified evidence separately from confirmed issues.
---

# Google Play release readiness

Подготовь проверяемый аудит конкретного приложения. Следуй языку и объему запроса пользователя; локальный аудит не расширяет поручение до изменения Console, публикации или рекламного расхода.

## Материалы и актуальность

Прочитай [review guide](references/docs/play-review-guide.md). Для листинга дополнительно используй [metadata](references/knowledge/play-metadata.md) и [creatives](references/knowledge/play-creatives.md), только когда они входят в аудит.

Собери доступные app/build facts: package, versionCode, target/min SDK, form factors, merged manifest, SDK versions, data flows, billing model, account creation/deletion, reviewer access и текущие Console declarations. Используй существующие материалы и явно назови пробелы; отсутствие live Console не мешает частичному локальному аудиту.

Перепроверь изменяемые правила по официальным Google Play / Android ссылкам из guide: target API и исключения, testing gate, 16 KB compatibility dates, чувствительные permissions и региональные Billing программы. Запиши дату и область применения. Если источник не доступен, пометь актуальность `unverified`; не называй старый snapshot текущим подтвержденным правилом.

## Проверка

Сопоставь обещания листинга и disclosures с фактической release-сборкой. Проверяй SDK и merged manifest, а не только код приложения. Выбирай дополнительные policy sections по реальным функциям и аудитории: Families, UGC/AI, health/finance, location, Accessibility и другие применимые категории. Не выводи Data safety ответы только из наличия или отсутствия permission.

Если есть доступ к работающему приложению, проверь основной путь, отказ в разрешениях, login/reviewer path, покупки/restore и account deletion в применимой части. Не помещай credentials в публичные файлы. Если запуска нет, конкретно укажи какие проверки остались невыполненными.

Не скрывай реальные функции от рецензента, не предлагай обходы review. Исправление текста/документа в авторизованном scope выполняй без отдельного согласования; изменение поведения app, declarations или submission должно соответствовать поручению пользователя.

## Результат

Сначала перечисли confirmed blockers, затем risks и unverified checks. Каждая находка содержит:

- Доказательство: путь/строка, экран, artifact или конкретный предоставленный факт.
- Применимое правило: официальный URL, checked date, platform/category scope.
- Исправление и способ проверить его.

Используй статусы `confirmed`, `unverified`, `not-applicable`; severity `blocker`, `risk`, `improvement`. Не путай отсутствие доказательства с подтвержденным нарушением. Финал должен дать конкретную готовность к следующему шагу и оставшиеся зависимости, не обещать одобрение Google.

При установленной копии все references должны существовать локально. Если пакет поврежден и reference недоступен, сообщи точный путь и продолжи аудит по доступным официальным источникам, помечая ограничение.
