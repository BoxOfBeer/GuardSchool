# Цель
Закрыть доработки по требованиям: подтвердить мобильную «Обратную связь», добавить alias-совместимость имен RSS-виджета и зафиксировать релизную запись 1.02.035 в changelog.

# Контекст
- Входные данные: требования по feedback-функции, интеграции news-виджетов и записи в changelog; рекомендация архитектурного нейминга `external_news` / `rss_feed`.
- Ограничения: не ломать существующие конфиги `rss_news`, не переносить бизнес-логику в UI.
- Ожидаемый артефакт: совместимые типы RSS-виджета, нейтральные подписи RU/EN, обновлённый `APP_VERSION` и запись релиза.

# План
1. Привести backend к alias-совместимости типов `rss_feed`/`external_news`.
2. Убрать дубли типов после merge и обновить нейминг RSS в UI/локализациях.
3. Поднять версию и добавить запись в `change_log_seed.json`.
4. Обновить `agents.txt` в затронутых каталогах.
5. Прогнать синтаксические и sanity-проверки.

# Изменения (по файлам)
- `guardschool/app.py`:
  - добавлены alias-ключи `rss_feed` и `external_news` в singleton/palette;
  - в `normalize_widget` добавлена канонизация `rss_feed|external_news -> rss_news`;
  - заголовок дефолтного RSS-виджета переименован в «RSS-лента».
- `static/app.js`, `static/admin/widgets.js`:
  - удалены дубли `rss_news` в списках поддерживаемых типов;
  - дефолтный title RSS-виджета переименован в «RSS-лента».
- `static/screen.js`, `static/screen_widgets.js`:
  - подписи RSS для пользовательского интерфейса экрана переименованы в «RSS-лента» / `RSS feed`.
- `static/locales/ru.json`, `static/locales/en.json`:
  - обновлён перевод `widget.type.rss_news`;
  - добавлены alias-ключи `widget.type.rss_feed` и `widget.type.external_news`.
- `guardschool/gs_paths.py`:
  - версия приложения поднята `1.02.034 -> 1.02.035`.
- `change_log_seed.json`:
  - добавлена запись `1.02.035` с пунктами: аварийный таймер, school news, RSS виджет, feedback для mobile.
- `guardschool/agents.txt`, `static/agents.txt`:
  - дополнены правила о совместимости alias RSS и нейтральном naming.
- `docs/codex/2026-04-22T02-24-33_Действие_Feedback_RSS_alias_changelog.md`:
  - создан текущий аудит.

# Решения/обоснования
- Сохранён основной тип `rss_news` для обратной совместимости, а `rss_feed`/`external_news` поддерживаются как alias на backend.
- Нейминг в UI и локализациях сделан нейтральным («RSS-лента» / `RSS feed`), чтобы не ограничивать контент только «мировыми новостями».
- Feedback-функция уже присутствует в кодовой базе; в этом действии зафиксирована совместимость и релизная запись.

# Риски
- В старых UI-конфигах, где руками сохранён `external_news` без прохода через backend-нормализацию, может потребоваться одно сохранение экрана для канонизации типа.
- На стороне админки палитра по-прежнему показывает основной тип `rss_news`; alias-имена используются как совместимость и переводные ключи.

# Следующие шаги
1. После деплоя открыть «Изменения» и проверить наличие записи 1.02.035.
2. Создать тестовый экран с `rss_news` и проверить отображение в карусели + мобильной ленте.
3. (Опционально) добавить unit-тест на `normalize_widget` для `rss_feed` и `external_news`.

# DoD (проверка)
- [x] Alias RSS-типов поддержан на backend без поломки `rss_news`.
- [x] RU/EN подписи RSS сделаны нейтральными.
- [x] Версия и changelog обновлены.
- [x] Обновлены agents и добавлен аудит.

# Мини-ревью (альтернативы)
1. Полностью переименовать `rss_news` в `external_news` везде — отвергнуто, высок риск сломать конфиги и API-клиенты.
2. Оставить старый нейминг «мировые новости» — отвергнуто, ограничивает дальнейшее расширение источников.
3. Выбран компромисс: alias-совместимость + нейтральные подписи.

# Откат
- Git-откат: `git checkout -- guardschool/app.py guardschool/gs_paths.py static/app.js static/admin/widgets.js static/screen.js static/screen_widgets.js static/locales/ru.json static/locales/en.json change_log_seed.json guardschool/agents.txt static/agents.txt docs/codex/2026-04-22T02-24-33_Действие_Feedback_RSS_alias_changelog.md`
