# План Store listing experiment

Проверено: **2026-10-14**. Заполняйте на основе доступных настроек Google Play Console. Перед запуском прочитайте [метрики](../knowledge/play-metrics.md) и [официальную справку](https://support.google.com/googleplay/android-developer/answer/12053285?hl=en): доступные поля и метрики со временем меняются.

| Параметр | Что записать |
| --- | --- |
| Приложение и listing | Package, main/custom listing, версия |
| Гипотеза | Какой барьер устраняет изменение и почему |
| Аудитория | Язык/рынки/тип пользователей и ограничения |
| Control | Текущий текст/графика, сохраненный исходник |
| Variant | Один измененный элемент; ссылка на материал |
| Тип experiment | Default graphics или localized; проверенные Console eligibility и listing rollout |
| Primary metric | Точное название и определение в текущем Console |
| Guardrails | Activation/retention, жалобы, выручка, качество |
| Настройки | Доля трафика, MDE/confidence если доступны |
| Оценка | Условие достаточности данных и минимальный период с учетом сезонности |
| Остановка | Условия сбоя и согласованный предел времени/трафика |
| Confounders | Релиз, цена, реклама, сезонность, технические ошибки |
| Решение | Применить, продолжить, отклонить или результат неопределен |
| Владелец и журнал | Кто запускает/применяет, experiment ID, start/end и ссылки на результаты |

В текущей справке указаны `Unique user install clicks`, `Unique user open clicks` и `Unique user pre-registration clicks`. Сохраняйте точный label, его определение и источник экспорта: слово «clicks» не дает оснований приравнять метрику к собственному SDK `first_open`, activation или выручке. Для подтверждения downstream результата нужен согласованный источник продуктовой аналитики. Числа из учебного примера не являются расчетом мощности для вашего приложения.

## Выбор типа и аудитории

Default graphics проверяет icon/feature graphic/screenshots; localized добавляет descriptions. Локализованные graphic assets могут исключать пользователей соответствующего языка из default graphics experiment. Это выбор языка просмотра listing, не автоматический country targeting. На дату проверки Console допускает один default graphics или до пяти localized experiments, до двух variants; перепроверьте доступные настройки перед запуском. Источник: [Experiments](https://support.google.com/googleplay/android-developer/answer/12053285?hl=en).

Название приложения и keywords не считать доступными test fields, если Console их не предлагает. Если требуется другой аудитории custom listing, проверить ее наличие, targeting и eligibility отдельно. Control должен соответствовать реально активной карточке; сохранить материалы до изменений.

## Формулировка гипотезы

Учебный пример для приложения с существующим быстрым вводом расходов:

```text
Barrier: первый кадр перечисляет инструменты и не объясняет результат.
Change: заменить только message первого phone screenshot,
сохранив реальные UI, остальные кадры и visual style.
Control: «Категории и отчеты» + current export.
Variant: «Посмотрите, куда уходят деньги» + same capture.
Population: en-US listing viewers; проверенная Console аудитория.
Primary metric: точный доступный install-related label из Console.
Guardrail: существенное ухудшение activation/retention по сопоставимой
когорте, если такую когорту позволяет выделить доступная аналитика.
Stop: техническая ошибка, ложное обещание, согласованный предел времени.
Decision: применить только при достаточных данных и допустимых guardrails.
```

Guardrail на уровне всего приложения может смешивать control/variant. Если downstream analytics не связывает пользователя с variant, назовите это ограничением и не приписывайте разницу конкретному screenshot. Не связывать политику «меняем один элемент» с невозможностью сделать комплексный концепт: в таком тесте результат относится ко всему концепту, а причина отдельных эффектов неизвестна.

## Прочтение результата и журнал

Запишите по control/variant даты, объем/знаменатель, название метрики, point estimate, interval, MDE и Console recommendation. Не объявляйте winner по одному положительному дню; `More data needed`, `Draw` и пересечение неопределенности — полезные исходы, не ошибки. Временной предел выбирается по трафику и сезонности, а не универсальным числом дней. Console calculator дает оценку длительности, не гарантию завершения.

Сохраните confounders и причина решения: `apply / keep control / continue / inconclusive`. После разрешенного применения сверить активный listing и дату начала нового baseline. Применение variant меняет внешнюю карточку; нужен scope владельца. По текущей справке experiment автоматически останавливается через шесть месяцев, без применения variant. Источник: [Review/apply results и autocompletion](https://support.google.com/googleplay/android-developer/answer/12053285?hl=en).
