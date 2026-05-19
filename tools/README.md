# Инструменты GuardSchool

## Актуальные (использовать в CI и релизах)

| Скрипт | Назначение |
|--------|------------|
| `verify_open_core.py` | Сборка open-core tree + community-тесты |
| `build_open_core_tree.py` | Каталог без `_*_pg` для публичного tarball |
| `package_open_core_release.py` | Дерево + `.tar.gz` / `.zip` в `dist/` |
| `check_open_core_bundle.py` | Проверка, что в дереве нет private-файлов из manifest |
| `check_locales.py` | Паритет ключей `static/locales/ru.json` / `en.json` |
| `neutralize_terminology.py` | Нейтральные термины в locale (опционально) |
| `private_modules_manifest.json` | Список закрытых модулей для open-core |

## Разработка / генерация

| Скрипт | Назначение |
|--------|------------|
| `gen_widgets.py` | Генерация заготовок виджетов |
| `generate_text_xlsx_templates.py` | Шаблоны Excel для импорта |
| `push_prune_stale.py` | Обслуживание push-подписок |

## Архив

Одноразовые скрипты миграции `app.py` (2026) — каталог [`archive/`](archive/). **Не запускать** на текущем дереве.

Актуальная структура backend — [docs/architecture.md](../docs/architecture.md).
