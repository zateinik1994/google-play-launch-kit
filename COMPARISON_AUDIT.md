# Повторный аудит соответствия оригиналу

Дата: **2026-10-14**. Оригинал: [appstore-launch-kit](https://github.com/dmitriipolushin/appstore-launch-kit), GitHub HEAD `9145a369228b2e02656b6e82c5d742afeec001ff`; с прошлого сравнения не изменился. Android baseline: `a5cfefa`. Проверены AGENTS.md/CLAUDE.md, все восемь скиллов и их references, knowledge/docs, Python CLI/API, визуальный генератор, installer/config/plugin и CI. Функциональная карта — [FEATURE_PARITY](FEATURE_PARITY.md).

## Исправленные ошибки

| Область | Подтвержденный дефект | Исправленное поведение |
| --- | --- | --- |
| Keyword coverage | Терялись цифры: 7-day/30-day и 2FA/3FA считались одинаковыми | Numeric/alphanumeric tokens сохраняют смысл |
| Discovery | Фразы искусственно соединяли конец title и начало description | N-grams создаются внутри каждого поля |
| Gap evidence | Терялись country/source и конфликтующие decisions; последующий отчет терял fixture metadata | Страны разделены, conflicts явные, keyword provenance сохраняется отдельно |
| Profiles/inputs | Поврежденные ответы и другой appId могли пройти нормализацию | Package identity, types, limits и наблюденные поля проверяются до использования |
| Numeric analysis | Переполнение/потеря точности давали Infinity или ложный ноль | Непригодные значения отклоняются |
| Play CSV | Один исходный столбец мог стать visitors и acquisitions, давая ложные 100% | Duplicate mappings отклоняются; SHA256/encoding/source columns сохранены |
| Publisher rollback | Откат первого добавленного video сохранял новую ссылку | Отсутствие baseline video восстанавливается explicit empty value |
| Release versions | 42/0042 и совпавший `$uploaded` могли повторить одну версию | Numeric duplicates блокируются до track write |
| Publisher preflight | Existing backup/export обнаруживался после invalidating edit | Известные path/config errors блокируют credentials/edit заранее |
| API input errors | Некорректный JSON enum/URL мог вызвать traceback | Локальная ошибка с соответствующим exit code |
| Data safety | Повторное чтение CSV могло рассогласовать comparison, archive и payload | Единый bounded byte snapshot связывает все три этапа |
| Ads scope | Customer/action и parent relationships могли быть неподтвержденными | Проверяются точные resource identities и campaign→group→ad |
| Ads write result | Неверный тип mutate-result мог быть принят по resourceName | Typed result должен подтверждать ожидаемую операцию, иначе unknown/no retry |
| Ads files | Serialization/IO failure мог оставить неполный CSV/sidecar | Staging и exclusive publication сохраняют существующие файлы и очищают свой неполный результат |
| Output preflight | Dangling symlink обходил `.exists()` перед credential/billed setup | Ссылки и sidecars блокируются до подключения |
| Screenshot RTL | Script variants вроде ar-Latn/az-Arab определялись по языку | Явная письменность имеет приоритет |
| Screenshot sources | Feature preview мог показывать другой capture; prefix-ID deletion ломал соседний capture | Preview/batch source совпадают, удаляются только точные image keys |
| Screenshot packaging | Validator examples не соответствовали вложенным export paths, portable docs links были сломаны | Пути исправлены; docs/examples доставляются переносимой копии |
| Workspace safety | `--output` мог уничтожить собственный input; failed init оставлял частичные файлы | Защита source/aliases и staging cleanup |
| Installer | Копирование захватывало runtime dependencies | node_modules/.venv/caches исключены; исходники сохраняются |
| Readiness | Некорректный pending timestamp мог оставить частичный JSON | Все timestamp types проверяются; serialization выполняется до output open |

## Восполненные полезные возможности

- Own/competitor field coverage matrix по наблюдаемым профилям в совместимом locale/country, без difficulty/ranking score.
- Повторяющиеся фразы и feature-request cues в review sample с IDs/date/version и явными ограничениями dictionary метода.
- [Locale inventory и evidence checklist](docs/readiness.md) для конкретного package/build вместо недоказанных market revenue/translation/compliance прогнозов.
- [Review/publishing lifecycle GET](docs/play-api.md) без нового edit. Максимум20 non-obsolete summaries; PUBLISHED включает partial/halted releases и не подтверждает видимость листинга.
- [Персональные палитры кадров](examples/screenshots-generator/README.md) для контраста, сохраняемые в project и manifests.

AGENTS.md, маршруты скиллов, примеры и CI синхронизированы с итоговым поведением. CLI smoke теперь проверяет непустую coverage matrix и сохраненный fixture marker; успешный exit не заменяет содержательную проверку данных.

## Верификация и пределы

Исправления покрыты regression tests с fake transports; выполнены независимые reviews ASO, Publisher и Ads, реальные CLI-прогоны из `--copy` скиллов вне клона, проверка всей локальной Markdown-навигации и Chrome/editor/headless PNG/ZIP/manifests. ASO edge cases включают RU, fr-CA, es-419, неполные поля, UTF-16 и suppression. Browser checks включают EN/AR, phone/tablet, palette/source round trip и prefix IDs.

Локальный итог: **240 Python tests, 15 Node engine tests и 1 полный browser/CLI integration test — PASS**. Все восемь скиллов прошли quick_validate; канонические ссылки, раскрытые portable references и offline CI examples проверены. Реальные Google-аккаунты в этих проверках не использовались.

В этой проверке не выполнялись private/account API writes или billed AppStoreSpy вызовы. Тесты и primary schemas подтверждают локальное поведение и контракты; server eligibility, actual delivery и policy approval требуют соответствующего аккаунта. Android-границы и оставшиеся workflows перечислены в [FEATURE_PARITY](FEATURE_PARITY.md); Apple-specific mechanics и непроверенные числовые эвристики не представлены Android-фактами.
