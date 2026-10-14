---
name: play-store-screenshots
description: Подготовка и локализация phone/tablet screenshots и feature graphic для Google Play из реальных Android captures; редактор, batch ZIP/manifest и headless export сохраненного проекта. Для Wear OS, TV, Automotive и XR нужны отдельные capture/profile workflow.
---

# Визуальные материалы Google Play

Подготовь последовательность скриншотов и feature graphic, которые представляют текущую Android-сборку. Прочитай [требования к графике](references/knowledge/play-creatives.md); перед live-загрузкой проверь актуальные [правила Google](https://support.google.com/googleplay/android-developer/answer/9866151?hl=en-GB).

## Brief, порядок и тексты

Используй уже известные product facts и запроси только отсутствующие материалы, меняющие результат: реальные captures, приоритет функций, локали/поддерживаемые устройства, стиль и доступные brand assets. При отсутствии brand rules выведи палитру из приложения и обозначь выбор. Не останавливай всю работу из-за отсутствия необязательной иконки, референса или отдельного шрифта.

Используй реальные экраны пользователя. Если их нет, сними запущенное приложение доступным инструментом Android-эмулятора или подготовь явно обозначенный концепт, который нельзя считать готовым пакетом для загрузки. Не выдумывай функции, отзывы, рейтинги и ценовые обещания. Масштабирование phone screenshot не демонстрирует опыт tablet или другого устройства.

До верстки подготовь storyboard: порядок → один понятный результат/сценарий → экран, который его доказывает → короткий заголовок → локаль. Примеры последовательности, копирайтинга и output manifest находятся в [производственном workflow](references/knowledge/play-creatives.md#план-последовательности-и-copy). Пиши варианты заголовков там, где выбор обещания действительно меняет дизайн; используй уже выбранную пользователем формулировку без повторного согласования. Не подменяй понятное обещание списком кнопок и функций.

Сохрани пропорции и читаемость UI, показывай основной опыт в первых трех кадрах. Указания Google о taglines до 20%, отсутствии hardware-рамок, центре feature graphic и alt text до 140 символов относятся к `Highly recommended`; обязательные технические требования и отдельные form-factor rules перечислены в knowledge. Не называй рекомендацию общим основанием для rejection. Соблюдай правдивость материалов и проверяй возможную обрезку.

## Локальная студия

[references/generator](references/generator) содержит Canvas-редактор без зависимостей и сетевой передачи файлов. Запусти:

```sh
python3 -m http.server 8000 --bind 127.0.0.1 --directory <skill-directory>/references/generator
```

`<skill-directory>` замени абсолютным путем к этому скиллу. Открой `http://127.0.0.1:8000` и следуй README генератора: выбери настоящий source device, загрузи PNG/JPEG, упорядочь кадры, отредактируй copy/локали и сохрани JSON-проект. Студия поддерживает phone portrait/landscape, 7/10-inch tablet, safe custom dimensions, stacked/split/UI-only layouts и настройки размеров текста/UI для профиля или отдельного кадра. Feature graphic — 1024×500. Экспорт всегда использует реальный capture; name/headline нужны для layout с marketing copy. Файлы имеют RGB PNG без alpha, preview guides исключены.

Проверь изображение при типичном размере на экране телефона. Сократи текст, который не помещается; не скрывай важный UI ради заголовка. Перепиши copy для каждой локали, проверь переносы, currency/date examples и glyph coverage. Студия зеркалит split composition и задает RTL text direction, но сохраняет сам capture. Для другого языка UI загрузи source override для выбранной локали/кадра. Fallback к default source отражается в manifest и требует проверки; не отражай UI по горизонтали. Для tablet используй настоящий tablet capture и предпочти UI-only layout.

Выбери export locales/profiles и создай ZIP со всеми подходящими кадрами, feature graphics и JSON/CSV manifest: порядок, device, source/fallback, alt text, dimensions и состояния проверки. Profiles без captures не создают кадры; проверь полноту пакета. Portrait/landscape exports — альтернативные наборы, итоговый upload должен соблюдать count на устройство. Сохрани JSON v2 вместе с PNG; старые v1 projects мигрируют при открытии.

## Headless export

Для повторяемого экспорта сохраненного проекта используй optional Node.js 20+/Playwright renderer из той же папки. Его dependencies устанавливаются только при необходимости CLI; browser editor не требует npm. Команды установки и limits находятся в generator README.

```sh
node <skill-directory>/references/generator/export.cjs --project /absolute/path/project.json --output /absolute/path/new-assets --zip
```

CLI использует тот же renderer, localhost и заблокированные внешние requests. Выходная папка должна быть новой; ошибки очищают staging exports. Проверь RGB файлы и визуальное отображение: system fonts/antialiasing зависят от browser environment. Локальный export не загружает материалы в Console.

## Техническая проверка

Запусти linked validator с явным типом материала:

```sh
python3 <skill-directory>/references/validator --kind screenshot output/en-US/phone-*.png
python3 <skill-directory>/references/validator --kind tablet-screenshot output/en-US/tablet-*.png
python3 <skill-directory>/references/validator --kind feature-graphic output/en-US/feature-graphic.png
```

`screenshot` сохраняет phone-профиль 320–3840 px и соотношение до 2:1; `tablet-screenshot` проверяет large-screen профиль 1080–7680 px и 9:16/16:9. Publisher применяет его к sevenInchScreenshots/tenInchScreenshots. Feature graphic проверяется на 1024×500. Для этих файлов нужен JPEG или 24-bit RGB PNG без alpha. Отличай обязательные размеры от рекомендаций для промоформатов; условия количества и device coverage смотри в knowledge.

Валидатор проверяет dimensions и encoding, CRC и размер сжатых scanlines PNG. JPEG scan data он не декодирует: открой JPEG и проверь фактическую отрисовку. Успешная техническая проверка не подтверждает policy, качество композиции, правдивость обещаний, перевод или необходимое число кадров. Верни исходные проекты, финальные файлы, порядок и локали, alt text и manifest со статусом каждой комбинации locale/device, плюс конкретные нерешенные проблемы. Для запроса A/B приложи control/variant и одну проверяемую гипотезу; не обещай рост конверсии. Загрузка выполняется только в пределах поручения пользователя.
