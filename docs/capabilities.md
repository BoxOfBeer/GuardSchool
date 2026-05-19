# Capabilities (доступность функций)

GuardSchool использует единый реестр **capabilities** — UI и API спрашивают `has_capability("…")`, а не наличие конкретного файла.

## Статусы

| Статус | Значение |
|--------|----------|
| `available` | Функция доступна |
| `missing` | Модуль физически отсутствует в сборке |
| `disabled` | Отключено настройкой / env |
| `locked` | Установлено, но закрыто лицензией или тарифом |
| `unavailable` | Требует SaaS, интернет или подключение |
| `error` | Модуль найден, но не загрузился |

## Идентификаторы

### SaaS / Online

- `mobile_external` — внешний мобильный доступ
- `push_notifications` — push-уведомления
- `cloud_sync` — облачная синхронизация
- `tenant_feedback` — обратная связь с мобильной страницы
- `remote_tv_pairing` — удалённое сопряжение ТВ
- `cloud_status` — статус облака

### Commercial / Platform

- `license_check`, `registration`, `payment`, `tenant_provisioning`, `tariff_limits`, `production_portal`

### Core / Local

- `local_widgets` — локальные виджеты поставки
- `custom_widgets` — сторонние виджеты (только local self-hosted)

## API

- `GET /api/capabilities` — полный список с сообщениями для UI
- В `GET /api/admin/config` поле `_meta.capabilities` дублирует данные для админки

## Переменные окружения

- `GUARDSCHOOL_DEPLOYMENT_MODE` — `local` | `hybrid` | `saas`
- `GUARDSCHOOL_LAYER_PATH` — каталог с закрытыми слоями (`layers/saas`, `layers/commercial`)
- `GUARDSCHOOL_DISABLED_CAPABILITIES` — список id через запятую для принудительного `disabled`
- `GUARDSCHOOL_TENANT_PLAN_ID` — тариф без SaaS БД (`free`, `starter`, `pro`, `enterprise`, …)

## Слои

Закрытые слои **не входят** в community-репозиторий. На сервере их кладут в `GUARDSCHOOL_LAYER_PATH` и регистрируют через `register_capabilities()` / `register_routes(app)` в `__init__.py` слоя.

В hybrid/saas сборке с встроенными модулями capabilities могут быть `available` через `capability_bootstrap` до полного выноса кода в слой.

Ограничение по тарифу: `license_capability_provider.py` при `get_capabilities()`:

- источник plan: `tenants.plan_id` для текущего `tenant_slug` (SaaS БД), иначе env `GUARDSCHOOL_TENANT_PLAN_ID`;
- id: `free`, `paid`, `saas_only`, `starter`, `pro`, `enterprise` (`paid`→`starter`, `saas_only`→`enterprise`);
- часть SaaS/commercial caps → `locked`, если не входят в тариф.
