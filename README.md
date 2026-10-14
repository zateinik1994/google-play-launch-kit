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
| [play-aso-research](skills/play-aso-research/SKILL.md) | Конкуренты, keyword bank с источниками, локализованные метаданные |
| [play-store-screenshots](skills/play-store-screenshots/SKILL.md) | Заголовки, реальные экраны, PNG screenshot/feature graphic |
| [play-metadata](skills/play-metadata/SKILL.md) | Проверка, план, экспорт и загрузка текстов через Android Publisher API |
| [play-aso-monitoring](skills/play-aso-monitoring/SKILL.md) | Сравнение предоставленных наблюдений позиций и корректная интерпретация метрик |
| [play-store-optimization](skills/play-store-optimization/SKILL.md) | Проверка карточки, анализ отзывов, план Store listing experiment |
| [play-policy-review](skills/play-policy-review/SKILL.md) | Подготовка к модерации и разбор отказа Google Play |
| [google-ads-launch](skills/google-ads-launch/SKILL.md) | План, API validateOnly и создание action tCPA campaign в статусе PAUSED |
| [google-ads-monitoring](skills/google-ads-monitoring/SKILL.md) | Чтение App campaign отчетов через API и анализ нормализованного CSV |

Общая [база знаний](knowledge/) содержит источники и даты проверки. [Различия платформ](docs/platform-differences.md) объясняют адаптацию iOS-процесса к Google Play.

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

## Генератор графики

```bash
python3 -m http.server 8765 --bind 127.0.0.1 --directory examples/screenshots-generator
```

Откройте [локальную студию](http://127.0.0.1:8765). Загрузите реальные экраны, отредактируйте тексты и локали, экспортируйте PNG. Файлы обрабатываются в браузере. Инструкция: [README генератора](examples/screenshots-generator/README.md).

Phone screenshot preset — 1080×1920; feature graphic — 1024×500. [Validator](scripts/validate_images.py) проверяет размер/формат, а не содержание и принятие модерацией. Обязательные ограничения и рекомендации разделены в [базе графики](knowledge/play-creatives.md).

## Подключить API

Для live-команд требуется отдельная настройка прав и credentials:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Следуйте [Publisher инструкции](docs/play-api.md) или [Google Ads инструкции](docs/google-ads-api.md). [Шаблон переменных](config/api_keys.env.example) документирует конфигурацию; `.env` автоматически не исполняется.

Publisher CLI обновляет тексты основного листинга, сохраняет backup и явно требует `--live`. Он не загружает AAB/графику, не заполняет Data safety и не меняет release tracks. Google Ads CLI поддерживает конкретный сценарий Android in-app actions tCPA и создание в PAUSED; включение рекламного расхода — отдельное действие владельца. Live-проверка на реальном аккаунте не проводилась; тесты API используют подставные ответы.

## Что нельзя переносить из iOS

У Google Play нет скрытого keyword field и subtitle. Нет официальной общедоступной шкалы Play Search Popularity, которую этот набор мог бы получать как Apple Ads SP. Google Ads App campaigns не предоставляют аналог ASA ручной кампании с отдельной ставкой на каждый ASO-запрос. Объяснения и источники — в [сравнении платформ](docs/platform-differences.md).

Toolkit не скрейпит массово Play и не выдает предполагаемые выручку, download volume или ranking formula за измерения. Для исследования предоставьте экспорты ASO-сервиса, реальные наблюдения или используйте доступные агенту read-only источники с указанием происхождения данных.

## Проверки и поддержка

```bash
python3 -m unittest discover -s tests -v
python3 scripts/check_knowledge.py
```

GitHub Actions запускает офлайн-проверки без секретов. Предметные правила проверены **14 октября 2026**; перед запуском сверяйте текущие ссылки Google и настройки Console. Для модерации начните с [review guide](docs/play-review-guide.md), для эксперимента — с [шаблона](docs/experiment-template.md).

Лицензия собственного кода и инструкций — [MIT](LICENSE). Названия продуктов принадлежат их владельцам; проект не связан с Google или автором исходного iOS-набора.
