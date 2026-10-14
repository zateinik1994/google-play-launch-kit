# AGENTS.md — руководство для агента

Начни с этого файла: здесь маршруты задач, порядок запуска и возможности Google Play Launch Kit. После выбора задачи читай соответствующий скилл и нужные справочные материалы.

## Назначение репозитория

Набор помогает запускать и развивать Android-приложение в двух направлениях:

- **ASO:** конкуренты и запросы, локализованные title / short description / full description, графика карточки, подготовка к модерации и последующие итерации.
- **Google Ads App campaigns:** install-volume/tCPI и in-app-action/tCPA, PAUSED create, чтение и сверка, отчеты и разрешенные изменения бюджета/target/status.

Запросы про органические позиции и карточку относятся к ASO. Запросы про рекламный бюджет, conversion actions и стоимость привлечения относятся к Google Ads. У этих процессов общие сведения о продукте и креативы, но разные источники данных и способы управления.

В репозитории находятся инструкции и инструменты. Исходники приложения, реальные скриншоты и доступ к аккаунтам предоставляет пользователь. Работать можно из клона и через установленные скиллы.

## Сначала определи задачу

Выбери маршрут по поручению. Для узкой задачи используй нужные разделы; полный процесс запуска требуется при соответствующем запросе.

| Запрос | Где работать |
| --- | --- |
| Ключевые слова, конкуренты, ASO нового приложения | [play-aso-research](skills/play-aso-research/SKILL.md) и [keyword research](knowledge/play-keyword-research.md) |
| Название и краткое описание | [play-aso-research](skills/play-aso-research/SKILL.md) и [правила метаданных](knowledge/play-metadata.md) |
| Полное описание | [play-aso-research](skills/play-aso-research/SKILL.md): сценарии, функции, аудитория и монетизация |
| Проверка готового текста или локалей | [play-metadata](skills/play-metadata/SKILL.md) и [контракт CLI](docs/usage.md) |
| Скриншоты и feature graphic | [play-store-screenshots](skills/play-store-screenshots/SKILL.md) и [студия](examples/screenshots-generator/README.md) |
| Тексты, графика, AAB или release tracks | [play-metadata](skills/play-metadata/SKILL.md) и [Publisher API](docs/play-api.md) |
| Подготовка модерации или разбор отказа | [play-policy-review](skills/play-policy-review/SKILL.md) и [review guide](docs/play-review-guide.md) |
| Отзывы, аудит карточки, A/B гипотеза | [play-store-optimization](skills/play-store-optimization/SKILL.md) и [шаблон эксперимента](docs/experiment-template.md) |
| Позиции и результаты изменения метаданных | [play-aso-monitoring](skills/play-aso-monitoring/SKILL.md) и [метрики](knowledge/play-metrics.md) |
| Профили, выдача, подсказки, оценки конкурентов | [сбор ASO](docs/aso-data-api.md): public collection/AppStoreSpy, provenance и ограничения оценки |
| Выгрузка показателей Play | [Play reports](docs/play-reports-api.md): GCS/Console CSV и отдельные metric families |
| План или создание рекламы | [google-ads-launch](skills/google-ads-launch/SKILL.md) и [Google Ads API](docs/google-ads-api.md) |
| Проверка рекламы, рост CPA, предложения изменений | [google-ads-monitoring](skills/google-ads-monitoring/SKILL.md) и [decision gates](knowledge/google-ads-app-campaigns.md) |
| Запуск от исследования до публикации | Полный маршрут ниже |

## Полный маршрут запуска

Начни со сведений о продукте: реальные функции, аудитория, бесплатные/платные возможности, рынки и языки. Используй известные сведения; уточняй существенные пробелы. Package name нужен для операций с конкретным приложением через API. Его отсутствие не блокирует исследование и черновики.

```text
1. ASO-исследование
   play-aso-research: конкуренты → запросы → источники → релевантность → gap-анализ
                  ↓
2. Название и краткое описание
   play-aso-research + play-metadata: варианты → выбор → матрица локалей
                  ↓
3. Полное описание
   play-aso-research: сценарии, функции, монетизация, ограничения
                  ↓
4. Скриншоты и feature graphic
   play-store-screenshots: история продукта → реальные экраны → локализация → QA
                  ↓
5. Подготовка карточки Google Play
   play-metadata: тексты/графика/details → plan/diff → backup → API validate/commit
                  ↓
6. Готовность к модерации и выпуск
   play-policy-review: сборка, reviewer access, privacy/Data safety, declarations
   AAB/tracks/rollout: play_release; Data safety CSV: play_safety
   Остальные declarations/reviewer access и неподдерживаемые действия: Play Console
                  ↓
          Приложение доступно пользователям
                  ↓
7. Подготовка и создание рекламы
   google-ads-launch: tracking → baseline → экономика → assets → validateOnly
   API create оставляет Campaign + AdGroup + AdGroupAd PAUSED
   После проверки явный ads_manage status plan может активировать выбранные ресурсы
                  ↓
8. Регулярные итерации
   google-ads-monitoring: campaign/geo/asset reports → lag/cohort → budget/target/status plan
   play-aso-monitoring: сбор позиций/Play reports → discovery/gaps → план эксперимента
```

Подготовку к review начинай раньше при блокирующих проблемах сборки или данных. Для опубликованного приложения используй только нужные этапы.

**Связь ASO и рекламы.** Исследование помогает формулировать ценность и тексты assets. App campaigns автоматически управляют таргетингом; keyword bank не превращается в ручные exact-keyword ставки. До старта рекламы сохрани сопоставимый baseline доступных показателей Play и продукта вместе с определениями источников. Для оценки инкрементальности учитывай атрибуцию и сезонность; вычитание Ads conversions из общего числа установок не дает надежную органику.

**Зависимости материалов.** Тексты и графика описывают одну ценность и одну сборку. Сначала выбери основной сценарий и локали, затем готовь финальные материалы. Формулировки на скриншотах служат ясности сообщения; набор не утверждает, что Google индексирует подписи по правилам Apple.

Регулярность проверок определяется объемом данных и задачей. Расписание создавай по поручению пользователя; отсутствие новой информации не требует изменения карточки или бюджета.

## Рабочие правила

### 1. Подтверждай функции до выбора запросов

Текст должен соответствовать текущему продукту. Offline, AI, экспорт, синхронизацию, календарь и другие возможности включай при подтверждении. Различай реализованное, планируемое и неизвестное. Функция конкурента не становится функцией приложения пользователя.

### 2. Разберись с монетизацией

Запиши, что бесплатно, что требует покупки/подписки, какие ограничения у trial. Это влияет на описание, графику, рекламу и review. Не представляй платную функцию как общедоступную. Правила промо-заявлений — в [metadata](knowledge/play-metadata.md), требования к paywall/подписке — в [review guide](docs/play-review-guide.md).

### 3. Выполняй внешние изменения в пределах разрешения

Разрешение на конкретное действие может уже быть дано: учитывай его и не запрашивай повторно. Подготовка исследования или файлов сама по себе не разрешает менять карточку, выпускать приложение или расходовать бюджет. Если разрешения на внешнее изменение нет, сначала подготовь файл/diff/план, затем получи согласие на конкретное действие.

Различай offline-план, серверную проверку, создание ресурсов, commit, review и фактическую публикацию. PAUSED create не активирует рекламу. При неизвестном исходе записи проверь серверное состояние и receipt/backup до повтора.

### 4. Сохраняй происхождение и ограничения данных

- Неизвестный объем запроса оставляй неизвестным. У набора нет общедоступного официального Play Search Popularity 0–100.
- Подсказка поиска, позиция, частота слова в тексте и provider volume — разные наблюдения.
- Загрузки/выручку из внешних моделей обозначай как оценки с источником и периодом.
- Поисковая позиция требует времени, страны, языка, контекста и depth. Category chart и выдача по запросу — разные измерения.
- Примеры `examples/data/` вымышленные. Отсутствие ключа или данных не разрешает заполнять отчет догадками.

### 5. Показывай реальные экраны Android

Используй captures текущего приложения. Оформление фона, композиции и подписей выполняй отдельно. Если captures нет, получи их из доступной сборки/эмулятора или запроси у пользователя. Обозначенный макет для обсуждения не считается готовой графикой магазина. Проверь читаемость UI, права на материалы, локализацию и device coverage.

### 6. Пиши краткое описание понятным предложением

`shortDescription` объясняет пользу и основной сценарий. Банк запросов помогает выбрать естественные формулировки. Перечисление нерелевантных слов не заменяет описание. Контракт Play использует title, shortDescription, fullDescription; отдельные iOS subtitle и скрытое keyword field в него не входят.

### 7. Проверяй читаемость каждой локали

Перечитай название, описание и заголовки графики в контексте целевого языка. Проверь длину, отображение, поддержку locale магазином и соответствие языку UI. Повтор слова между полями оценивай по смыслу. Численные веса ранжирования и универсальная плотность ключей не являются установленными правилами Google.

## Карта репозитория

```text
.
├── AGENTS.md                         Маршруты и порядок работы
├── README.md                         Обзор для владельца
├── skills/
│   ├── play-aso-research/             Исследование и тексты
│   ├── play-metadata/                 Проверка и API карточки
│   ├── play-store-screenshots/        Методика графики и студия
│   ├── play-policy-review/            Review и разбор отказа
│   ├── play-store-optimization/       Отзывы, аудит, эксперименты
│   ├── play-aso-monitoring/           Последующие итерации ASO
│   ├── google-ads-launch/             План и PAUSED campaign
│   └── google-ads-monitoring/         Рекламные отчеты и решения
├── knowledge/
│   ├── play-foundations.md           Принципы и границы известных фактов
│   ├── play-keyword-research.md       Источники и запросы
│   ├── play-metadata.md               Поля и локали
│   ├── play-creatives.md              Требования к графике
│   ├── play-metrics.md                Метрики и итерации
│   └── google-ads-app-campaigns.md     Реклама и decision gates
├── docs/                             CLI, API, review, эксперименты
├── shared/
│   ├── cli.py                        Offline CLI
│   ├── analysis.py                   Анализ нормализованных CSV
│   ├── metadata.py                   Listing JSON validation
│   ├── play_api.py                   Android Publisher API v3
│   ├── play_release.py               Графика/AAB/tracks и backup/receipt
│   ├── play_safety.py                Официальный Data safety CSV POST
│   ├── image_validation.py           Phone/tablet/feature/icon checks
│   ├── store_data.py                 Bounded public Play collector
│   ├── appstorespy.py                22 типизированные Android API операции
│   ├── appstorespy_schema.json       Проверенный registry провайдера
│   ├── aso_tools.py                  Discovery/gaps/experiment planning
│   ├── play_reports.py               GCS reports/CSV/дневные агрегаты
│   ├── google_ads.py                 Ads create/reports/keyword ideas
│   └── ads_manage.py                 Snapshot/reconcile/update/activation
├── scripts/                          CLI wrapper, установка и валидаторы
├── examples/
│   ├── data/                         Учебные JSON/CSV
│   └── screenshots-generator/        HTML/CSS/Canvas студия
├── config/                           Пример brief и настройки доступа
├── tests/                            Offline-проверки поведения
└── .github/workflows/check.yml        CI без секретов
```

### Приоритет при противоречиях

Функции и условия продукта подтверждаются материалами пользователя и фактической сборкой. Правила платформы сверяй с актуальными официальными страницами Google, схемой API и Console выбранного приложения. Для методологии используй канонические `knowledge/` и `docs/`, учитывая дату и источник. Учебный пример не подтверждает правило или реальную метрику.

`skills/*/references/` доставляют те же общие материалы скиллам. Исправляй канонический файл при устаревшем правиле; не создавай конкурирующие копии.

## Инструменты анализа и их входные данные

Офлайн-команды принимают нормализованные файлы. Публичный collector получает профили, выдачу/позиции и отзывы; AppStoreSpy клиент — типизированные provider данные с billing/provenance. Estimates не становятся фактической выручкой. Сохраняй URL/дату/рынок/метод и разделяй реальные наблюдения и fixtures.

| Задача | Команда из корня клона | Режим и вход |
| --- | --- | --- |
| Папка приложения | `python3 scripts/playkit.py init workspace/my-app --package com.example.myapp` | Локальные project.json и папки; existing destination не перезаписывается |
| Проверка текста | `python3 scripts/playkit.py validate examples/data/listings.json` | Locale → Listing JSON, offline |
| Запросы | `python3 scripts/playkit.py keywords examples/data/keywords.csv` | Relevance и наблюдения пользователя, offline |
| Позиции | `python3 scripts/playkit.py ranks examples/data/ranks-before.csv examples/data/ranks-after.csv` | Два сопоставимых снимка, offline |
| Отзывы | `python3 scripts/playkit.py reviews examples/data/reviews.csv` | CSV и EN/RU словарь тем, offline |
| Рекламные показатели | `python3 scripts/playkit.py ads-report examples/data/ads.csv` | Campaign/day CSV выбранного action, offline |
| Рекламный brief | `python3 scripts/playkit.py ads-plan examples/data/campaign.json` | Draft для in-app action tCPA, offline |
| Тексты Play | `python3 shared/play_api.py list --package com.example.myapp` | Сетевое чтение через временный edit |
| Diff карточки | `python3 shared/play_api.py plan --input examples/data/listings.json` | Offline, optional `--current` для baseline |
| Google Ads report | `python3 shared/google_ads.py report --help` | Справка параметров; сам `report` делает сетевое чтение |
| Профили/поиск/позиции/отзывы | `python3 shared/store_data.py --help` | Сетевой bounded public collection; `--fixture` полностью offline |
| AppStoreSpy | `python3 shared/appstorespy.py query --body examples/data/provider-query.json` | Offline-plan; явный `--execute` может расходовать credits |
| Кандидаты/coverage/мощность | `python3 shared/aso_tools.py --help` | Offline discover/gaps/experiment, без ранговой модели или Console writes |
| Play CSV | `python3 shared/play_reports.py --help` | Download offline/`--execute`; normalize/summary offline |
| Play release | `python3 shared/play_release.py plan --config examples/data/play-release.example.json` | Offline; snapshot/validate/apply сеть только с `--live` |
| Data safety | `python3 shared/play_safety.py --help` | CSV plan offline; apply `--live` с prior export/backup |
| Ads budget/target/status | `python3 shared/ads_manage.py --help` | Snapshot/reconcile network; plan/validate/apply offline по умолчанию |

Подставляй реальные подготовленные файлы вместо fixtures. [docs/usage.md](docs/usage.md) описывает колонки CSV, сохранение результата и коды завершения.

Важные особенности:

- `keywords` упорядочивает редакционную релевантность, сохраняет volume и источник, не измеряет спрос. Relevance=0 остается в bank как `excluded`; в final shortlist он не входит.
- Пустой rank означает «за depth», пропущенная строка — отсутствие наблюдения. Разные source/depth не дают точного числового изменения.
- Темы `reviews` определяются словарем; проверь исходные тексты перед выводами.
- `ads-report` использует полный расход кампании и выбранную конверсию. Не суммируй повторенный cost отчетов для разных actions.
- Play click CTR, legacy acquisition conversion и качество cohort имеют разные определения: см. [play-metrics](knowledge/play-metrics.md).

## Доступ и внешние сервисы

Офлайн-анализ, методология и студия работают без credentials. Сеть подключается отдельно:

| Возможность | Что нужно | Инструкция |
| --- | --- | --- |
| Play list/export/apply --live | ADC со scope androidpublisher и доступ к приложению в Play Console | [Publisher API](docs/play-api.md) |
| Play release/Data safety --live | Те же Publisher credentials; Data safety требует prior Console CSV export | [Publisher API](docs/play-api.md) |
| Ads create/update/report/ideas | ADC со scope adwords, developer token, customer access; manager ID при соответствующей схеме | [Google Ads API](docs/google-ads-api.md) |
| Public Play collection | Optional `google-play-scraper`; явный market/locale, bounded limits | [Сбор ASO](docs/aso-data-api.md) |
| AppStoreSpy --execute | `APPSTORESPY_API_KEY`, действующий тариф/credits и разрешенный scope | [Сбор ASO](docs/aso-data-api.md) |
| GCS reports --execute | ADC со scope devstorage.read_only и доступ к выбранному report bucket | [Play reports](docs/play-reports-api.md) |

[config/api_keys.env.example](config/api_keys.env.example) описывает `GOOGLE_APPLICATION_CREDENTIALS`, `GOOGLE_ADS_DEVELOPER_TOKEN`, `GOOGLE_ADS_LOGIN_CUSTOMER_ID`, `APPSTORESPY_API_KEY`. Программы читают окружение и ADC; `.env` автоматически не исполняется. Храни credentials вне клона и не проси секреты в чате. Ads customer и supported API version передаются аргументами.

Особенности сетевых операций:

- Play list/export создают временный edit и удаляют его; новый edit инвалидирует прежний edit той же учетной записи. Учитывай параллельные publisher tools.
- Play apply без `--live` — offline-план. Text CLI сохраняет backup и использует `ERROR_IF_IN_REVIEW`. Release CLI получает свежие listing/details/images/bundles/tracks, сохраняет JSON и оригиналы image bytes до destructive writes, связывает AAB с фактическим versionCode, затем validate/commit. При unknown outcome используй receipt и read-back до повтора.
- Data safety — отдельный официальный POST вне edits, без validateOnly/read endpoint. `play_safety` требует prior CSV и сохраняет оба CSV/receipt до отправки; syntax validation не проверяет правдивость declarations.
- Ads plan/validate/create без `--live` — offline. Live validate использует validateOnly; live create после проверки создает все три рекламные сущности PAUSED и сохраняет receipt.
- Ads report/geo-report/asset-report/keyword-ideas и ads_manage snapshot/reconcile выполняют сетевое чтение. Управление existing budgets/target/status использует свежую сверку, validateOnly, повторную сверку, atomic mutate и read-back. `ENABLED` может начать расход; конкретное изменение должно входить в поручение. Conversion tracking этим CLI не создается.
- Store listing experiments/custom listing targeting/appeals остаются Console workflows; подтвержденные public endpoints для них не найдены. Power estimate не запускает эксперимент. Google Search keyword metrics не являются спросом Google Play.

Если доступа нет, продолжай подготовку и анализ имеющихся материалов. Назови недоступные измерения/действия; draft не считается отправленным запросом.

## Пути, установка и Python

Для всего набора используй Python **3.11+**. Offline CLI работает на стандартной библиотеке. Для сетевых команд настрой окружение:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Установку выполняй при соответствующем поручении; читать клон можно без нее:

```bash
./install.sh --dry-run
./install.sh                         # Codex
./install.sh --target claude
./install.sh --check
./install.sh --target claude --check
./install.sh --target directory --directory /absolute/path/to/skills --copy
```

`--check` показывает состояние установки, фактический Python и наличие optional dependencies для сети. Он не проверяет credentials или доступ к аккаунту. Симлинки используют общие материалы текущего клона, `--copy` раскрывает их для переносимой копии. Установщик не перезаписывает существующий скилл.

Команды с `<путь-скилла>` используют его реальное расположение:

```bash
# Из корня клона
python3 scripts/playkit.py validate examples/data/listings.json

# Из установленного скилла: подставь путь и свой JSON
python3 <путь-скилла>/references/shared/cli.py validate /absolute/path/to/listings.json
```

В соответствующих скиллах доступны те же `references/shared/` CLI и schema registry, включая collector/provider/reports, release/safety и Ads management. Пути студии/image validator указаны в screenshots-скилле. Фиксированный каталог `~/.claude` или `~/.codex` не предполагается. Public collector требует отдельной установки `requirements-collection.txt`; optional headless renderer — Node 20+/Playwright по README студии.

Материалы приложения сохраняй в выбранной папке, например `workspace/<app>/research`, `metadata`, `screenshots`, `reports`. Workspace, output/outputs и credentials исключены из Git. Учебные fixtures клиентскими данными не заменяй.

## Использование генератора графики

Студия — готовый локальный HTML/CSS/Canvas инструмент. Используй существующий код и layout, расширяй их при требованиях за пределами настроек.

| Что нужно | Файл |
| --- | --- |
| Поля, captures, локали | [index.html](examples/screenshots-generator/index.html) |
| Оформление редактора | [studio.css](examples/screenshots-generator/studio.css) |
| Layout/render engine, v1→v2 migration и RTL | [engine.js](examples/screenshots-generator/engine.js) |
| UI, reorder, locale sources, JSON save/open и ZIP/manifest export | [studio.js](examples/screenshots-generator/studio.js) |
| Offline headless CLI того же engine | [export.cjs](examples/screenshots-generator/export.cjs) |
| Порядок работы | [README студии](examples/screenshots-generator/README.md) |
| Методика содержания/device coverage | [screenshots-скилл](skills/play-store-screenshots/SKILL.md) и [play-creatives](knowledge/play-creatives.md) |

```bash
python3 -m http.server 8765 --bind 127.0.0.1 --directory examples/screenshots-generator
```

Открой `http://127.0.0.1:8765`, загрузи реальные PNG/JPEG, задай тексты/локали, device profile, layout и порядок кадров. Сохрани project JSON с исходниками; экспортируй RGB PNG или весь ZIP с JSON/CSV manifests. Presets: phone portrait/landscape, 7/10-inch tablet; feature graphic — 1024×500. Custom size не заменяет правила выбранного устройства.

Осмотри каждый экспорт: читаемость, полный UI, язык, обещания, порядок кадров. При различиях UI по языкам используй per-locale source override; fallback отмечается в manifest. RTL меняет композицию. Проверь файлы:

```bash
python3 scripts/validate_images.py --kind screenshot /absolute/path/to/phone-assets
python3 scripts/validate_images.py --kind tablet-screenshot /absolute/path/to/tablet-assets
python3 scripts/validate_images.py --kind feature-graphic /absolute/path/to/feature-graphic.png
```

Validator не проверяет содержание, число кадров, device coverage или одобрение review. JPEG проверяется по метаданным без полного decode — убедись, что он открывается. Сохрани JSON-проект вместе с PNG для последующих правок.

## Чеклист перед передачей результата

- [ ] Функции, аудитория, монетизация подтверждены; неизвестное обозначено.
- [ ] Страна, язык карточки и язык UI выбраны отдельно.
- [ ] У конкурентов/запросов/метрик есть происхождение и дата; измерение отделено от оценки.
- [ ] Relevance=0 исключена из shortlist; неподтвержденный volume не придуман.
- [ ] Title/short/full description читаемы и валидированы; locale поддерживается Play.
- [ ] Платные функции и ограничения последовательно объяснены в карточке, графике и продукте.
- [ ] Графика содержит реальные Android captures; экспорт осмотрен, локализован и проверен.
- [ ] Review findings имеют доказательства и статус; неизвестные data flows/SDK/permissions отмечены.
- [ ] Внешние изменения соответствуют разрешению; ранее данное разрешение учтено.
- [ ] Фактическое состояние названо: draft, validated-only, committed, created-paused, опубликовано.
- [ ] Для Play записи есть backup; при неизвестном commit состояние проверено до повтора.
- [ ] Для Ads проверены tracking, action, валюта/бюджет, география/языки, assets, decision gates.
- [ ] Baseline и условия оценки зафиксированы; PAUSED create не назван активным запуском.
- [ ] Отчет учитывает определения метрик, conversion lag и сопоставимость наблюдений.
- [ ] Переданы файлы, проверки, существенные пробелы и следующий шаг.

## При изменении самого набора

Обновляй канонические knowledge/shared/docs, сохраняй относительные references и возможность `--copy`. Описывай реализованное поведение. Для изменений кода проверяй затронутые CLI/API сценарии: offline defaults, контракты, backup/receipt, порядок записи, cleanup и неизвестный исход. Live операции для тестов требуют соответствующего разрешения.

```bash
python3 scripts/check_knowledge.py
python3 -m unittest discover -s tests -v
node --test examples/screenshots-generator/tests/engine.test.cjs
```

При изменении документации проверь ссылки и команды. Изменения студии проверь в браузере: upload, locale round trip, JSON save/open, preview/export и PNG encoding. Сообщи результат, проверки и существенные ограничения.
