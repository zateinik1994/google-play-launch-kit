# Сопоставление с App Store Launch Kit

Повторно проверено **2026-10-14** по [исходному репозиторию](https://github.com/dmitriipolushin/appstore-launch-kit), актуальный HEAD `9145a369228b2e02656b6e82c5d742afeec001ff`. Таблица сопоставляет реальные рабочие задачи и автоматизацию. Подтвержденные ошибки, дополнительные утилиты и независимые проверки описаны в [отчете аудита](COMPARISON_AUDIT.md). Android-механики не заменяют Apple APIs один к одному.

| Раздел оригинала | Android-раздел | Реализованная автоматизация | Граница |
| --- | --- | --- | --- |
| AGENTS.md | [AGENTS.md](AGENTS.md) | Два направления, роутинг, полный запуск, правила, структура, CLI, доступ, установка, генератор и checklist | Android-поля и permissions |
| aso-collection | [play-aso-research](skills/play-aso-research/SKILL.md) | Public profiles/search/reviews, scope/provenance, discovery n-grams, keyword bank, own/competitor coverage matrix | Product-fit и перевод требуют редакционной проверки; volume не выдумывается |
| app-store-screenshots | [play-store-screenshots](skills/play-store-screenshots/SKILL.md) | Phone/tablet presets, layouts/ratios, локализованные sources, RTL, reorder, PNG/ZIP/manifests | Нужны настоящие Android captures; автозахват приложения отдельным workflow |
| asc-metadata | [play-metadata](skills/play-metadata/SKILL.md) | Listing/details, image upload/replace/delete/reorder, AAB, tracks/rollout, backup/receipt, review/publishing GET без edit | App creation и остальные Console declarations не реализованы; lifecycle не подтверждает полную delivery |
| aso-monitoring | [play-aso-monitoring](skills/play-aso-monitoring/SKILL.md) | Сбор и сравнение rank snapshots, GCS download, CSV normalization и сегментные агрегаты | Public web rank отличается от personalized device; новый click export может требовать Console |
| app-store-optimization | [play-store-optimization](skills/play-store-optimization/SKILL.md) | Metadata validation, review collection/EN-RU темы/evidence/recurring phrases, competitor coverage, experiment sample/traffic estimate | Нет официального ranking score; experiment запуск/readout в Console |
| launch_checklist / localization_helper | [readiness](docs/readiness.md) | Target locale inventory, alternative asset sets, отсутствующие поля/локали, package/release evidence template/report | Provided records не доказывают compliance; fixed market revenue/translation multipliers не используются |
| review guide | [play-policy-review](skills/play-policy-review/SKILL.md) и [guide](docs/play-review-guide.md) | Data safety CSV validation/offline plan/официальный POST с prior export/backup | Truth audit, reviewer access, other declarations и appeals требуют владельца/Console |
| asa-launch | [google-ads-launch](skills/google-ads-launch/SKILL.md) | Install-volume/tCPI или in-app-action/tCPA, validateOnly, atomic PAUSED create | Conversion tracking, billing, MMP и другие campaign goals — отдельные workflows |
| asa-monitoring | [google-ads-monitoring](skills/google-ads-monitoring/SKILL.md) | Campaign/geo/asset reports, snapshot/reconcile, budget/target/status plan→validate→mutate→read-back | Creative/strategy/geo/event updates вне CLI; cohort/LTV требует продуктовых данных |
| AppStoreSpy toolkit | [ASO data API](docs/aso-data-api.md) | 22 Android операции по typed OpenAPI registry, queued/partial statuses и credits/provenance | Provider estimates остаются модельными; `--execute` billed |
| keyword suggestions/popularity | [ASO tools](docs/aso-tools.md), [Ads keyword ideas](docs/google-ads-api.md) | Provider suggestions/search jobs, listing n-grams, Google Search Keyword Planner | Нет официального Play Search Popularity; Google Search volume — другая поверхность |
| knowledge | [knowledge/](knowledge/) | Android sources/dates, метаданные, графика, метрики, эксперименты, реклама | Apple algorithm claims не объявляются фактами Google |
| screenshots-generator | [Canvas studio](examples/screenshots-generator/README.md) | Zero-dependency editor, JSON migration, per-asset palettes, script-aware RTL, batch ZIP и optional headless Node CLI | Font/browser context влияет на pixels; каждый экспорт требует визуального QA |
| install/config/plugin | [installer](scripts/install_skills.py), [config](config/api_keys.env.example), [manifest](.claude-plugin/plugin.json) | Codex/Claude links/copy/check, portable references, optional dependency diagnostics | Manifest не устанавливает Python/Node dependencies или credentials |

## Различия платформ

- Play title/shortDescription/fullDescription заменяют iOS subtitle и hidden keywords. Нет дополнительного hidden keyword budget.
- App campaigns автоматизируют targeting/optimization; ручное ASA keyword bidding не имеет прямого соответствия. Target costs обновляются на campaign уровне.
- Public search ranks, category charts, provider database search, modeled estimates и Keyword Planner — разные наблюдения. Сохраняются страна, язык, время, глубина и источник.
- Data safety использует собственные определения Google; CSV POST не проверяет реальные data flows и не заменяет review.
- Phone/tablet и feature graphic имеют собственные профили. Next.js и hardware mockups не обязательны для воспроизводимого Android export.

Предметные источники: [metadata](knowledge/play-metadata.md), [creatives](knowledge/play-creatives.md), [metrics](knowledge/play-metrics.md), [App campaigns](knowledge/google-ads-app-campaigns.md), [platform differences](docs/platform-differences.md).

## Оставшиеся workflows и пределы

В проверенной public API schema не подтверждены endpoints для создания Store listing experiments, таргетинга custom store listings и appeals. Toolkit готовит данные, assets и planning estimate; фактические действия выполняются через доступный разрешенный Console workflow. Другие App content declarations, reviewer access и eligibility также проверяются отдельно.

Google Ads automation покрывает документированные acquisition create и budget/target/status updates. Создание image/video assets, переключение strategy/conversion event/geo/language, импорт/связка GA4/MMP cohorts и общий stop-loss не реализованы этими CLI. Это границы набора, а не утверждение об отсутствии соответствующих API. Keyword bidding, Search Match, ASA impression share и Apple popularity относятся к другой рекламной механике.

Publisher и Ads writes покрыты offline fake-transport tests и независимым review; реальная публикация/расход на аккаунте не проверялись. Public collector проверен одним ограниченным чтением реальной карточки. Browser/headless exporter проверен локально на PNG/ZIP/manifests с EN/AR и phone/tablet. Эти проверки не гарантируют server eligibility, policy approval или маркетинговый эффект.

Для следующей задачи используй уже реализованный CLI, сохрани provenance и текущие gates. Неподдерживаемое действие назови явно; неизвестные данные не превращай в ноль или успешную публикацию.
