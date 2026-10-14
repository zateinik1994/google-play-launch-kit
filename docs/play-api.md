# Метаданные через Google Play Developer API

`shared/play_api.py` работает с официальным Android Publisher API v3. Он читает и экспортирует локализованные тексты основного store listing, проверяет локальный JSON и применяет изменения названия, краткого и полного описания, ссылки на YouTube. Ограничения полей и редакторские рекомендации находятся в [knowledge/play-metadata.md](../knowledge/play-metadata.md).

Этот клиент не загружает AAB, скриншоты, иконки или feature graphic, не меняет release tracks, Data safety и custom store listings, не создает рекламу Google Ads. У Google есть отдельные ресурсы для части этих операций; в данном CLI они не реализованы.

## Подготовка доступа

Для offline-команд достаточно Python 3.10+. Для сетевых команд установите дополнительную зависимость:

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

Серверный [validate](https://developers.google.com/android-publisher/api-ref/rest/v3/edits/validate) проверяет edit, но не заменяет проверку Google и не обещает мгновенную публикацию. [Commit](https://developers.google.com/android-publisher/api-ref/rest/v3/edits/commit) учитывает review и publishing settings приложения; появление карточки в магазине может произойти позже.

Сохраните выведенные edit ID, diff и путь backup в папке приложения. После commit проверьте Publishing overview/review state в Console и карточку нужной локали. `export` после commit может подтвердить серверные тексты, но не доказывает, что они уже отображаются каждому пользователю; такой экспорт также создает новый edit. Используйте отдельное имя файла и учитывайте другие процессы публикации.

Клиент всегда передает `changesInReviewBehavior=ERROR_IF_IN_REVIEW`. Если приложение уже имеет изменения на проверке, commit завершается ошибкой, не отменяя существующий review. В текущем API поведение по умолчанию другое: `CANCEL_IN_REVIEW_AND_SUBMIT`. Клиент не выбирает его автоматически. Для предусмотренных Google случаев, например изменений после отклонения, доступен явный флаг `--changes-not-sent-for-review`. Это не универсальный режим черновика; точную семантику определяет [документация commit](https://developers.google.com/android-publisher/api-ref/rest/v3/edits/commit).

## Ошибки и восстановление

До успешного commit клиент пытается удалить edit при ошибке. Успешный commit не сопровождается DELETE. Ошибка очистки выводится вместе с исходной ошибкой; HTTP 404 при очистке означает, что edit уже отсутствует. [Удаление edit](https://developers.google.com/android-publisher/api-ref/rest/v3/edits/delete) отбрасывает его неподтвержденные изменения.

При таймауте, HTTP 5xx или некорректном ответе на commit итог может быть неизвестен: сервер мог применить изменения, даже если клиент не получил подтверждение. CLI сообщает об этом и не повторяет commit. Проверьте Play Console перед повторным запуском. Попытка DELETE после такой ошибки не отменяет уже успешный commit.

До commit изменения находятся в edit и могут быть отброшены. После commit нет автоматического rollback: подготовьте новый проверяемый план с сохраненным снимком и при необходимости примените его отдельным запуском. Клиент сохраняет и обновляет только тексты; он не восстанавливает скриншоты, релизы или настройки приложения.

Восстановление baseline через `apply` возвращает тексты переданных локалей. Если предыдущий запуск создал **новую** локаль, которой нет в baseline, такое восстановление не удалит ее: удаление локали выполняется отдельным поддерживаемым способом и требует собственного проверенного scope. Также перед восстановлением сравните свежие серверные значения, чтобы не затереть последующие изменения владельца.

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
