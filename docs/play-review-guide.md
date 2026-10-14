# Подготовка к Google Play review

Проверено: **2026-10-14**. Применять к реальному приложению и конкретному типу выпуска. Перечень ниже — рабочая проверка набора, а не полный каталог Google Play Policies.

## Входные материалы

Собрать package name, тип/дату создания developer account, страны и форм-факторы, AAB/versionCode, merged manifest, target/min API, список SDK с версиями, ссылки privacy/deletion, модель монетизации, доступ рецензента и текущие declarations в Console. Без сборки или Console можно проверить документацию и листинг, но результат обозначить как частичный аудит.

Хранить секретные тестовые пароли в защищенном канале владельца, не в публичном репозитории. В отчет записывать существование и работоспособность доступа без раскрытия credentials.

## Build и доступ к production

| Проверка | Актуальное правило / действие |
| --- | --- |
| Package / version | Package name уникален и постоянен; новый выпуск требует большего `versionCode` |
| Signing | Проверить release signing и Play App Signing, различать upload key и app signing key |
| Target API | С 2026-08-31 новые phone/tablet apps и updates: Android 16 / API 36+; Wear OS и Automotive 35+, TV и XR 34+ |
| Existing availability | Для уже опубликованного mobile app отдельный порог API 35; это не разрешение прислать новый update с API 35 |
| 16 KB | Проверить `.so`/native SDK, packaging/alignment и запуск на устройстве 16 KB; чистый Java/Kotlin стек также протестировать |
| Новые personal accounts | Созданные после 2023-11-13: closed test, минимум 12 opted-in testers непрерывно 14 дней до заявки на production access |

Package/version/signing: [Create and set up your app](https://support.google.com/googleplay/android-developer/answer/9859152?hl=en). Target и исключения: [Target API requirements](https://support.google.com/googleplay/android-developer/answer/11926878?hl=en). Тестирование: [New personal accounts](https://support.google.com/googleplay/android-developer/answer/14151465?hl=en-en).

**Даты, которые нельзя считать постоянными.** На дату проверки target-policy допускает запрос extension до 2026-11-01; наличие/применимость проверять в Notifications приложения. А текущая [16 KB compatibility guidance](https://developer.android.com/guide/practices/page-sizes) указывает 2027-02-01 как дату блокировки несовместимых updates для API 35+ на 64-bit devices. Это снимок источника, не утверждение о статусе всех аккаунтов. Не брать старый deadline из блогов; перед выпуском заново открыть guidance и warning конкретной сборки.

Наличие 12 адресов в testers list не доказывает непрерывный opt-in. Выполнение порога позволяет **подать заявку**, не гарантирует production access. Сохранить реальные сценарии тестирования, найденные дефекты и внесенные исправления.

## App content и работающий доступ

Проверить declarations: ads, target audience/content, rating, Sign-in details и актуальные category-specific формы. Если функция закрыта логином, membership, географией или другим ограничением, дать рецензенту работающий способ ее проверить; учесть OTP/MFA. Декларации должны соответствовать доступной сборке. Источник: [Prepare your app for review](https://support.google.com/googleplay/android-developer/answer/9859455?hl=en).

Наш практический smoke test: чистая установка, вход/гостевой режим, основная функция, отказ в разрешении, потеря сети, purchase/restore при наличии и удаление аккаунта при наличии. Проверить ссылки на отдельном устройстве без developer session. Для доступа рецензента записать необходимые действия, тестовые данные и ограничения; не прятать существенные функции специальным review-only UI.

## User Data и Data safety

Privacy policy должна быть доступна в Console и приложении, описывать реальное обращение с данными. Если приложение создает пользовательские аккаунты, нужны доступный путь запроса удаления внутри приложения и внешняя web-страница; freezing не заменяет удаление. Обоснованное хранение части данных раскрывается явно. Источник: [User Data policy](https://support.google.com/googleplay/android-developer/answer/10144311?hl=en).

Data safety заполняется для приложения с учетом SDK и текущей реализации. «Нет своего backend» не доказывает отсутствие сбора SDK. Даже без сбора данных обычному публикуемому приложению требуется форма; исключение для приложения исключительно в internal testing не переносить на closed/production. Источник: [Data safety form](https://support.google.com/googleplay/android-developer/answer/10787469?hl=en).

Для каждого data type составить фактографическую строку:

```text
data type → feature / SDK → destination → purpose → retention → deletion
evidence: код, SDK documentation, настройки или проверенный сетевой запрос
form answer: collected / shared / optional / required / exception + обоснование
```

Автоматический scanner не знает всех серверных потоков, remote config и contracts. Если поведение SDK неизвестно, отметить `unverified` и запросить факты у владельца, не выбирать «не собираем» по умолчанию.

## Permissions

Сверить **merged manifest релизной сборки**, а не только source manifest: библиотека может добавить разрешение. Для чувствительных API проверить необходимость основной функции, минимальный scope, disclosure/consent и отдельную declaration, если она требуется. Background location, например, должна иметь значимую связь с core functionality и проходит permission declaration review. Источник: [Background location requirements](https://support.google.com/googleplay/android-developer/answer/9799150?hl=en).

Наш подход к остальным разрешениям: при наличии SMS/Call Log, Accessibility, all-files, photos/video, health или advertising ID открыть **их текущую отдельную policy** и сохранить URL. Не объявлять весь класс разрешений запрещенным и не утверждать, что runtime consent автоматически обеспечивает соответствие.

## Billing и подписки

Цифровые функции/товары в Play-distributed app обычно требуют Google Play billing, с исключениями и региональными программами из текущей политики. Физические товары/услуги имеют другую механику. Не переносить региональное исключение на весь мир. Источник: [Payments](https://support.google.com/googleplay/android-developer/answer/9858738?hl=en).

Для subscription прозрачно показать цену, период, автопродление, условия trial и необходимость подписки; пользователь должен понимать предложение до покупки. Источник: [Subscriptions](https://support.google.com/googleplay/android-developer/answer/9900533?hl=en). Практически проверить покупку, подтверждение entitlement, restore и путь управления подпиской с реальным поддерживаемым Billing flow.

## Листинг и дополнительные категории

Пройти [metadata](../knowledge/play-metadata.md) и [creatives](../knowledge/play-creatives.md): фактические функции, paywall/интернет/аккаунт, длины, подходящие локали, права на материалы и реальный Android UI. Не обещать результат, который текущая сборка не дает.

Если аудитория включает детей, проверить Families и advertising SDK eligibility: [Target audience](https://support.google.com/googleplay/android-developer/answer/9867159?hl=en-en). Если приложение генерирует пользовательский контент с AI, отдельно проверить ограничения и встроенный reporting/flagging: [AI-Generated Content](https://support.google.com/googleplay/android-developer/answer/13985936?hl=en). Для UGC, health, finance, news, VPN, gambling и других фактических категорий добавить применимые проверки из Policy Center, не утверждать их соответствие по одному общему checklist.

## Результат аудита

Для каждой находки: severity (`blocker`, `risk`, `improvement`), статус (`confirmed`, `unverified`, `not-applicable`), доказательство из приложения, официальный URL и checked date, точное исправление и способ повторной проверки. Отсутствие доказательств не означает нарушение, а отсутствие найденных нарушений не означает одобрение Google.

Пример: «`unverified / risk`: analytics SDK присутствует, но data flows и Data safety ответы не предоставлены; сверить SDK config и outgoing payloads, затем обновить таблицу и форму».

После исправлений сверить Publishing overview, активные tracks, предупреждения релизной сборки и план выпуска. Отправку на review и rollout выполнить только в пределах поручения владельца. [Prepare and roll out a release](https://support.google.com/googleplay/android-developer/answer/9859348?hl=en) описывает текущий Console workflow.
