# Известные ограничения (open-core)

## Слои SaaS / Commercial

- Закрытые файлы перечислены в `tools/private_modules_manifest.json`; overlay: `GUARDSCHOOL_PRIVATE_PYTHONPATH` + пакет `guardschool_private` ([private_modules.md](private_modules.md)).
- **SaaS skeleton:** `layers/saas/__init__.py` + `guardschool/saas_routes.py` (layer / embedded / stubs).
- **Community local** (`GUARDSCHOOL_DEPLOYMENT_MODE=local`, без `GUARDSCHOOL_LAYER_PATH`): SaaS caps `missing`, SaaS URL → 503.
- **Hybrid** без слоя: embedded routes + `register_embedded_capabilities`.
- Push / tv-pairing вынесены в SaaS layer (`routes_push` через `mount_saas_push`).
- Commercial — `layers/commercial/` (пример).

## Виджеты

- Рендер на ТВ — один JS runtime (`screen_widgets.js`); Python-модули задают manifest и defaults.
- Custom widgets без sandbox; ошибка рендера одного виджета не роняет экран (error boundary).
- Удаление `widgets/time.py` скрывает тип из палитры, но существующие экраны показывают заглушку.

## Лицензии

- `plan_id` тенанта (`public.tenants`) и env `GUARDSCHOOL_TENANT_PLAN_ID` ограничивают SaaS caps (`locked`) через `license_capability_provider.py` при каждом `get_capabilities()`.
- Планы в БД по умолчанию: `free`, `paid` (локаль + SaaS), `saas_only` (облачная школа); оба платных дают полный SaaS-набор caps. Дополнительные id: `starter`, `pro`, `enterprise`. Алиас `full`→`paid`.
- SaaS-функция и лицензия разделены: модуль может быть установлен, но `locked` по тарифу.

## TV API

- Push/feedback используют `gs_tv_screen_api` (slug, Bearer/device-token, tenant slug).
- `find_active_screen()` для feedback вызывает `load_config()` лениво из `gs_app_config` (без циклического импорта `app`).
- Статусы сигналов (`bell_status`) на ТВ локализуются по `config.ui_locale` (`ru` / `en`) через `gs_bell_strings.py`; смена языка в админке влияет на payload после сохранения config.

## PyInstaller

- Каталог `widgets/` должен быть включён в spec; `GUARDSCHOOL_LAYER_PATH` — вне exe на сервере.
