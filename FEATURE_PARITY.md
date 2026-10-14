# Сопоставление с App Store Launch Kit

Проверено **2026-10-14** по [исходному репозиторию](https://github.com/dmitriipolushin/appstore-launch-kit), snapshot `9145a36`. Таблица отражает методологию и фактическую автоматизацию Android-набора. Похожее название скилла само по себе не подтверждает равенство API-возможностей.

## Карта разделов

| Раздел оригинала | Android-раздел | Что адаптировано | Ограничения автоматизации |
| --- | --- | --- | --- |
| AGENTS.md | [AGENTS.md](AGENTS.md) | Два направления, роутинг, полный запуск, правила, структура, источники, инструменты, доступ, установка, генератор и checklist | Android-поля и поддерживаемые API-сценарии описаны отдельно |
| aso-collection | [play-aso-research](skills/play-aso-research/SKILL.md) | Brief/locale matrix, выборка конкурентов, intent/gap-анализ, shortlist, тексты, QA/handoff | Источники собирает агент/владелец; CLI нормализует предоставленный keyword CSV |
| app-store-screenshots | [play-store-screenshots](skills/play-store-screenshots/SKILL.md) | Storyboard, copy, последовательность, реальные captures, локали/устройства, требования и manifest | Студия поддерживает фиксированные phone/feature layouts; другие устройства и layout требуют доработки |
| asc-metadata | [play-metadata](skills/play-metadata/SKILL.md) | Локали, validation, plan/diff, read/export, backup, запись и recovery | Основной текстовый listing; графика/AAB/tracks/custom listings/declarations не реализованы |
| aso-monitoring | [play-aso-monitoring](skills/play-aso-monitoring/SKILL.md) | Baseline, timeline, сопоставимые позиции, traffic mix, метрики, experiment gates, журнал | Импортированные rank snapshots; автоматического сбора позиций и Console метрик нет |
| app-store-optimization | [play-store-optimization](skills/play-store-optimization/SKILL.md) | Проверка текста, review sampling/темы, гипотезы и readout экспериментов | Словарь EN/RU; эксперимент проводится в Console; универсальный ranking score не рассчитывается |
| review guide | [play-policy-review](skills/play-policy-review/SKILL.md) и [guide](docs/play-review-guide.md) | Сборка, app access, данные/SDK, permissions, paywall, rejection/appeal, шаблоны | Submission/appeal/rollout не выполняются собственным CLI |
| asa-launch | [google-ads-launch](skills/google-ads-launch/SKILL.md) | Цель, tracking, экономика, baseline, assets, plan, server validation, создание | Android acquisition in-app action tCPA, все три serving entities PAUSED; другие цели готовятся отдельно |
| asa-monitoring | [google-ads-monitoring](skills/google-ads-monitoring/SKILL.md) | Scope аккаунта/приложения, выбранная конверсия, lag/cohorts, экономика, decision gates, журнал | Campaign/day report и CSV; нет автоматической правки бюджета/ставок/status или asset/geo/cohort API-отчетов |
| AppStoreSpy toolkit | [keyword research](knowledge/play-keyword-research.md) и [CLI](docs/usage.md) | Происхождение оценок, конкурентная evidence matrix, нормализация | Собственного Android ASO-provider клиента нет |
| knowledge | [knowledge/](knowledge/) | Android-правила, sources/dates, метрики, локали, графика, гипотезы, реклама | Недоказанные Apple algorithm claims не адаптируются как факты Google |
| screenshots-generator | [Canvas studio](examples/screenshots-generator/README.md) | Реальные captures, локализованная copy, JSON save/open, RGB PNG | Нет batch export, drag reorder и загрузки в магазин |
| install/config/plugin | [installer](scripts/install_skills.py), [config](config/api_keys.env.example), [manifest](.claude-plugin/plugin.json) | Codex/Claude, links/copy/check, interpreter/dependency diagnostics, plugin metadata | Credentials/доступ проверяются отдельно; manifest не ставит Python dependencies |

## Различия платформ

- **Метаданные:** title/shortDescription/fullDescription вместо subtitle и hidden keyword field. Search keywords targeting custom store listings — отдельная функция Console; наш Publisher CLI ее не реализует.
- **Спрос:** Apple Search Popularity не является метрикой Play. Volume внешнего сервиса и наблюдаемые запросы сохраняют источник, рынок и период.
- **Реклама:** App campaigns автоматизируют таргетинг и оптимизацию по цели; ручная ставка на ASA keyword не переносится напрямую. Отсутствие нашего budget/status updater — ограничение реализации, а не запрет Google Ads API.
- **Графика:** Android device coverage и feature graphic имеют собственные правила. Фиксированный Canvas layout — выбор реализации; Google не требует именно этот генератор или один phone preset.
- **Review/метрики:** Play declarations, reviewer access, testing eligibility и определения Console проверяются по Android workflow. Metadata commit не равен готовому release.

Предметные источники: [metadata](knowledge/play-metadata.md), [creatives](knowledge/play-creatives.md), [metrics](knowledge/play-metrics.md), [App campaigns](knowledge/google-ads-app-campaigns.md), [platform differences](docs/platform-differences.md).

## Практическая граница текущей версии

Методология покрывает исследование, выпуск и итерации. Самостоятельно выполняются нормализация/проверки, сравнение наблюдений, reviews/Ads CSV-анализ, работа с текстами Play и указанный сценарий Google Ads API. Действия без собственного CLI выполняет владелец/агент через разрешенный источник или Console.

Для неподдерживаемой автоматизации сохрани цель пользователя, подготовь нужные данные/план и назови недостающий инструмент. Не подменяй install campaign action tCPA, отсутствие наблюдений нулевым трафиком или external estimate фактической выручкой.
