# Разбиение крупных модулей

Цель: файлы **&lt; ~400–500 строк**, границы по **домену**, не по «каждые N строк». Публичные URL и поведение **не меняются**.

## Приоритет (строки на момент плана)

| Файл | Строк | Статус |
|------|------:|--------|
| `static/screen_widgets.js` | ~650 | **Готово** → фасад |
| `static/tv-core-utils.js` | ~245 | **Готово** |
| `static/tv-schedule-table.js` | ~238 | **Готово** |
| `static/tv-screen-shell.js` | ~836 | **Готово** |
| `guardschool/local_audio_worker.py` | ~52 | **Готово** → фасад |
| `guardschool/local_audio_ffmpeg.py` | ~241 | **Готово** |
| `guardschool/local_audio_playback.py` | ~303 | **Готово** |
| `guardschool/local_audio_orchestration.py` | ~1025 | **Готово** (preview можно вынести позже) |
| `guardschool/gs_app_config.py` | ~299 | **Готово** → фасад |
| `guardschool/gs_app_config_defaults.py` | ~559 | **Готово** |
| `guardschool/gs_app_config_audio.py` | ~122 | **Готово** |
| `guardschool/gs_schedule_bells.py` | ~213 | **Готово** → фасад |
| `guardschool/gs_bell_schedules_io.py` | ~126 | **Готово** |
| `guardschool/gs_bell_entries.py` | ~181 | **Готово** |
| `guardschool/gs_bell_status.py` | ~98 | **Готово** |
| `guardschool/gs_schedule_class.py` | ~144 | **Готово** |
| `guardschool/gs_schedule_rows.py` | ~251 | **Готово** |
| `guardschool/gs_schedule_bells_time.py` | ~48 | **Готово** |

## `routes_admin.py` → подроутеры

| Модуль | Зона `/api/admin/*` | Статус |
|--------|---------------------|--------|
| `routes_admin.py` | Фасад `register_admin_routes`, config, schedule snapshot, overrides, bells, preview, screen-watch | **Ядро (~409)** |
| `routes_admin_audio.py` | PC audio, audio-stream, break-music | **Готово** |
| `routes_admin_checkin.py` | checkin/* | **Готово** |
| `routes_admin_uploads.py` | upload-* (фоны, excel, bells, …) | **Готово** |
| `routes_admin_import_export.py` | export/import, weekly template, excel sample | **Готово** |
| `routes_admin_school_news.py` | school-news CRUD + gallery | **Готово** |

Паттерн: отдельный `APIRouter(tags=["admin"])`, монтирование из `register_admin_routes()`.

## `local_audio_worker.py` (готово)

| Модуль | Содержимое | Строк |
|--------|------------|------:|
| `local_audio_ffmpeg.py` | resolve ffplay/ffmpeg/ffprobe, WASAPI, duration | ~241 |
| `local_audio_playback.py` | play_file_async, stop, get_status | ~303 |
| `local_audio_orchestration.py` | break orchestration, tick_once, preview | ~1025 |
| `local_audio_worker.py` | Фасад + `play_test_file` / re-export | ~52 |

Публичный импорт `from . import local_audio_worker` **не менялся**.

## `screen_widgets.js` (готово)

| Модуль | Содержимое | Строк |
|--------|------------|------:|
| `tv-core-utils.js` | tvUiStrings, escapeHtml, дата/время, school-news sanitize | ~245 |
| `tv-schedule-table.js` | buildScheduleTable, bell status HTML, SCHEDULE_THEME | ~238 |
| `tv-screen-shell.js` | фон, часы, check-in bind, emergency countdown | ~836 |
| `screen_widgets.js` | renderWidgetHtml, helpers, GuardSchoolScreen | ~650 |

Порядок загрузки: `tv-core-utils` → `tv-schedule-table` → `tv-screen-shell` → `screen_widgets` (см. `screen.html`, `app.js`).

## `gs_schedule_bells.py` (готово)

| Модуль | Содержимое | Строк |
|--------|------------|------:|
| `gs_bell_schedules_io.py` | load/migrate/default bell_schedules, schedule_date_iso | ~126 |
| `gs_schedule_class.py` | селекторы классов, pickable для экрана/ТВ | ~144 |
| `gs_bell_entries.py` | entry helpers, звуки звонков | ~181 |
| `gs_bell_status.py` | build_bell_status | ~98 |
| `gs_schedule_bells_time.py` | timezone, calendar_today, wall_clock | ~48 |
| `gs_schedule_rows.py` | collect_enriched_schedule_rows | ~251 |
| `gs_schedule_bells.py` | build_schedule_payload, build_bell_audio_payload, re-export | ~213 |

Импорт `from .gs_schedule_bells import …` **не менялся** (`build_bell_status` патчит фасад через lazy import).

## `gs_app_config.py` (готово)

| Модуль | Содержимое | Строк |
|--------|------------|------:|
| `gs_app_config_defaults.py` | default_screen, default_config, emergency, migrate | ~559 |
| `gs_app_config_audio.py` | sanitize_audio_stream, audio defaults | ~122 |
| `gs_app_config.py` | load_config, sanitize_config, re-export | ~299 |

После каждого шага: `python -m unittest discover -s tests -q`.
