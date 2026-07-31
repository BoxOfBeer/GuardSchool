# Виджеты (plugin registry)

## Реестр

- Python: `guardschool/widget_registry.py`
- Загрузка: `guardschool/widget_loader.py`
- Встроенные типы: `guardschool/widgets_builtin.py`
- Official plugins: каталог [`widgets/`](../widgets/) (по одному `.py` на тип)
- API: `GET /api/widgets/registry`, `_meta.widget_registry` в admin config

## Manifest

Каждый модуль вызывает `register_widget({...})`:

| Поле | Описание |
|------|----------|
| `type` | Ключ типа в `screen.widgets` |
| `title` | Название в админке |
| `category` | `basic`, `schedule`, `media`, `safety`, `checkin`, `news` |
| `api_version` | Контракт manifest/JS (сейчас **1**) |
| `version` | Semver модуля |
| `official` | `true` — поставка проекта |
| `singleton_id` | Фиксированный `id` экземпляра |
| `aliases` | Например `rss_feed` → `rss_news` |
| `requires_capabilities` | Нужные capabilities |
| `permissions` | Informational: `filesystem`, `network`, `subprocess` |
| `render_key` | Ключ ветки в `screen_widgets.js` / `static/widgets/{type}.js` |
| `settings_schema` | JSON Schema для полей `settings` (см. `guardschool/widget_settings_schemas.py`) |

Если `api_version` больше, чем `CURRENT_WIDGET_API_VERSION` в core — виджет не загружается (`error`).

## Рендер на ТВ

HTML строит `static/screen_widgets.js` + опциональные плагины в `static/widgets/*.js`.

Реестр: `GuardSchoolWidgets.register(type, fn)` в `static/widgets/runtime.js`.  
Все типы с HTML-рендером вынесены в `static/widgets/*.js` (после `screen_widgets.js`). **carousel** — `static/widgets/carousel-runtime.js` (state/таймеры) + вызов из `screen.js` / `startCarousel`.

Точка входа — `renderWidgetHtml` (error boundary):

- тип не в `widget_types_available` → заглушка **missing**
- исключение при рендере → заглушка **error** (остальной экран работает)

Список типов приходит в `GET /api/screen/{slug}` → `widget_types_available`.

## Админка: настройки по schema

- `static/admin/widget-settings-form.js` — поля из `settings_schema` (boolean, number, string, enum).
- Простые типы (`date`, `time`, `blank`) — только schema + enabled/backdrop/menu.
- Сложные (`carousel`, `image`, `checkin_*`) — ручные блоки в `widgets.js`; schema дополняет оставшиеся ключи.
- Валидация min/max/enum при `change` / `blur`.

## Удалённый модуль

Если виджет есть в конфиге, но модуль удалён из `widgets/`:

- экран **не падает**;
- на ТВ: «Виджет {type} отсутствует.»;
- в админке: предупреждение с текстом из `explain_widget_status`.

## Версии API

| api_version | Примечание |
|-------------|------------|
| 1 | Текущая: manifest + `render_key`, defaults в registry |

При повышении версии в core обновите `CURRENT_WIDGET_API_VERSION` и документируйте breaking changes.
