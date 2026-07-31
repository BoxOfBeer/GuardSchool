# Цель
Сделать ожидаемое расположение админского CRUD «Обратной связи» (между «Аварийные шаблоны» и «Изменения») и подключить редактор TinyMCE для формы «Новости школы».

# Контекст
- Входные данные: замечание заказчика, что feedback-CRUD не в нужном месте, и вопрос о наличии TinyMCE в настройке школьных новостей.
- Ограничения: сохранить текущую логику API, не ломать существующие формы, fallback при недоступности CDN TinyMCE.
- Ожидаемый артефакт: новая вкладка Program Settings «Обратная связь», рабочие действия read/hide/block, TinyMCE-редактор контента новостей школы.

# План
1. Перенести feedback UI в Program Settings как отдельную вкладку после аварийных шаблонов.
2. Разделить статистику и feedback в `static/admin/stats.js` (экспорт рендера/байндинга feedback).
3. Подключить TinyMCE для `#school-news-content` с безопасным fallback на textarea.
4. Обновить локализации и agents.
5. Прогнать JS/JSON/Python проверки.

# Изменения (по файлам)
- `static/index.html`:
  - добавлена вкладка `programSettings.tabFeedback` между `emergency` и `changelog`;
  - добавлена pane `program-settings-pane-feedback` с `#feedback-admin-body`;
  - удалён блок feedback из секции «Статистика ТВ»;
  - уточнена подпись поля новости: «Текст новости (TinyMCE)».
- `static/app.js`:
  - в роутинг вкладок Program Settings добавлен `feedback`;
  - при открытии вкладки feedback вызываются `bindFeedbackAdminPanelOnce()` и `refreshFeedbackAdminPanel()`;
  - добавлены функции `ensureSchoolNewsTinyMce`, `getSchoolNewsEditorContent`, `setSchoolNewsEditorContent`;
  - сохранение/редактирование новостей переведено на TinyMCE API (с fallback).
- `static/admin/stats.js`:
  - `fetchAndRender()` оставлен только для статистики ТВ;
  - экспортированы `refreshFeedbackAdminPanel()` и `bindFeedbackAdminPanelOnce()` для использования во вкладке Program Settings.
- `static/locales/ru.json`, `static/locales/en.json`:
  - добавлен ключ `programSettings.tabFeedback`.
- `static/agents.txt`:
  - добавлено правило по расположению feedback-CRUD и TinyMCE/fallback для новостей.
- `docs/codex/2026-04-22T02-31-39_Действие_Перенос_feedback_и_TinyMCE_school_news.md`:
  - создан текущий аудит.

# Решения/обоснования
- Feedback оставлен на прежних API endpoint, изменено только место отображения в админке.
- TinyMCE подключается лениво: сначала пробуем уже загруженный `window.tinymce`, затем динамически подгружаем CDN; при ошибке редактор не блокирует форму и остаётся textarea.
- Порядок вкладок теперь соответствует ожиданию: `... → emergency → feedback → changelog`.

# Риски
- На стендах без доступа к CDN TinyMCE останется textarea (функционально корректно, но без WYSIWYG).
- Если одновременно открыты старые вкладки со старым DOM-кэшем, нужно hard reload для появления новой вкладки.

# Следующие шаги
1. На сервере обновить статику и проверить вкладку «Обратная связь» в Program Settings.
2. Протестировать ввод/сохранение новости через TinyMCE (вставка текста/ссылки/картинки URL).
3. При необходимости локально vendoring TinyMCE (без CDN) для оффлайн-инсталляций.

# DoD (проверка)
- [x] Feedback CRUD отображается во вкладке Program Settings.
- [x] Порядок вкладок: emergency → feedback → changelog.
- [x] Форма news использует TinyMCE, fallback на textarea сохранён.
- [x] Проверки JS/JSON/Python прошли.

# Мини-ревью (альтернативы)
1. Оставить feedback в «Статистике ТВ» — отвергнуто, противоречит требованию по расположению.
2. Жёстко требовать TinyMCE без fallback — отвергнуто, ломает оффлайн/ограниченные сети.
3. Выбран вариант lazy-load TinyMCE + fallback textarea.

# Откат
- Git-откат: `git checkout -- static/index.html static/app.js static/admin/stats.js static/locales/ru.json static/locales/en.json static/agents.txt docs/codex/2026-04-22T02-31-39_Действие_Перенос_feedback_и_TinyMCE_school_news.md`
