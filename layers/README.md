# Закрытые слои (manual deploy)

Подробнее о выносе модулей в private git: [docs/private_modules.md](../docs/private_modules.md).

На сервере:

```bash
export GUARDSCHOOL_LAYER_PATH=/opt/guardschool-layers
# опционально: модули в пакете guardschool_private/ (см. layers/private-deploy/)
export GUARDSCHOOL_PRIVATE_PYTHONPATH=/opt/guardschool-private
```

Структура:

```
/opt/guardschool-layers/
  layers/
    saas/
      __init__.py      # register_capabilities, register_routes
    commercial/
      __init__.py
```

## SaaS skeleton в community-репозитории

В этом репозитории уже есть рабочий **`layers/saas/__init__.py`**. Для разработки:

```bash
export GUARDSCHOOL_LAYER_PATH=/path/to/GuardSchool
export GUARDSCHOOL_DEPLOYMENT_MODE=local   # capabilities всё равно поднимет слой
```

Слой вызывает `mount_all_saas_routes(app)` из `guardschool.saas_routes`:

- `routes_feedback` — обратная связь с ТВ (`tenant_feedback`)
- `routes_cloud_sync` — `/api/sync/status`, `/api/sync/bundle` (`cloud_sync`)
- `routes_cloud_status` — `/api/admin/sync-status` (`cloud_status`)
- `routes_push` — Web Push + `/api/screen/{slug}/tv-pair-link` (`push_notifications`, `remote_tv_pairing`)

## Community local (без слоя)

`GUARDSCHOOL_DEPLOYMENT_MODE=local` и **без** `GUARDSCHOOL_LAYER_PATH`:

- SaaS capabilities → `missing`
- Те же URL обслуживает **`routes_saas_stubs`** → HTTP **503** (`require_capability`)
- Расписание, экраны, виджеты — работают

## Hybrid без внешнего слоя

`GUARDSCHOOL_DEPLOYMENT_MODE=hybrid` (по умолчанию), модули `gs_feedback`, `gs_cloud_sync` в tree:

- `register_embedded_capabilities` помечает SaaS caps `available`
- `configure_saas_http` монтирует реальные роутеры из core (до полного выноса)

## Commercial skeleton

В репозитории: **`layers/commercial/__init__.py`** — `register_capabilities`, `register_routes` → `routes_commercial`.

Community **local** без слоя: commercial caps `missing`, `/api/provider/*` и `/api/saas/register` → **503** (stubs).

**Hybrid** без внешнего слоя: embedded `routes_commercial` + caps из `register_embedded_capabilities` (модуль `saas_db`).

Core при старте:

```text
apply_layer_routes(app)
configure_saas_http(app)
configure_commercial_http(app)
```
