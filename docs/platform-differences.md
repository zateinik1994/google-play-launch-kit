# Как адаптирован iOS launch workflow

Проверено: **2026-10-14**. Это соответствие рабочих задач Android-набору; механики платформ нельзя переносить заменой названия магазина.

| Задача iOS workflow | Android / Google Play подход | Практическое следствие |
| --- | --- | --- |
| Title, subtitle, hidden keywords | Title 30, short description 80, full description 4000 | Нет subtitle и hidden keywords в Play Listing API; keyword bank остается исследованием |
| Исследование Apple Search Ads popularity | Собственный Console, наблюдения, пользовательская речь, явно названные estimates | Не генерировать «Play SP» и не переносить Apple score |
| ASA keyword bids / exact-broad структуры | Google Ads App campaigns: автоматизированное multi-network продвижение | Планировать conversion goal, assets, measurement и бюджет |
| App Store screenshots | Phone/tablet и другие Play form-factor assets, отдельный feature graphic | Проверять Android UI, locale, реальные размеры и профиль устройства |
| Product page conversion | Текущий Play listing CTR и отдельно legacy acquisition CVR | Не объединять клики намерения и успешные установки |
| Product page experiments | Play Store listing experiments для доступных graphics/descriptions | Выбрать настоящий target metric; проверить Console eligibility |
| Review readiness | Play declarations, Data safety, permissions, Billing и reviewer access | Проверять actual release и SDK, а не только маркетинговую страницу |
| TestFlight workflow | Internal, closed, open tracks и production | Для новых personal accounts есть отдельный gate closed testing |
| Минимальная ОС / SDK | `minSdk` и `targetSdk`, ежегодная Play target policy | Повышение target не равно автоматическому отказу от старых Android |

Источники Android-механик: [Listing schema](https://developers.google.com/android-publisher/api-ref/rest/v3/edits.listings), [App campaigns](https://support.google.com/google-ads/answer/6247380?hl=en-EN), [Play performance](https://support.google.com/googleplay/android-developer/answer/9859173?hl=en), [Experiments](https://support.google.com/googleplay/android-developer/answer/12053285?hl=en), [Testing accounts](https://support.google.com/googleplay/android-developer/answer/14151465?hl=en-en), [Target API](https://support.google.com/googleplay/android-developer/answer/11926878?hl=en).

## Что остается полезным

Сбор product truth, исследование аудитории, понятный оффер, локализация, качественная графика, небольшие проверяемые эксперименты и журнал решений применимы к обеим платформам. Хранить данные каждой платформы отдельно, затем сравнивать совместимые пользовательские этапы — discovery, намерение, установка, activation, retention, purchase.

Для переноса существующего iOS проекта первым результатом сделать Android brief: package name, рынки, доступные Android функции, отличия onboarding/paywall, Android SDK/data flows и статус Play account. Текст или изображения, показывающие только iOS функцию, требуют переработки до публикации.

## Чего этот репозиторий не доказывает

Набор не имеет доступа к developer account сам по себе, не публикует приложение, не создает рекламный расход и не гарантирует одобрение или рост. CLI может проверить локальные данные и подготовить результаты; marketplace metrics и policies остаются внешними источниками. Без доступа к Console анализ помечается как частичный.

Подробные правила находятся в [knowledge](../knowledge/play-foundations.md), практическая подготовка — в [review guide](play-review-guide.md). Открывать официальные ссылки снова перед фактическим submission, поскольку отчетность, eligibility и deadlines изменяются.
