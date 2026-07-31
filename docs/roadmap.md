# Roadmap (open-core)

## Сделано

- Capabilities registry + `GET /api/capabilities`
- Widget registry + загрузчик `widgets/*.py`
- `api_version`, informational `permissions`
- JS error boundary для виджетов
- Capability gates на ключевых SaaS/commercial endpoints
- Bootstrap embedded capabilities для hybrid/saas
- Нейтральная терминология UI (слот / сигнал / группа)
- Паритет ru/en: `tools/check_locales.py` (587+ ключей)
- Подсказки настроек виджета по JSON Schema
- i18n capabilities в админке + `gs_bell_strings.py` для ТВ
- **SaaS layer:** `layers/saas/`, `saas_routes.py`, stubs (feedback, cloud_sync, cloud_status, push)
- **Commercial layer:** `layers/commercial/`, `commercial_routes.py`, stubs
- **Тариф plan_id:** `tenants.plan_id` + env → `locked` caps (`license_capability_provider`, `lookup_tenant_plan_id`)
- **Фасады private-модулей:** `_private_facade.py`, `gs_push`, `gs_feedback`, `gs_cloud_sync`, `gs_sync_http`, `saas_db`, `provider_licenses`, `gs_saas_bootstrap` (`_*_pg` + stub)
- **`tools/build_open_core_tree.py`** — сборка дерева без `_*_pg`
- **Роутеры и notify:** `_routes_*_pg`, `_push_notify_pg`, `_provider_demo_pg`, `_gs_portal_cms_pg`; mount через `saas_routes` / `commercial_routes`
- **`app_lifecycle`**, **`app_try_demo`**, **`app_host_routing`**, **`_app_saas_portal_pg`** (`/demo`, `/try-demo`); CI `tools/verify_open_core.py` + `.github/workflows/open-core.yml`
- **PWA manifest:** `app_pwa_manifest` → `_app_pwa_manifest_pg` / stub (`/pwa/screen`, `/pwa/t`, HTML `<link rel=manifest>`)
- **Портал guarddoc.ru:** `app_portal_web` → `_app_portal_web_pg` / stub (`/register`, `/ADM`, `/about/*`, `/api/portal/cms`)
- **TV pairing:** `gs_tv_pair.py`, `_routes_tv_pg` (`/t/…`, `/api/tv/pair`, `/api/admin/tv-access/*`); mount в `saas_routes`
- **Admin + screen API:** `routes_admin.py`, `routes_screen.py` — явные импорты, без `__getattr__`
- **`gs_app_config.py`:** `load_config`, `sanitize_config`, defaults, emergency templates
- **`routes_auth.py`**, **`routes_public.py`**, **`routes_pages.py`:** bootstrap, login, HTML, uploads
- **`gs_data_loaders.py`**, **`gs_schedule_bells.py`**, **`gs_screen_push.py`:** расписание, payload ТВ, push
- **`gs_school_news.py`**, **`gs_checkin_screen.py`**, **`gs_admin_upload.py`**, **`gs_net_utils.py`**, **`app_hosting.py`**
- **`gs_app_factory.py`:** `create_app()` — сборка FastAPI; **`app.py`** — тонкий entry (`app = create_app()`)
- **`local_audio_worker.py`:** прямые импорты из domain-модулей (без `guardschool.app`)

## Дальше

1. ~~Генерация форм из `settings_schema`~~ — `widget-settings-form.js` (простые типы + доп. поля; карусель/image — вручную)
2. ~~State карусели в отдельном модуле~~ — `static/widgets/carousel-runtime.js`
3. ~~Инфраструктура выноса в private git~~ — manifest, `private_modules.py`, фасад `saas_db`, [private_modules.md](private_modules.md)
4. ~~`plan_id` → capabilities~~ — `license_capability_provider` + `tenants.plan_id` (приоритет над env)
5. ~~Разрез монолитного `app.py`~~ — `gs_app_factory`, `routes_*`, `gs_*` ([architecture.md](architecture.md))
6. ~~Релиз community tarball~~ — `package_open_core_release.py`, CI `.github/workflows/open-core-release.yml`
7. ~~Архив одноразовых `tools/extract_*` / `patch_*`~~ — `tools/archive/`

## Фаза: эксплуатация и качество

1. ~~CI-проверка паритета виджетов Python ↔ JS~~ — `tools/check_widget_parity.py` + `.github/workflows/open-core.yml`
2. ~~Интеграционные тесты ZIP и screen payload~~ — `tests/test_integration_core.py`
3. ~~IT runbook~~ — [deploy.md](deploy.md): порты, бэкап `data/`, один worker для PC audio, reverse proxy
4. ~~Docker Compose~~ — [`Dockerfile`](../Dockerfile), [`docker-compose.yml`](../docker-compose.yml)
5. ~~Расширить CI JS~~ — `node --check` на все `static/widgets/*.js`
6. ~~Тесты импорта Excel~~ — `tests/test_excel_import.py` (образцы `gs_import_sample_xlsx`)
7. ~~Health endpoint~~ — `GET /api/health` (`gs_health.py`, `routes_public.py`)
8. ~~Pin зависимостей~~ — диапазоны в `requirements.txt`

## Фаза: нейтральная терминология (surface)

Школьная модель остаётся **core**; обезличивание — **UI и импорт**, без rename schema.

1. ~~Словарь surface vs core~~ — [neutral_model.md](neutral_model.md)
2. ~~Алиасы Excel~~ — `Группа`/`Group`, `Слот1`/`Slot1`, `Date` (`gs_excel_import.py`)
3. ~~Локали cap / тарифы~~ — `cap.effectivePlan*`, `neutralize_terminology.py`
4. ~~Тесты алиасов Excel~~ — `tests/test_excel_import.py` (Group / Slot / Date)
5. ~~Остатки UI~~ — `check_locales.py --check-tv --warn-terms`; SaaS/PC-audio сообщения; README RU

## Фаза: onboarding и упаковка

1. ~~Тесты `sanitize_config` / `migrate_screen_layout`~~ — `tests/test_gs_app_config.py`
2. ~~Demo-seed при `/api/setup`~~ — `gs_community_seed.py` (local, пустой `config.json`)
3. ~~PyInstaller spec~~ — `change_log_seed.json` в datas; `tests/test_community_seed.py`
4. ~~CI Docker build~~ — `.github/workflows/open-core.yml`
