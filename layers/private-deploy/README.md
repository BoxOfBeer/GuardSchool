# Пример private-deploy (закрытый репозиторий)

Шаблон структуры для **варианта B** из [docs/private_modules.md](../../docs/private_modules.md).

1. Скопируйте файлы из `tools/private_modules_manifest.json` в `guardschool_private/` (имена модулей без префикса `guardschool/`).
   - PostgreSQL: `guardschool/_saas_db_pg.py` → `guardschool_private/saas_db.py`
   - Push/feedback/sync: `_gs_push_pg.py`, `_gs_feedback_pg.py`, `_gs_cloud_sync_pg.py`, `_gs_sync_http_pg.py` → одноимённые в `guardschool_private/`
   - Commercial: `_provider_licenses_pg.py`, `_provider_demo_pg.py`, `_gs_portal_cms_pg.py`, `_routes_commercial_pg.py`, `_gs_saas_bootstrap_pg.py`
   - Routes SaaS: `_routes_push_pg.py`, `_routes_feedback_pg.py`, `_routes_cloud_sync_pg.py`, `_routes_cloud_status_pg.py`
   - `_push_notify_pg.py`
2. Установка (опционально): `pip install -e .` из этого каталога (`pyproject.toml`).
2. Укажите корень каталога с пакетом:

```bash
export GUARDSCHOOL_PRIVATE_PYTHONPATH=/path/to/GuardSchool-Private
export GUARDSCHOOL_LAYER_PATH=/path/to/guardschool-layers
```

3. Скопируйте `layers/saas` и `layers/commercial` из community repo в `guardschool-layers/layers/`.

Пустой пакет в этом каталоге — только заглушка; реальный код в вашем private git.
