# Закрытые модули (private git)

Open-core **community** репозиторий рассчитан на работу без SaaS/Commercial кода. Полная сборка (hybrid/SaaS) подключает закрытые модули одним из способов ниже.

## Манифест и сборка open-core

Список полных реализаций (`_*_pg.py`) и роутеров: [`tools/private_modules_manifest.json`](../tools/private_modules_manifest.json).

В open-core в tree остаются **фасады** (`gs_push.py`, `saas_db.py`, …) и **stubs** (`_gs_push_stub.py`, …).

Собрать каталог без закрытых файлов:

```bash
python tools/build_open_core_tree.py --out ../GuardSchool-open-core --force
```

Архив для релиза (версия из `APP_VERSION`):

```bash
python tools/package_open_core_release.py --out dist --force
# → dist/guardschool-open-core-<version>.tar.gz и .zip
```

GitHub Actions: workflow **open-core-release** (тег `v*` или `workflow_dispatch`) — artifact `guardschool-open-core`.

Проверка, что в текущем дереве нет «лишних» private-файлов для tarball (в dev-репо с `_pg` — ожидаемо fail):

```bash
python tools/check_open_core_bundle.py
```

Если скрипт завершился с кодом 1 — в дереве остались файлы из manifest; их нужно убрать из публичной сборки или не помечать релиз как open-core.

## Три режима поставки

| Режим | Когда | Capabilities | HTTP |
|--------|--------|--------------|------|
| **Community local** | `DEPLOYMENT_MODE=local`, без слоя | SaaS/commercial → `missing` | stubs → 503 |
| **Embedded** | hybrid/saas, файлы в `guardschool/` или `guardschool_private/` | `register_embedded_capabilities` | `configure_*_http` |
| **Layer** | `GUARDSCHOOL_LAYER_PATH` + `layers/saas`, `layers/commercial` | `register_capabilities` в слое | `register_routes` в слое |

HTTP-контракты (URL, JSON) не меняются при выносе — меняется только место кода.

## Вариант A — модули в community tree (сейчас)

Файлы из manifest лежат в `guardschool/`. Подходит для разработки и hybrid без отдельного репозитория.

## Вариант B — пакет `guardschool_private` на PYTHONPATH

1. Создайте закрытый репозиторий, например:

```
GuardSchool-Private/
  guardschool_private/
    __init__.py
    gs_push.py          # копия из manifest
    saas_db.py
    ...
  pyproject.toml        # опционально: pip install -e .
```

2. На сервере:

```bash
export GUARDSCHOOL_PRIVATE_PYTHONPATH=/opt/guardschool-private
export GUARDSCHOOL_DEPLOYMENT_MODE=hybrid
# community core без gs_push.py в tree — optional_imports подхватит guardschool_private.gs_push
```

3. Слой по-прежнему можно задать через `GUARDSCHOOL_LAYER_PATH` (см. [`layers/README.md`](../layers/README.md)).

`private_modules.module_present()` и `import_optional_module()` ищут модуль сначала в `guardschool/`, затем в `guardschool_private`.

**Фасады в open-core:** `saas_db`, `gs_push`, `gs_feedback`, `gs_cloud_sync`, `gs_sync_http`, `push_notify`, `provider_licenses`, `provider_demo`, `gs_portal_cms`, `gs_saas_bootstrap` + соответствующие `_stub.py`.

**Роутеры SaaS/commercial** монтируются из `_routes_*_pg.py` через `saas_routes` / `commercial_routes`. Портал demo: `register_saas_portal_routes(app)` → `_app_saas_portal_pg.py`. Lifespan SaaS: `app_lifecycle` → `app_saas_lifecycle` → `_app_saas_lifecycle_pg.py`.

**Open-core CI:** `python tools/verify_open_core.py` (сборка дерева + community-тесты).

**Сборка приложения:** `guardschool/gs_app_factory.py` → `create_app()`; entry `guardschool/app.py`. HTTP open-core — `routes_*.py` (см. [architecture.md](architecture.md)).

**`saas_db`:** без `_saas_db_pg` → `saas_db_enabled()` = `False`. Push/feedback — `optional_imports` + фасады.

## Вариант C — только слой + полный checkout

```bash
export GUARDSCHOOL_LAYER_PATH=/opt/guardschool-layers
# layers/saas/__init__.py → mount_all_saas_routes
# layers/commercial/__init__.py → mount_commercial_routes
```

Модули могут оставаться в том же checkout, что и core (как skeleton в community repo).

## Пример layout на сервере

```
/opt/guardschool-core/          # public git, без manifest-файлов
/opt/guardschool-private/       # private git → guardschool_private/
  guardschool_private/
    gs_push.py
    saas_db.py
    ...
/opt/guardschool-layers/
  layers/
    saas/__init__.py
    commercial/__init__.py

export GUARDSCHOOL_PRIVATE_PYTHONPATH=/opt/guardschool-private
export GUARDSCHOOL_LAYER_PATH=/opt/guardschool-layers
export GUARDSCHOOL_DEPLOYMENT_MODE=saas
export GUARDSCHOOL_SAAS_DATABASE_URL=postgresql://...
```

## Связанные документы

- [capabilities.md](capabilities.md) — id и статусы
- [known_limitations.md](known_limitations.md) — plan_id, слои
- [layers/README.md](../layers/README.md) — `register_routes` / stubs
