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
| App Review Notes / demo access | App content Sign-in details / reviewer instructions и policy-specific evidence | Пошаговый working access, роли, регион и MFA; не копировать Apple Notes как обязательное Play поле |
| Privacy labels / account deletion | Play Data safety, privacy policy и применимый in-app + web deletion путь | Классифицировать app/SDK data flows по определениям Play, а не копировать Apple ответы |
| IAP / StoreKit | Google Play Billing, products/base plans/offers и применимые программы | Проверять реальное предложение, eligibility, recurring terms и management в Android flow |
| App Store icon / device mockup | Отдельный 512×512 listing icon и form-factor captures | Launcher/adaptive icon не заменяет listing icon; iPhone frame не доказывает Android UI |
| Reject / Resolution Center | Play Policy status, исправление releases/declarations или evidence-backed appeal | Различать rejection/removal/suspension и проверить affected test tracks |
| TestFlight workflow | Internal, closed, open tracks и production | Для новых personal accounts есть отдельный gate closed testing |
| Минимальная ОС / SDK | `minSdk` и `targetSdk`, ежегодная Play target policy | Повышение target не равно автоматическому отказу от старых Android |

Источники Android-механик: [Listing schema](https://developers.google.com/android-publisher/api-ref/rest/v3/edits.listings), [App campaigns](https://support.google.com/google-ads/answer/6247380?hl=en-EN), [Play performance](https://support.google.com/googleplay/android-developer/answer/9859173?hl=en), [Experiments](https://support.google.com/googleplay/android-developer/answer/12053285?hl=en), [Testing accounts](https://support.google.com/googleplay/android-developer/answer/14151465?hl=en-en), [Target API](https://support.google.com/googleplay/android-developer/answer/11926878?hl=en).

Для дополнительных строк: [Prepare for review](https://support.google.com/googleplay/android-developer/answer/9859455?hl=en-GB), [Data safety](https://support.google.com/googleplay/android-developer/answer/10787469?hl=en), [User Data](https://support.google.com/googleplay/android-developer/answer/10144311?hl=en), [Subscriptions](https://support.google.com/googleplay/android-developer/answer/9900533?hl=en), [Preview assets](https://support.google.com/googleplay/android-developer/answer/9866151?hl=en-GB), [Enforcement](https://support.google.com/googleplay/android-developer/answer/9899234?hl=en).

## Что остается полезным

Сбор product truth, исследование аудитории, понятный оффер, локализация, качественная графика, небольшие проверяемые эксперименты и журнал решений применимы к обеим платформам. Хранить данные каждой платформы отдельно, затем сравнивать совместимые пользовательские этапы — discovery, намерение, установка, activation, retention, purchase.

Для переноса существующего iOS проекта первым результатом сделать Android brief: package name, рынки, доступные Android функции, отличия onboarding/paywall, Android SDK/data flows и статус Play account. Текст или изображения, показывающие только iOS функцию, требуют переработки до публикации.

По каждому артефакту записать `reuse / adapt / recreate / unavailable` с причиной и evidence. Например: брендовая палитра — reuse; тексты платной функции с другим Android offer — adapt; iPhone capture — recreate; история Apple Search Popularity — unavailable как Play measurement. Это сохраняет полезный исходный материал и делает пробелы переносимого проекта видимыми.

## Объем визуального инструментария

Оригинальный screenshot skill предлагает построение Next.js генератора и iPhone/iPad mockups. Здесь поставляется готовая local Canvas studio: реальные default/localized captures, reorder, три editable palettes, stacked/split/UI-only layouts и ratios по профилю/кадру, portrait/landscape phone/tablet и custom sizes, RTL text/composition, v1→v2 project migration и batch ZIP с RGB PNG/manifest. Optional Node/Playwright CLI повторяет export сохраненного проекта. Отсутствие Next.js и hardware mockup — выбор реализации. Произвольные vector layouts, Wear/TV/Automotive/XR profiles и автозахват исходного приложения требуют отдельного workflow.

## Чего этот репозиторий не доказывает

Набор не имеет доступа к developer account сам по себе и не гарантирует одобрение или рост. При явно настроенном доступе и разрешенном `--live` CLI может отправлять Publisher changes и Ads mutations; `ENABLED` может начать рекламный расход. Offline plan и validateOnly не подтверждают публикацию. Метрики и policies остаются внешними источниками; без нужного доступа анализ помечается как частичный.

Подробные правила находятся в [knowledge](../knowledge/play-foundations.md), практическая подготовка — в [review guide](play-review-guide.md). Открывать официальные ссылки снова перед фактическим submission, поскольку отчетность, eligibility и deadlines изменяются.
