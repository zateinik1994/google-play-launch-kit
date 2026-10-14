# Метаданные через Google Play Developer API

`shared/play_api.py` работает с официальным Android Publisher API v3. Он читает и экспортирует локализованные тексты основного store listing, проверяет локальный JSON и применяет изменения названия, краткого и полного описания, ссылки на YouTube. Ограничения полей и редакторские рекомендации находятся в [knowledge/play-metadata.md](../knowledge/play-metadata.md).

Текстовый CLI `shared/play_api.py` работает только с main listing. Для AAB, графики, контактов и release tracks реализован отдельный `shared/play_release.py`, описанный ниже. Data safety, custom listings и реклама относятся к другим поверхностям; не подставляйте их поля в Listing JSON.

## Подготовка доступа

Для набора используйте Python 3.11+. Для сетевых команд установите дополнительную зависимость:

```bash
python3 -m pip install "google-auth[requests]>=2"
```

Включите Google Play Android Developer API в Google Cloud. Дайте выбранной учетной записи доступ к нужному приложению в Play Console с разрешениями, соответствующими выполняемым операциям. Для service account добавьте его email в Users and permissions. Cloud IAM сам по себе не дает доступ к приложению в Play Console. Следуйте актуальной [официальной инструкции доступа](https://developers.google.com/android-publisher/getting_started).

Клиент использует Application Default Credentials со scope `https://www.googleapis.com/auth/androidpublisher`. Можно передать путь к credentials через переменную окружения:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/absolute/path/outside-repository/service-account.json"
```

Также подходят другие настроенные ADC, включая одобренный вашей инфраструктурой способ без постоянного ключа. Credentials не копируются в репозиторий и не выводятся CLI. Подробности — [Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials).

API требует уже созданное приложение. Первоначальное создание приложения, необходимые согласия и первичная подготовка релиза остаются в Play Console. См. [ограничения Edits API](https://developers.google.com/android-publisher/edits).

## Формат файла

Верхний уровень — объект с языковыми тегами; поля используют имена официального API:

```json
{
  "en-US": {
    "title": "Focus Timer",
    "shortDescription": "Plan focus sessions and follow your progress.",
    "fullDescription": "Start a focus session, take a break, and track your progress.",
    "video": "https://www.youtube.com/watch?v=abcdef12345"
  }
}
```

`title`, `shortDescription` и `fullDescription` обязательны для каждой переданной локали. `video` необязателен. При обновлении существующей локали отсутствие `video` сохраняет текущую ссылку; явное `"video": ""` передает пустую строку для удаления ссылки. Локали, которых нет в локальном файле, остаются без изменений. CLI не удаляет локализованные карточки. Схема ресурса описана в [Listing API](https://developers.google.com/android-publisher/api-ref/rest/v3/edits.listings).

CLI выполняет `listings.update` (PUT), поэтому файл является полным набором текстов **для переданной локали**, а не произвольным partial patch. Чтобы поменять только title, возьмите остальные два текста из свежего экспорта и меняйте только title. Не добавляйте `keywords`, `subtitle`, `whatsNew` или URL privacy policy: ресурс Listing и этот CLI их не поддерживают.

Языковые теги сверяйте с экспортом/списком языков Play Console. Локальный validator проверяет синтаксис тега, но не полный реестр поддерживаемых Play locales и не качество перевода; окончательную допустимость определяет сервер. Не переносите локали Apple механической заменой дефисов или названий регионов. Это основной store listing, а не custom listing по стране/кампании; default language, контакты и прочие app details лежат в других ресурсах и данным CLI не меняются.

## Локальная проверка и план

Команды выполняются из корня репозитория:

```bash
python3 -m shared.play_api validate --input listings.json
python3 -m shared.play_api plan --input listings.json
python3 -m shared.play_api plan --input listings.json --current before.json
python3 -m shared.play_api apply --package com.example.app --input listings.json
```

Все четыре команды выше работают без сети и credentials. `apply` по умолчанию возвращает `status: dry-run`. С флагом `--current` план сравнивает данные с ранее экспортированным JSON. Без него `baselineProvided: false`: план показывает предлагаемые значения без знания текущего состояния Google Play. Это не серверная проверка и не гарантия принятия карточки.

## Чтение и экспорт

```bash
python3 -m shared.play_api list --package com.example.app
python3 -m shared.play_api export --package com.example.app --output before.json
```

Эти команды обращаются к Google. Метод [listings.list](https://developers.google.com/android-publisher/api-ref/rest/v3/edits.listings/list) требует edit ID, поэтому клиент создает временный edit, читает карточки и удаляет edit. Экспорт совместим с локальным форматом и отказывается перезаписывать существующий файл.

**Даже такое чтение имеет побочный эффект:** новый edit делает невалидным предыдущий открытый edit той же учетной записи. Изменения в Play Console или commit другой учетной записи также могут сделать текущий edit невалидным. Не запускайте несколько инструментов публикации одновременно для одного приложения; см. [модель Edits API](https://developers.google.com/android-publisher/edits).

## Применение подготовленного изменения

Флаг `--live` явно включает изменение карточки:

```bash
python3 -m shared.play_api apply \
  --package com.example.app \
  --input listings.json \
  --backup outputs/before-2026-10-14.json \
  --live
```

Последовательность: локальная проверка → создание edit → свежий снимок карточек → сохранение резервного JSON → PUT изменившихся локалей → серверный validate → commit. При отсутствии изменений edit удаляется и возвращается `status: unchanged`. Если `--backup` не указан, используется уникальное имя в `outputs/play-backups/`. Ошибка сохранения снимка останавливает работу до первого PUT. `--current` относится только к offline-плану; live всегда получает свежий снимок.

Существующий `--output` для export или `--backup` для live apply отклоняется до загрузки credentials и создания edit, включая broken symlink. Выбирайте новые пути: создание лишнего edit могло бы инвалидировать другую незавершенную операцию этой учетной записи.

Серверный [validate](https://developers.google.com/android-publisher/api-ref/rest/v3/edits/validate) проверяет edit, но не заменяет проверку Google и не обещает мгновенную публикацию. [Commit](https://developers.google.com/android-publisher/api-ref/rest/v3/edits/commit) учитывает review и publishing settings приложения; появление карточки в магазине может произойти позже.

Сохраните выведенные edit ID, diff и путь backup в папке приложения. После commit проверьте Publishing overview/review state в Console и карточку нужной локали. `export` после commit может подтвердить серверные тексты, но не доказывает, что они уже отображаются каждому пользователю; такой экспорт также создает новый edit. Используйте отдельное имя файла и учитывайте другие процессы публикации.

Клиент всегда передает `changesInReviewBehavior=ERROR_IF_IN_REVIEW`. Если приложение уже имеет изменения на проверке, commit завершается ошибкой, не отменяя существующий review. В текущем API поведение по умолчанию другое: `CANCEL_IN_REVIEW_AND_SUBMIT`. Клиент не выбирает его автоматически. Для предусмотренных Google случаев, например изменений после отклонения, доступен явный флаг `--changes-not-sent-for-review`. Это не универсальный режим черновика; точную семантику определяет [документация commit](https://developers.google.com/android-publisher/api-ref/rest/v3/edits/commit).

## Ошибки и восстановление

До успешного commit клиент пытается удалить edit при ошибке. Успешный commit не сопровождается DELETE. Ошибка очистки выводится вместе с исходной ошибкой; HTTP 404 при очистке означает, что edit уже отсутствует. [Удаление edit](https://developers.google.com/android-publisher/api-ref/rest/v3/edits/delete) отбрасывает его неподтвержденные изменения.

При таймауте, HTTP 5xx или некорректном ответе на commit итог может быть неизвестен: сервер мог применить изменения, даже если клиент не получил подтверждение. CLI сообщает об этом и не повторяет commit. Проверьте Play Console перед повторным запуском. Попытка DELETE после такой ошибки не отменяет уже успешный commit.

До commit изменения находятся в edit и могут быть отброшены. После commit нет автоматического rollback: подготовьте новый проверяемый план с сохраненным снимком и при необходимости примените его отдельным запуском. Клиент сохраняет и обновляет только тексты; он не восстанавливает скриншоты, релизы или настройки приложения.

Восстановление baseline через `apply` возвращает тексты переданных локалей. Если предыдущий запуск создал **новую** локаль, которой нет в baseline, такое восстановление не удалит ее: удаление локали выполняется отдельным поддерживаемым способом и требует собственного проверенного scope. Также перед восстановлением сравните свежие серверные значения, чтобы не затереть последующие изменения владельца.

Если baseline не содержит `video`, а после него видео было добавлено, для удаления передайте явное `"video":""`: отсутствие поля сохраняет текущую ссылку. Для восстановления полного release-плана используйте `play_release` и его `rollback.json`, который уже учитывает это различие и удаление добавленных локалей.

| Ошибка/состояние | Проверка и следующий шаг |
| --- | --- |
| Нет ADC / HTTP 401 | Выбранный тип credentials, OAuth scope и актуальность доступа. Не передавайте ключ в чат. |
| HTTP 403 | API enabled, email и app permissions в Play Console, выбранный аккаунт. IAM Cloud не заменяет Console access. |
| App/edit/locale не найден | Package name, подготовка приложения в Console, supported locale, срок/валидность edit. Ошибка не означает, что надо создать новое приложение. |
| Validate/PUT rejected | Точный текст ошибки, обязательные поля и состояние приложения; исправьте локальный файл перед новой попыткой. |
| Changes already in review | Дождитесь завершения либо выполните отдельно порученное владельцем действие в Console. CLI не отменяет review автоматически. |
| Commit outcome unknown | Зафиксируйте edit ID и backup, проверьте Console/фактические тексты. Не повторяйте commit или apply вслепую. |
| Успех commit, но карточка старая | Review, managed publishing и нужная локаль/отображение; не отправляйте дубликат изменения ради ускорения. |

Коды завершения: `0` — успех или корректный dry run, `2` — ошибка локального ввода/файла, `1` — API, credentials или неопределенный результат commit. Для сетевых ошибок и ошибок Publisher API нет автоматического повторения операций; авторизация может обновить истекший access token.

## Проверка реализации

```bash
python3 -m unittest discover -s tests -p 'test_play_api.py' -v
```

Тесты используют фейковый transport и проверяют порядок операций, сохранение видео и резервной копии, отсутствие commit при ошибке validate, очистку edit и неопределенный исход commit. Они не обращаются к Google. Live-публикация на реальном аккаунте не проверялась.

Официальные страницы проверены 14 октября 2026 года. При смене API сверяйте поведение методов и права доступа с актуальной документацией Google.

## Assets, AAB, контакты и release tracks

`shared/play_release.py` выполняет несколько операций **в одном edit**. Доступ и scope те же, что выше. В клоне запускайте `python3 -m shared.play_release`, в установленном скилле — `python3 <skill-directory>/references/shared/play_release.py`.

```bash
python3 -m shared.play_release plan --config examples/data/play-release.example.json
python3 -m shared.play_release snapshot --package com.example.app --live --output before.json
python3 -m shared.play_release plan --config release.json --current before.json
python3 -m shared.play_release validate --config release.json --live --backup-directory outputs/validation-01
python3 -m shared.play_release apply --config release.json --live --backup-directory outputs/release-01
```

`plan` всегда offline. `validate`, `apply` и `snapshot` без `--live` также не загружают credentials и не обращаются к Google. `validate --live` выполняет uploads/изменения внутри временного edit, серверный validate и удаление edit **без commit**. Это реальная серверная проверка артефактов, не read-only вызов; она не означает policy approval. `apply --live` после успешного validate делает commit с `ERROR_IF_IN_REVIEW`. Snapshot создает временный edit, читает listings/details/bundles/tracks/image metadata и удаляет edit; он имеет ту же оговорку о concurrent edits.

Для ограниченного чтения images:

```bash
python3 -m shared.play_release snapshot --package com.example.app --language en-US --image-type phoneScreenshots --live --output phone-before.json
```

Без фильтра snapshot получает все 8 официальных AppImageType для существующих локалей. URL в snapshot — серверный preview, а не локальный бинарный backup. Live apply отдельно сохраняет оригинальные изображения перед изменением.

### Конфигурация

[Вымышленный пример](../examples/data/play-release.example.json) проходит offline plan, но требует собственного package и реально доступных versionCodes для live. Относительные пути файлов отсчитываются от папки JSON-конфига. Поддержаны:

| Поле | Операция |
| --- | --- |
| `package_name` | Обязательное приложение |
| `listings` | Locale map основного листинга, тот же контракт текста |
| `delete_listings` | Явный список удаляемых локалей; assets каждой локали резервируются |
| `details` | PATCH `contactEmail`, `contactWebsite`, `contactPhone`, `defaultLanguage`; отсутствующие поля сохраняются |
| `images` | Явные append/replace/delete/reorder по language/image_type |
| `bundle` | `file` AAB и optional `expected_version_code` |
| `tracks` | Exact API track IDs и полный желаемый список `releases` |
| `changes_not_sent_for_review` | Explicit boolean с семантикой commit API, не универсальный draft mode |

App details — публичные контакты, не privacy policy/Data safety. Источник: [AppDetails](https://developers.google.com/android-publisher/api-ref/rest/v3/edits.details).

### Images: upload, replace, delete и порядок

Ключи image type совпадают с [AppImageType](https://developers.google.com/android-publisher/api-ref/rest/v3/AppImageType): `icon`, `featureGraphic`, `phoneScreenshots`, `sevenInchScreenshots`, `tenInchScreenshots`, `tvScreenshots`, `tvBanner`, `wearScreenshots`. Пример фрагмента `images`:

```json
[
  {"language":"en-US","image_type":"phoneScreenshots","operation":"replace","files":["screenshots/01.png","screenshots/02.png"]},
  {"language":"en-US","image_type":"featureGraphic","operation":"append","files":["screenshots/feature.png"]}
]
```

`append` добавляет файлы; `replace` удаляет группу и загружает новые файлы последовательно в указанном порядке. `delete` с `ids:["image-id"]` удаляет выбранные изображения, с `all:true` — всю группу. `reorder` с `ids:["second-id","first-id"]` требует **каждый текущий ID ровно один раз**, резервирует оригиналы, удаляет группу и повторно загружает их в этом порядке. Новые IDs могут отличаться. Это композиция реальных [list/upload/delete/deleteall](https://developers.google.com/android-publisher/api-ref/rest/v3/edits.images), а не отдельный выдуманный reorder endpoint. После commit проверь порядок в Console и магазине.

В одной конфигурации допускается одна операция на language/type. Для upload нужен существующий listing этой локали или `listings` в том же config: текст записывается первым. Клиент проверяет вместимость группы (один icon/feature/banner, до восьми screenshots). Canonical [image validator](../shared/image_validation.py) проверяет размеры/формат phone, 7/10-inch tablet, icon и feature; остальные form factors проходят проверку файла, затем серверные ограничения и отдельный visual/policy review. Tablet profile использует 1080–7680 px и 9:16/16:9; это не способ превратить phone capture в tablet UI. JPEG scan data не декодируется полностью. Число нужных кадров и содержание не подтверждаются успешным API upload.

### AAB и версии

```json
{"file":"build/app-release.aab","expected_version_code":42}
```

Локально проверяются наличие файла, ZIP container, `BundleConfig.pb` и base manifest; локальный предел размера 2 GiB является ограничением этого клиента. Package, signing, SDK requirements и актуальную пригодность артефакта подтверждает сервер/Console. AAB передается через официальный [bundles.upload](https://developers.google.com/android-publisher/api-ref/rest/v3/edits.bundles/upload), resumable session init и потоковый PUT с увеличенным timeout по [media protocol](https://developers.google.com/android-publisher/upload). Session Location проверяется перед передачей credentials/media и не сохраняется в публичном receipt. Автоматических повторов upload нет.

Из ответа берется настоящий integer `versionCode`; при несовпадении с expected edit не коммитится. В `tracks[].releases[].versionCodes` строка `"$uploaded"` заменяется этим ответом; без `bundle` она недопустима. Клиент не угадывает versionCode из имени файла. SHA-256 локальных файлов проверяется при планировании и перед загрузкой, чтобы не отправить изменившийся артефакт.

Version codes уникальны по числовому значению: `"42"` и `"0042"` — одна версия. `$uploaded` также не должен совпадать с сохраняемой версией. При известном expected это проверяется локально, иначе — по ответу upload до отправки track PUT; совпадение отбрасывает edit без commit.

### Tracks, notes и rollout

```json
[
  {"track":"production","releases":[{
    "name":"42 gradual rollout",
    "versionCodes":["$uploaded"],
    "status":"inProgress",
    "userFraction":0.05,
    "releaseNotes":[{"language":"en-US","text":"Improved daily checklist."}]
  }]}
]
```

Используйте track ID из snapshot: `internal`, `production`, `alpha`/`beta` или конкретное имя существующего closed/form-factor track. Клиент не переименовывает «closed» в произвольный ID и не создает track/tester lists. `draft` не обслуживает пользователей; `completed` запрашивает полный выпуск; `inProgress` требует 0 < userFraction < 1; `halted` позволяет остановить дальнейшее обслуживание staged release. Полный массив включает версии, которые надо сохранить; пустой releases явно очищает track. Для `countryTargeting` поддержан production/inProgress; priority — 0..5. Источник схемы и статусов: [Track/Release](https://developers.google.com/android-publisher/api-ref/rest/v3/edits.tracks).

Release notes — уникальные language/text, максимум 500 Unicode code points на язык по [release guide](https://support.google.com/googleplay/android-developer/answer/9859348?hl=en). Locale syntax проверяется локально; поддержка и актуальные требования — сервером. Код не обходит production access/testing gate, review, country availability и managed publishing. Commit со статусом completed не доказывает, что выпуск уже виден пользователям.

### Review/publishing state без edit

Для состояния конкретного track доступен официальный [applications.tracks.releases.list](https://developers.google.com/android-publisher/api-ref/rest/v3/applications.tracks.releases/list). `release-state` использует GET вне Edits API и не создает edit:

```bash
python3 -m shared.play_release release-state --package com.example.app --track production
python3 -m shared.play_release release-state --package com.example.app --track production --live --output release-state.json
```

Первая команда offline. Live возвращает releaseName, точный track, activeArtifacts/versionCode и releaseLifecycleState с источником/временем чтения. Используйте конкретный versionCode для сопоставления отправленного AAB; имя релиза может повторяться. IN_REVIEW, APPROVED_NOT_PUBLISHED, NOT_APPROVED и PUBLISHED отражают разные стадии. По [схеме lifecycle](https://developers.google.com/android-publisher/api-ref/rest/v3/applications.tracks.releases), PUBLISHED включает частичный rollout и halted release; не означает полный rollout или видимость текста карточки в выбранном рынке/языке. API исключает obsolete releases и возвращает максимум 20: пустой ответ не доказывает историю релизов или одобрение приложения. Отсутствующее/неизвестное lifecycle значение не считайте approval. Команда только читает, не отправляет pending changes на review и не публикует approved release.

### Backups, восстановление и неизвестный исход

Перед **первой** загрузкой/PUT/PATCH/DELETE создается новая backup directory. Она содержит:

- `snapshot.json`: listings, details, текущие tracks/bundle metadata и IDs/URL/hash затронутых image groups.
- Оригинальные бинарные изображения + `assets.json` с путем и проверенным SHA-256.
- `rollback.json`: готовый config восстановления затронутых текстов/контактов/groups/tracks; добавленные локали удаляются явно, исходное отсутствие video восстанавливается пустой строкой.
- `transaction.json`: durable состояние staging/commit-pending/committed/validated-only либо staging-failed/commit-rejected/commit-outcome-unknown.
- `result.json` при подтвержденном результате.

Backup изображения скачивается без Publisher bearer token с разрешенных Google image hosts; SHA-256 или SHA-1 из API сравнивается с оригиналом. Если URL возвращает scaled preview, клиент пробует original-size variant и снова проверяет hash. При отсутствии checksum, недоступном файле или несовпадении **запись прекращается до destructive операций**. Existing backup directory не перезаписывается.

Заранее существующий backup path отклоняется до создания edit; остальные ошибки записи резервной копии блокируют изменение уже открытого edit. Восстановление проходит тот же план/validate/apply:

```bash
python3 -m shared.play_release plan --config outputs/release-01/rollback.json
python3 -m shared.play_release validate --config outputs/release-01/rollback.json --live --backup-directory outputs/restore-validation
python3 -m shared.play_release apply --config outputs/release-01/rollback.json --live --backup-directory outputs/restore-01
```

Rollback является новым изменением, требует соответствующего поручения и принимается сервером заново. Он не отменяет установку более новой версии на устройствах и не гарантирует возможность downgrade. Старые AAB представлены существующими versionCodes; Publisher не дает этому клиенту скачать исходный ранее загруженный AAB. Храните свои подписанные build artifacts отдельно.

Ошибка до commit удаляет edit; это не undo подтвержденного commit. Staging/pending receipt после прерывания не доказывает публикацию. При timeout/408/5xx или malformed commit result фиксируется неизвестный исход и автоматического повтора нет: сначала проверь Console/track/listing. Если после подтвержденного успеха receipt не удалось сохранить, результат выводится с `receipt_error`; повторять commit нельзя.

### Публичные API и границы

Сверено **2026-10-14** с [Android Publisher REST index](https://developers.google.com/android-publisher/api-ref/rest). Main listing, images, app contacts, bundle uploads и track releases автоматизированы выше. Для Data safety существует отдельный реальный `applications.dataSafety`, реализованный в `shared/play_safety.py` ниже. Для custom store listing targeting, Store listing experiments и прочих Console-specific анкет не подставляются неподтвержденные endpoints. Эти операции выполняются через доступную Console integration или UI в рамках поручения; способность загрузить release не заменяет заполнение declarations.

```bash
python3 -m unittest discover -s tests -p 'test_play_release.py' -v
```

Mocked tests проверяют media endpoints/session protocol, backup-before-write, hash gating, explicit image operations/order, actual versionCode binding, notes/rollout validation, track retention payload, remote validate без commit, persistent unknown outcome и offline defaults. Live-проверка с реальным аккаунтом не выполнялась.

## Data safety: отдельный официальный POST

`shared/play_safety.py` реализует [applications.dataSafety](https://developers.google.com/android-publisher/api-ref/rest/v3/applications/dataSafety): POST `/applications/{packageName}/dataSafety` с JSON `{"safetyLabels":"содержимое CSV"}`. Ответ успешной записи пустой. Метод находится **вне edit**, не имеет declaration GET или validateOnly и не участвует в backup/commit release-транзакции.

```bash
python3 -m shared.play_safety plan --package com.example.app --csv data-safety.csv
python3 -m shared.play_safety apply --package com.example.app --csv data-safety.csv
python3 -m shared.play_safety apply --package com.example.app --csv data-safety.csv --before-csv before-data-safety.csv --backup-directory outputs/safety-01 --live
```

Первые две команды offline. Для live необходим **предоставленный свежий before CSV из Console**: официальный метод не позволяет автоматически прочитать текущее declaration. Клиент сохраняет before/proposed CSV и durable receipt до POST; одинаковые исходные файлы не отправляются повторно. Каждая запись — отдельное внешнее изменение в пределах поручения пользователя; отсутствие edit означает отсутствие transactional undo.

Формат проверен на публичном CSV sample из [официальной Data safety справки](https://support.google.com/googleplay/android-developer/answer/10787469?hl=en) 14 октября 2026. Фактические headers: `Question ID (machine readable)`, **`Response ID (machine readable)`**, `Response value`, `Answer requirement`, `Human-friendly question label`. Принимается UTF-8/BOM, TRUE/FALSE/blank; проверяются CSV shape, уникальность question/response, обязательные ответы и максимум один TRUE для SINGLE_CHOICE. IDs из текущего шаблона передаются как есть, не генерируются из кода приложения. Conditional полноту, наличие всех SDK/data flows и правильность заявления подтверждает аудит продукта/Console, а не синтаксический validator. Public sample содержит демонстрационные ответы и не является declaration приложения пользователя.

Receipt состояния: submission-pending, submitted, submission-rejected или submission-outcome-unknown. Timeout/408/5xx/неожиданный ответ не повторяются автоматически; сначала проверь Console. `submitted` означает acceptance API, не одобрение policy или появление labels. Восстановление выполняется новой явной записью сохраненного before CSV с новым prior export/backup, если входит в поручение.

Каждый CSV читается один раз за операцию с локальным пределом 4 MiB. Сравнение, SHA-256, архивные файлы и payload используют один снимок этих байтов; изменение исходного файла во время запуска не подменяет подготовленный snapshot. При одинаковых proposed/prior байтах результат `unchanged`, без credentials, backup и POST. Существующая backup-папка для измененного declaration отклоняется до загрузки credentials.

```bash
python3 -m unittest discover -s tests -p 'test_play_safety.py' -v
```

Из установленного скилла используется `python3 <skill-directory>/references/shared/play_safety.py`. Credentials — те же ADC/scope androidpublisher, без сохранения секретов в файлы.
