# Google Ads App campaigns

Проверено: **2026-10-14**. Этот файл помогает подготовить план и оценить готовность; создание кампании и расход бюджета должны соответствовать конкретному поручению владельца.

## Механика

App campaigns автоматически комбинируют assets и оптимизируют показы на Search, Google Play, YouTube, Discover и Display. Есть сценарии installs, engagement и pre-registration. Источник: [About App campaigns](https://support.google.com/google-ads/answer/6247380?hl=en-EN).

Таргетинг автоматизирован: это не перенос Apple Search Ads exact/broad keyword структуры и ручных ставок по каждому запросу. Работа идет с целью, рынками, языками, бюджетом, conversion actions и материалами. Источник: [Assets and automated targeting](https://support.google.com/google-ads/answer/6357595?hl=en).

Поддерживаемая стратегия зависит от subtype и eligibility: tCPI, tCPA, maximize conversions, value/tROAS и другие доступные варианты нужно проверять в аккаунте. Android download conversions могут измеряться через Google Play, а in-app actions требуют корректного tracking. Источники: [Bid strategies](https://support.google.com/google-ads/answer/12073727?hl=en), [App conversion tracking](https://support.google.com/google-ads/answer/6100665?hl=en).

## Готовность до бюджета

Наши decision gates:

1. **Продукт:** app доступно в целевой стране, onboarding работает, листинг и paywall передают одну ценность.
2. **Measurement:** выбран реальный primary conversion, тестовые события проверены; дубли install/first_open/import устранены. Записаны окна атрибуции и источник выручки.
3. **Economics:** есть исходные данные для допустимого CPI/CPA либо честно выделенный research budget с пределом потерь. LTV не выдуман.
4. **Assets:** независимые тексты, изображения/видео и локализованный листинг готовы; рекламный оффер согласован с продуктом.
5. **Spend:** записаны валюта, средний дневной бюджет, срок, общий предел эксперимента, владелец и условие остановки. Прогноз не считается разрешением тратить.

## Размер теста

Google рекомендует для install-volume budget около **50× tCPI**, для in-app actions — **10–15× tCPA** в день, с учетом learning и conversion delay. Это рекомендация для обучения кампании, а не обязательная минимальная цена входа или обещание результата. Источник: [Set up campaigns depending on goal](https://support.google.com/google-ads/answer/6167156?hl=en).

Если владелец может выделить меньше, отметить вероятную нехватку данных; не увеличивать бюджет автоматически для соблюдения рекомендации. Возможные решения — подготовить measurement/органический трафик или ограниченный exploratory test с заранее согласованной неопределенностью.

Average daily budget — средний, а не жесткий дневной cap: для большинства кампаний начисление может достигать 2× дневного бюджета, месячный предел при неизменном бюджете обычно 30.4×. Проверять применимость к выбранной кампании и изменениям бюджета. Источник: [Spending limits](https://support.google.com/google-ads/answer/10486637?hl=en).

Иллюстрация, **не рекомендация расходов**: при tCPI 1 единица валюты правило 50× дает 50/день, а не гарантированные 50 качественных пользователей. Экономика оценивается по activation, retention и марже после возвратов/комиссий.

## Анализ результата

Сравнивать spend, install/in-app attributed conversions, conversion lag, качество по странам и cohorts. Изменять одну существенную настройку за раз и учитывать повторное обучение. Stop condition формулировать до старта: неверное событие, сломанный onboarding, согласованный предел потерь, либо недостаточная экономика после пригодного окна данных.

Ads installs не равны Play organic acquisitions. Дешевый CPI и рост брендовым поиском не доказывают инкрементальность. Для решения о масштабировании нужны качество привлеченной cohort и проверенная unit economics, а не обещание, что покупка установок сама повысит органический ранг. Связанные определения: [метрики](play-metrics.md).
