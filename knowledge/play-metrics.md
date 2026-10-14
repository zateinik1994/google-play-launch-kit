# Метрики листинга и роста

Проверено: **2026-10-14**. Не смешивать отчет о листинге, Google Ads и события внутри приложения.

## Смена отчетности в 2026 году

Официальная справка описывает переход June/July 2026 от результата установки к намерению: store listing performance использует unique Install/Open/Pre-register clicks и **CTR**, заменяющий legacy Conversion Rate. Acquisitions остаются в Statistics и legacy exports. Visitors дедуплицируются в день и по измерению; суммы дней/каналов не обязательно равны уникальным пользователям периода. Источник: [Understand and grow your app's user base](https://support.google.com/googleplay/android-developer/answer/9859173?hl=en).

| Метрика | Формула / смысл | Чего не доказывает |
| --- | --- | --- |
| Listing CTR | Уникальные клики выбранного действия / подходящие visitors ×100% | Успешную установку или запуск |
| Legacy acquisition CVR | Store listing acquisitions / совместимые store listing visitors ×100% | CTR новой отчетности |
| Activation rate | Пользователи с выбранным событием ценности / релевантная install или first-open cohort | Поисковый ранг |
| CPI | Расход / attributed install conversions | Цену удержанного или платящего пользователя |
| CPA | Расход / attributed события выбранного типа | Доход или прибыль |
| D7 retention | Возврат на D7 в явно определенной cohort | Lifetime value |

Формулы activation и экономических метрик — аналитические определения этого набора. Всегда записывать cohort, окно атрибуции, дедупликацию, timezone, дату выгрузки и точное поле из источника. При нулевом знаменателе результат `n/a`.

## Источники трафика

В нынешнем listing report `Google Play search` охватывает поиск названия/близкого бренда; `Google Play explore` включает browsing и категорийные запросы; `Ads and referrals` объединяет рекламу и переходы по ссылкам. В Grow overview используется другая группировка, включая `Paid and direct`. Поэтому `Ads and referrals` нельзя целиком объявлять платным, а `Paid and direct` — расходом Ads. Источник: [traffic source definitions](https://support.google.com/googleplay/android-developer/answer/9859173?hl=en).

Для анализа сделать отдельные срезы доступного органического, brand, paid и referral трафика. Не соединять в один показатель данные с несовместимыми определениями. UTM показывает размеченный переход, а не подтверждает инкрементальность рекламной кампании.

Google Ads clicks отличаются от Console visitors; attributed conversions могут отличаться от уникальных installers из-за единицы учета и атрибуции. Источник: [Using different data sources](https://support.google.com/googleplay/android-developer/answer/6263332?hl=en). В legacy CSV не складывать итоговую organic строку с ее search/browse подстроками: [Monthly report schemas](https://support.google.com/googleplay/android-developer/answer/6135870?hl=en).

## Эксперименты

На текущей странице экспериментов доступны цели unique install/open/pre-registration clicks; localized experiments позволяют тестировать descriptions и графику, default experiments — графику. Title не перечислен как экспериментальный asset. Результат зависит от confidence interval и minimum detectable effect; `More data needed` не является победой. Источник: [Store listing experiments](https://support.google.com/googleplay/android-developer/answer/12053285?hl=en).

Заранее записать сегмент, гипотезу, один изменяемый материал, выбранную метрику, минимально полезный эффект и допустимый риск. После результата проверить продуктовые guardrails: успешный первый запуск, activation, retention, complaints. Высокий CTR при неверном обещании способен ухудшить качество привлечения.

Без эксперимента до/после — наблюдение: сезонность, страна, paid mix и изменение продукта могут объяснять разницу. Не выдавать общую «нормальную конверсию Android» без сопоставимой категории и источника.
