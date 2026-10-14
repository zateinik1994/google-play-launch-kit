# Метрики листинга и роста

Проверено: **2026-10-14**. Не смешивать отчет о листинге, Google Ads и события внутри приложения.

## Смена отчетности в 2026 году

Официальная справка описывает переход June/July 2026: listing performance использует unique Install/Open/Pre-register clicks и **CTR** вместо legacy Conversion Rate. Acquisitions — отдельные outcomes в Statistics/exports. Visitors дедуплицируются в день и по dimension. Источник: [Understand and grow your app's user base](https://support.google.com/googleplay/android-developer/answer/9859173?hl=en).

| Метрика | Формула / смысл | Чего не доказывает |
| --- | --- | --- |
| Listing CTR | Уникальные клики выбранного действия / подходящие visitors ×100% | Успешную установку или запуск |
| Legacy acquisition CVR | Store listing acquisitions / совместимые store listing visitors ×100% | CTR новой отчетности |
| Activation rate | Пользователи с выбранным событием ценности / релевантная install или first-open cohort | Поисковый ранг |
| CPI | Расход / attributed install conversions | Цену удержанного или платящего пользователя |
| CPA | Расход / attributed события выбранного типа | Доход или прибыль |
| D7 retention | Возврат на D7 в явно определенной cohort | Lifetime value |

Формулы activation и экономических метрик — аналитические определения этого набора. Всегда записывать cohort, окно атрибуции, дедупликацию, timezone, дату выгрузки и точное поле из источника. При нулевом знаменателе результат `n/a`.

## Паспорт метрики и dataset

Перед выводом записать:

```text
source / raw_path / exported_at / report_version
package / main-or-custom listing / период / timezone
metric_name / numerator / denominator / unit / deduplication
country / language / traffic_source / install_state / app_version (если доступны)
cohort / attribution_window / conversion_lag / coverage / transformations
```

Это контракт аналитической работы, не формат, который все CLI принимают напрямую. Данные источника сохранять без изменения, normalized files — отдельно; произвольный Console/provider CSV нужно привести к [контрактам инструментов](../docs/usage.md). Метрики с одинаковым названием могут иметь разные определения после изменения отчета или SDK.

Сохранять counts и rates вместе. В расчетах использовать совместимые total numerator/denominator, а не среднее дневных процентов; дедуплицированные counts разных dimensions могут пересекаться. Например, рост 4% → 5% составляет +1 процентный пункт и +25% относительно baseline; эти представления не взаимозаменяемы. Пример математический, не benchmark.

Отсутствующая строка, privacy suppression, `Other`, unknown или неполный день не означают измеренный ноль. Описывать объем пропусков и влияние на вывод. Смена currency/action/unit требует отдельных рядов, а не объединения.

## Источники трафика

Нынешний listing report: `Google Play search` — brand/name search; `Google Play explore` включает browsing и категорийные запросы; `Ads and referrals` смешивает рекламу и referrals. Grow overview использует другую группировку, включая `Paid and direct`. Название канала не определяет рекламный расход. Источник: [traffic source definitions](https://support.google.com/googleplay/android-developer/answer/9859173?hl=en).

Для анализа сделать отдельные срезы доступного органического, brand, paid и referral трафика. Не соединять в один показатель данные с несовместимыми определениями. UTM показывает размеченный переход, а не подтверждает инкрементальность рекламной кампании.

Для действующих источников сопоставлять реальные определения: Ads clicks/selected conversions, Console visitors/clicks/acquisitions и продуктовые first_open/events. Toolkit [Ads report](../docs/google-ads-api.md) сохраняет полный campaign/day расход и одну выбранную conversion action, не уникальных installers. Из-за разных единиц учета и attribution простое вычитание Ads conversions из total Play installs не определяет organic.

Старая [страница acquisition/retention](https://support.google.com/googleplay/android-developer/answer/6263332?hl=en) явно относится к закрытому old Console report; ее каналы/даты/метрики не использовать как текущую схему. Для legacy Cloud Storage CSV читать [monthly report schemas](https://support.google.com/googleplay/android-developer/answer/6135870?hl=en) и не складывать organic total с вложенными search/browse. Вид legacy выгрузки не заменяет определения нынешнего listing report.

## Baseline, позиции и confounders

До изменения сохранить доступные current listing/материалы и наблюдения с контекстом. Журнал связывает proposal → actual submission/commit → фактическое появление → verification. Effect window начинается от проверенного воздействия, не от даты draft. У Play нет обещанного этим набором единого срока переиндексации.

Для before/after выбирать одинаковую длительность и weekday mix, сопоставимые сезоны/рынки/listings/source definitions. Записать release rollout, availability, price/paywall, product changes, ads spend/attribution, внешние кампании и concurrent experiments. Изменение среднего из-за country/traffic mix проверять отдельными совместимыми срезами.

Поисковый rank — отдельное наблюдение по query/country/locale/device-account context/time/depth/source. Category chart rank не является keyword rank; web search не воспроизводит Play search. Зафиксировать правила учета organic результатов и видимых ad blocks, не смешивать методы. В rank CSV контекст включать в `source`, так как bundled сравнение не учитывает произвольные дополнительные колонки.

Пустой rank означает «не найден в первых depth». Вход/выход за глубину, разные depth/source и missing observations не дают точного изменения мест. Для собственного summary можно считать число запросов в top N или долю в наблюдаемой глубине на неизменном keyword set и методе; это coverage выборки, не объем рынка и не автоматически weighted share of voice. Bundled CLI возвращает изменения отдельных наблюдений.

## Decision gates перед рекомендацией

Это проверки методологии набора, не требования Google:

| Gate | Что подтвердить | Если не подтверждено |
| --- | --- | --- |
| Product truth | Обещанная функция/условия есть в текущем Android опыте | Исправить misleading claim; exclude запрос |
| Exposure | Изменение реально показано выбранному listing/locale/сегменту | Проверить delivery, не считать эффект draft |
| Data quality | Определение/units/coverage, dedup, timestamps известны | Исправить вход/дать partial observation |
| Comparability | Источники, сегмент, периоды и confounders совместимы | Разделить ряды или снизить уверенность |
| Evidence sufficiency | Есть пригодная выборка и ожидаемое окно результата | Продолжить измерение, не объявлять победу |
| Product guardrails | Клики не сопровождаются неприемлемым вредом UX/quality | Проверить продукт/обещание до масштабирования |

Guardrails выбирать по задаче: успешный первый запуск, подтвержденная activation, retention, complaints/refunds, crashes/ANR, фактическая маржа. Их наблюдение в общей аналитике не означает измерение по randomized variant: если вариант нельзя связать с downstream cohort, не заявлять причинный эффект на retention/выручку. Vitals и rating definitions имеют свой scope; смотреть [Android vitals](https://developer.android.com/google/play/vitals) и [ratings](https://support.google.com/googleplay/android-developer/answer/138230?hl=en).

Не использовать универсальный rating порог, CPA, «нормальную Android конверсию» или длительность ожидания. Benchmark допускается при известном peer set/периоде/сегменте и такой же метрике; отсутствие benchmark — отсутствие данных. Для малого объема выбрать более крупный эффект/агрегацию только если сохраняется осмысленный сегмент, либо признать результат неопределенным.

## Эксперименты

На текущей странице настройки: unique install/open/pre-registration clicks; localized experiments — descriptions/графика, default — графика. Title не перечислен. Настройки и результат учитывают confidence interval/MDE; `More data needed` не победа. Источник: [Store listing experiments](https://support.google.com/googleplay/android-developer/answer/12053285?hl=en).

На той же help page нижняя таблица user metrics сохраняет старые install-based формулировки. Маркетинговая landing page также описывает acquisition/1-day retention. При такой несогласованности записать **фактическую target metric и определение текущей Console**, дату и source; не объявлять click результат успешной установкой. Если Console недоступна, заранее пометить metric confirmation как pending.

### Рабочий цикл

1. Найти barrier с evidence и определить segment/listing, hypothesis и предполагаемый механизм. Заполнить [шаблон](../docs/experiment-template.md).
2. Проверить eligibility и поддерживаемый asset. Сохранить current control/variants; обычно менять один существенный элемент для интерпретации его эффекта.
3. Выбрать точную primary metric, практический полезный эффект и доступные audience/MDE/confidence settings. Оценить пригодность traffic и downstream измерений; не изобретать fixed sample size без исходных assumptions.
4. Задать окно/условие оценки и условия остановки при реальном вреде/поломке. Для сезонного сравнения заранее покрыть нужный цикл; рекомендация Google [тестировать хотя бы неделю](https://google.play/business/store-listing-experiments/) учитывает weekdays/weekends, но не гарантирует достаточности данных за неделю.
5. После actual start проверить delivery/language, пропуски и concurrent изменения. При обычном промежуточном просмотре не переименовывать ранний высокий процент в winner.
6. Рассмотреть current Console status/interval, practical effect, gates и guardrails. Решения: apply в разрешенном scope, keep control, continue, draw/inconclusive или остановить из-за проблемы.
7. Сохранить результаты и rationale; после фактического применения проверить отображение и доступные продуктовые показатели. Draft plan, test configured, running, completed и applied — разные статусы.

Toolkit не создает эксперименты, не считает statistical power и не объявляет winner автоматически. Multi-element concept test допустим как общая гипотеза, но не измеряет вклад каждого изменения. Title/другие неподдерживаемые поверхности требуют иного дизайна; before/after остается наблюдением с альтернативными объяснениями.

## Связь ASO, рекламы и экономики

Согласовать метрику качества привлечения с продуктом: например, достижение реального value event, возврат или оплаченная подписка. Проверить deduplication, refunds, currency, attribution и margin. Cheap CPI или красивый CTR сами по себе не дают прибыльной cohort.

Рост paid и organic одновременно допускает гипотезы brand lift, сезонности и других общих причин; ровная органика не доказывает провал ASO. Для incrementality нужны подходящий control/дизайн и данные. Не использовать фиксированный organic multiplier или universal halo процент из чужого кейса. Исследование и эксперимент с экономикой не расширяют разрешение пользователя на рекламный расход.

Если оценивается ROI работы команды, записать ее стоимость, пригодный counterfactual, срок и marginal contribution после возвратов/комиссий. При отсутствии causal evidence дать сценарный расчет с assumptions, а не точную «выручку от ASO».

## Итерация и отчет

Отчет начинается с фактического изменения и scope: что измерено, где/когда, counts и rates, missing coverage. Затем возможные объяснения, пройденные/непройденные gates и небольшой приоритетный backlog `evidence → change → expected effect → primary metric → risk/effort → next review condition`.

В журнале сохранять before/after, status, даты воздействия/verification и итог `keep / change / test / inconclusive`. Operational alerts по сбоям могут требовать быстрых действий; маркетинговые итерации оцениваются по пригодности данных, не календарному количеству правок. Cadence предложить по traffic/lag/целям, а повторное расписание создавать только по поручению пользователя.
