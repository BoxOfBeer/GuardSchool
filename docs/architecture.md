# Архитектура backend (после open-core split)

## Точка входа

| Файл | Назначение |
|------|------------|
| [`app.py`](../app.py) (корень репо) | Shim для `uvicorn app:app` |
| [`guardschool/app.py`](../guardschool/app.py) | `app = create_app()` |
| [`guardschool/gs_app_factory.py`](../guardschool/gs_app_factory.py) | Сборка FastAPI: слои, роутеры, middleware, `/static` |

## HTTP (open-core)

| Модуль | Префикс / зона |
|--------|----------------|
| `routes_pages.py` | `/`, `/screen/*`, `/uploads/*`, `sw.js` |
| `routes_auth.py` | `/api/setup`, `/api/login`, `/api/bootstrap`, capabilities, widget registry |
| `routes_public.py` | `/api/version`, school-news (public) |
| `routes_screen.py` | `/api/screen/*`, check-in с ТВ |
| `routes_admin.py` | `/api/admin/*` |
| `app_pwa_manifest.py` | PWA manifest (фасад → `_pg` / stub) |
| `app_portal_web.py` | Портал guarddoc.ru (фасад → `_pg` / stub) |
| `app_hosting.py` | SaaS tenant middleware (cookie → `tenant_ctx`) |

SaaS/commercial URL монтируются через `saas_routes.py` / `commercial_routes.py` и `layer_loader.py` (см. [private_modules.md](private_modules.md)).

## Доменная логика (`gs_*`)

| Модуль | Ответственность |
|--------|------------------|
| `gs_app_config.py` | `config.json`: load/sanitize, emergency templates |
| `gs_paths.py` | Пути данных, `APP_VERSION`, `STATIC_DIR` |
| `gs_data_loaders.py` | Расписание, праздники, marquee, RSS, overrides |
| `gs_schedule_bells.py` | Payload расписания/звонков для ТВ, bell audio, константы оркестрации |
| `gs_school_news.py` | Школьные новости, загрузка изображений |
| `gs_checkin_screen.py` | Экран по slug, виджеты, check-in board |
| `gs_checkin.py` | Журнал отметок, БД |
| `gs_screen_push.py` | Web Push (content / check-in / emergency) |
| `gs_admin_upload.py` | Лимиты загрузок и квоты SaaS |
| `gs_net_utils.py` | `normalize_stream_host` и сетевые хелперы |
| `gs_tv_screen_api.py` | Slug, TV Bearer, tenant для screen API |
| `gs_tv_pair.py` | PIN, rate limit, pairing |
| `widget_registry.py` | Типы виджетов, палитра, dedupe |
| `capabilities.py` | Capability registry |

## Звук на ПК

`local_audio_worker.py` и `bell_rupor_worker.py` импортируют доменные модули напрямую (не через `guardschool.app`).

## Private overlay

Фасады (`saas_db.py`, `gs_push.py`, …) и `_*_pg.py` — см. [`tools/private_modules_manifest.json`](../tools/private_modules_manifest.json) и [private_modules.md](private_modules.md).

## Проверки

```bash
python -m unittest discover -s tests -q
python tools/verify_open_core.py
python tools/build_open_core_tree.py --out /tmp/gs-oc --force
python tools/package_open_core_release.py --out dist --force
```
