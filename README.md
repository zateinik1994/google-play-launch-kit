# Google Play Launch Kit

Набор скиллов, инструкций и инструментов для запуска и роста Android-приложения в **Google Play**: ASO, локализованная карточка, графика, модерация и Google Ads App campaigns.

Идея и организация вдохновлены [appstore-launch-kit](https://github.com/dmitriipolushin/appstore-launch-kit). Реализация написана для Android с нуля. Это инструментарий для работы с вашим приложением; исходников приложения здесь нет.

## Быстрый старт

Дайте AI-агенту эту папку или ссылку на свой опубликованный клон и поручение:

> Прочитай AGENTS.md. Подготовь ASO для моего Android-приложения: трекер привычек, рынок США, язык en-US. Сначала проверь фактические функции и монетизацию.

> Сделай графику Google Play из моих реальных скриншотов: пять phone screenshots и feature graphic, локали en-US и ru-RU.

> Проверь готовые метаданные, подготовь diff для Google Play и план публикации.

> Подготовь Google Ads App campaign: Android, США, событие subscription_started, средний дневной бюджет 50 USD. Сначала покажи план.

AI-агент начинает с [AGENTS.md](AGENTS.md) и читает нужный скилл.

## Что внутри

| Скилл | Возможности |
| --- | --- |
| [play-aso-research](skills/play-aso-research/SKILL.md) | Сбор конкурентов, discovery фраз, coverage gaps, 22 операции AppStoreSpy, тексты |
| [play-store-screenshots](skills/play-store-screenshots/SKILL.md) | Phone/tablet, локализованный UI, RTL, batch ZIP/manifests и headless export |
| [play-metadata](skills/play-metadata/SKILL.md) | Тексты, графика, AAB, tracks/rollout через Publisher API с backup и receipts |
| [play-aso-monitoring](skills/play-aso-monitoring/SKILL.md) | Сбор позиций, GCS reports, нормализация и анализ по сегментам |
| [play-store-optimization](skills/play-store-optimization/SKILL.md) | Сбор/анализ отзывов, аудит карточки, расчет sample size эксперимента |
| [play-policy-review](skills/play-policy-review/SKILL.md) | Review readiness, Data safety CSV/API, разбор отказа |
| [google-ads-launch](skills/google-ads-launch/SKILL.md) | Install tCPI/action tCPA, validateOnly и создание PAUSED |
| [google-ads-monitoring](skills/google-ads-monitoring/SKILL.md) | Campaign/geo/asset reports, snapshot/reconcile, budget/target/status updates |

Общая [база знаний](knowledge/) содержит источники и даты проверки. [Различия платформ](docs/platform-differences.md) объясняют Android-механику, а [сопоставление разделов](FEATURE_PARITY.md) показывает глубину методологии и фактические границы автоматизации относительно iOS-набора.

## Установка скиллов

Нужен Python **3.11+**. Можно работать прямо с клоном без установки. Для установки всех восьми скиллов:

```bash
./install.sh --dry-run                 # показать пути без изменений
./install.sh                          # симлинки в $CODEX_HOME/skills или ~/.codex/skills
./install.sh --target claude           # симлинки в ~/.claude/skills
./install.sh --check                   # проверить установку Codex
./install.sh --target claude --check
```

Симлинки используют единственные `knowledge/`, `shared/`, `docs/` в клоне; обновления подхватываются сразу. Не перемещайте клон после такой установки. Для переносимых копий:

```bash
./install.sh --copy
./install.sh --target directory --directory /absolute/path/to/skills --copy
```

`--copy` раскрывает внутренние симлинки. Обычное копирование с сохранением ссылок может нарушить пути. Установщик отказывается перезаписывать уже существующий скилл и не меняет другие настройки агента. Для Cursor и других агентов используйте AGENTS.md и инструкции из клона; формат установки зависит от вашего агента.

`--check` также показывает фактический Python, поддержку версии и наличие optional Google API dependencies. Отсутствие сетевых пакетов не мешает offline-командам; credentials и права аккаунта проверяются отдельно.

Для подключения всего клона как локального плагина Claude Code добавлен [.claude-plugin/plugin.json](.claude-plugin/plugin.json):

```bash
claude plugin validate /absolute/path/to/google-play-launch-kit
claude --plugin-dir /absolute/path/to/google-play-launch-kit
```

Используйте этот способ либо установку отдельных скиллов. Manifest и стандартная папка `skills/` описаны в [официальной инструкции Claude Code](https://code.claude.com/docs/en/plugins-reference). Runtime-загрузка плагина не проверена: Claude Code CLI отсутствует в текущем окружении.

## Проверить инструменты без аккаунта Google

```bash
python3 scripts/playkit.py validate examples/data/listings.json
python3 scripts/playkit.py keywords examples/data/keywords.csv
python3 scripts/playkit.py ranks examples/data/ranks-before.csv examples/data/ranks-after.csv
python3 scripts/playkit.py reviews examples/data/reviews.csv
python3 scripts/playkit.py ads-report examples/data/ads.csv
python3 scripts/playkit.py ads-plan examples/data/campaign.json
python3 shared/play_api.py apply --package com.example.habits --input examples/data/listings.json
```

Все примеры вымышленные. Последняя команда по умолчанию — офлайн-план. Подробности форматов и ограничений: [CLI](docs/usage.md), [Publisher API](docs/play-api.md), [Google Ads API](docs/google-ads-api.md).

Новая автоматизация также проверяется без аккаунта:

```bash
python3 shared/store_data.py profiles --package com.example.habits --locale en-GB --country GB --fixture examples/data/public-play-fixture.json --output output/demo-profiles.json
python3 shared/aso_tools.py discover --profiles output/demo-profiles.json --seed 'habit tracker' --output output/demo-candidates.json
python3 shared/aso_tools.py gaps --keywords output/demo-candidates.json --listings examples/data/listings.json --output output/demo-gaps.json
python3 shared/aso_tools.py experiment --baseline-rate 0.08 --mde-relative 0.15 --daily-visitors 1000 --output output/demo-experiment.json
python3 shared/appstorespy.py query --body examples/data/provider-query.json
python3 shared/play_reports.py normalize --input examples/data/play-performance.csv --output output/demo-performance.json
python3 shared/play_release.py plan --config examples/data/play-release.example.json
python3 shared/ads_manage.py plan --config examples/data/google-ads-update.json --current examples/data/google-ads-snapshot.json --output output/demo-ads-plan.json
```

Файлы `output/demo-*` создаются один раз; для повторного запуска выберите новые пути. Подробности: [сбор ASO](docs/aso-data-api.md), [offline tools](docs/aso-tools.md), [Play reports](docs/play-reports-api.md).

## Генератор графики

```bash
python3 -m http.server 8765 --bind 127.0.0.1 --directory examples/screenshots-generator
```

Откройте [локальную студию](http://127.0.0.1:8765). Загрузите реальные экраны, задайте тексты и локали, порядок и layout по кадрам. Экспортируйте все материалы ZIP с JSON/CSV manifests либо отдельные PNG. Файлы обрабатываются в браузере. Для воспроизводимого headless export сохраненного проекта доступен Node 20+ CLI с optional Playwright. Инструкция: [README генератора](examples/screenshots-generator/README.md).

Presets покрывают phone portrait/landscape и 7/10-inch tablet; есть безопасные custom dimensions, реальные captures по локалям и RTL composition. Feature graphic — 1024×500. [Validator](scripts/validate_images.py) имеет отдельный `tablet-screenshot` профиль и проверяет размер/формат. Содержание и принятие модерацией проверяются отдельно по [базе графики](knowledge/play-creatives.md).

## Подключить API

Для live-команд требуется отдельная настройка прав и credentials:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Следуйте [Publisher инструкции](docs/play-api.md) или [Google Ads инструкции](docs/google-ads-api.md). [Шаблон переменных](config/api_keys.env.example) документирует конфигурацию; `.env` автоматически не исполняется.

Publisher release CLI поддерживает listing/details, загрузку/замену/удаление/перестановку графики, resumable AAB upload, releases и staged rollout по точным track IDs. До изменения сохраняются данные и оригиналы изображений; неизвестный commit не повторяется автоматически. Data safety CSV отправляется отдельным официальным API с prior export/backup. Изменения требуют явного `--live`.

Google Ads поддерживает install-volume/tCPI и in-app-action/tCPA create в PAUSED, отчеты campaign/geo/assets, чтение и сверку кампаний, изменения бюджетов, target cost и статусов выбранных ресурсов. Перед write сверяется свежий snapshot; activation `ENABLED` может начать расход и должна входить в поручение. Keyword Planner дает отдельный сигнал **Google Search**, не Play query volume. Live-публикация и рекламные изменения на реальном аккаунте не проверялись; API-тесты используют подставные ответы.

Публичный сбор требует `pip install -r requirements-collection.txt`. AppStoreSpy использует `APPSTORESPY_API_KEY`, по умолчанию строит план и выполняет billed-вызов только с `--execute`. GCS reports требуют отдельного storage read scope и доступа к report bucket. Источники, версии, контекст и модельный характер оценок сохраняются.

## Что нельзя переносить из iOS

У Google Play нет скрытого keyword field и subtitle. Нет официальной общедоступной шкалы Play Search Popularity, которую этот набор мог бы получать как Apple Ads SP. Google Ads App campaigns не предоставляют аналог ASA ручной кампании с отдельной ставкой на каждый ASO-запрос. Объяснения и источники — в [сравнении платформ](docs/platform-differences.md).

Toolkit ограничивает публичный сбор и не выдает предполагаемые выручку, download volume или ranking formula за измерения. Создание Store listing experiments, targeting custom listings и appeals остаются Console workflows: публичные подходящие endpoints в проверенной схеме не подтверждены. Расчет мощности эксперимента дает planning estimate, а не решение движка Google.

## Проверки и поддержка

```bash
python3 -m unittest discover -s tests -v
python3 scripts/check_knowledge.py
node --test examples/screenshots-generator/tests/engine.test.cjs
```

GitHub Actions запускает офлайн-проверки без секретов. Предметные правила проверены **14 октября 2026**; перед запуском сверяйте текущие ссылки Google и настройки Console. Для модерации начните с [review guide](docs/play-review-guide.md), для эксперимента — с [шаблона](docs/experiment-template.md).

Лицензия собственного кода и инструкций — [MIT](LICENSE). Названия продуктов принадлежат их владельцам; проект не связан с Google или автором исходного iOS-набора.
