# GuardSchool

**Self-hosted schedules, bells, and signage in the browser.** The product is **designed around a school lesson timetable** (classes, bells, days), but the underlying pattern is generic: **time + structured data** on one or more screens. The same setup can show **duty rosters**, **shift plans**, room booking-style boards, or any other table you feed through the same import and widget flow—not only “lessons.”

Runs **fully offline** after setup: data, settings, and media stay on your machine — **no mandatory cloud or external APIs**. Administration is **inside your network (LAN)**; you choose whether and how to expose HTTP access.

**Clients are just web pages:** a **mini PC + monitor**, a **smart TV** with a built-in browser, a **tablet** on a reception counter — if it can open a URL in fullscreen, it can be a display. No vendor app store required.

Admin UI: **English and Russian** (language switch in the header). Settings include **timezone** (for “today” in schedules and date/time on displays) and **clock offset in minutes** if TV clocks drift.

---

## Contents

- [Features](#features)
- [Quick start](#quick-start)
- [Repository layout](#repository-layout)
- [Localization & time](#localization--time)
- [Import / export](#import--export)
- [Changelog & versioning](#changelog--versioning)
- [Windows executable](#windows-executable)
- [Excel (short)](#excel-short)
- [License](#license)
- [Product notes](#product-notes)
- [Русский](#русский)

---

## Features

- Multi-screen admin (one tab per display), widget grid, schedules, bells, backgrounds
- One URL per display: `/screen/{slug}` — open the same server from every screen on the LAN
- Local admin authentication
- **ZIP export/import** for backup and migration without cloud
- Optional **PC audio** path (ffmpeg / scheduled bells) — see admin “PC audio” tab

## Quick start

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Open:

- Admin: `http://127.0.0.1:8000`
- TV screen: `http://127.0.0.1:8000/screen/tv-1`

## Repository layout

| Path | Role |
|------|------|
| **`guardschool/`** | Python package: FastAPI app (`app.py`), shared modules (`gs_*.py`), PC audio workers (`local_audio_worker.py`, `bell_rupor_worker.py`). |
| **`app.py`** (repo root) | Thin shim: `from guardschool.app import app` — keeps **`uvicorn app:app`** and tools unchanged. |
| **`static/`** | Admin and TV front-end (ES modules under `static/admin/`, `screen_widgets.js`, locales). |
| **`data/`** | Runtime data (created on first run): `config.json`, schedules, bells, uploads — **back this up**. |
| **`change_log_seed.json`** | Default **release notes** merged into `data/change_log.json` when the admin “Changes” log is seeded. |
| **`requirements.txt`**, **`run_server.py`** | Dependencies and optional launcher. |

## Localization & time

- UI language: **Language** dropdown in the header (next to **Settings**).
- Timezone and offset: **Language, time & timezone** inside **Settings**.  
  “Today” for schedules and bells is computed **in the selected timezone**, not silently tied to the server OS clock without configuration.
- Import / Excel / ZIP validation messages from the API follow the selected UI language (the admin page sends `X-UI-Locale: en` or `ru`).

## Import / export

In the admin UI: **Export ZIP** / **Import ZIP** — full snapshot of config, schedules, bells, and uploads. Use for backups and moving between machines **without cloud**.

## Changelog & versioning

- **Current version** is defined as **`APP_VERSION`** in [`guardschool/gs_paths.py`](guardschool/gs_paths.py) (also exposed via **`GET /api/version`**).
- **Release notes** shown in the admin **“Changes”** tab come from **`data/change_log.json`**. On first setup, entries without a `version` field are cleaned up and the file can be seeded from [`change_log_seed.json`](change_log_seed.json) in the repo (ship history for fresh installs).
- To **record a release**: bump **`APP_VERSION`**, append an object `{ "version", "timestamp" (ISO-8601), "message" }` to **`change_log_seed.json`** (and optionally call **`append_release_note`** from [`guardschool/gs_change_log.py`](guardschool/gs_change_log.py) if you extend the log from code).

### Recent releases (summary)

| Version | Highlights |
|---------|------------|
| **1.02.001** | **1.02.x** line: SaaS / multi-tenant (host → slug), PostgreSQL **public + per-school schemas**, licenses & registration, `GUARDSCHOOL_DEPLOYMENT_MODE`, screen orientation & menu widgets, demo tokens; see **`change_log_seed.json`**. |
| **1.01.004** | Backend grouped under **`guardschool/`**; TV schedule **current-lesson** highlight uses **school timezone + clock offset**; TV **background layers** fixed after full grid rebuild; admin **modal focus / a11y**; JS split into `static/admin/*`. |
| **1.01.003** | Release log module, TV background cross-fade, carousel animations. |
| **1.01.002** | PC audio tab, program settings, widget palette, preview/`screen_widgets` integration. |
| **1.01.001** | Security hardening (ZIP import, screen API, cookies, XSS), subprocess audit, helper modules split from monolithic `app.py`. |
| **1.01.000** | Initial public line: screens, widgets, schedules, bells, backgrounds, carousel, admin, ZIP. |

## Windows executable

```powershell
build_exe.bat
```

Output: `dist/GuardSchool.exe`. A `data` folder is created next to the executable.

## Excel (short)

Typical dated schedule columns: `Date`, `Class`, `Lesson1` …  
Example row: `2026-04-01 | 5 | Russian | English | Math`  

Samples and auto-import from `data/import/` follow the same rules as in previous releases.

## License

**MIT** — see [`LICENSE`](LICENSE).

## Product notes

- **IT docs**: port layout, backing up `data/`, version upgrades.
- **Deploy**: Docker / MSI if the customer needs it.
- **Updates**: changelog, `config.json` migrations when the schema changes.
- **Security**: HTTPS behind a reverse proxy, IP allowlists, strong admin password. Session cookie uses **`Secure`** when the request is HTTPS or `X-Forwarded-Proto: https` (typical behind TLS reverse proxy).
- **PostgreSQL (optional)**: `GUARDSCHOOL_DATABASE_URL` is used by **`cloud_store`** (JSON snapshot / `school_snapshot`). For SaaS control-plane tables, prefer **`GUARDSCHOOL_SAAS_DATABASE_URL`**; if it is unset, **`saas_db`** falls back to `GUARDSCHOOL_DATABASE_URL`. One DSN for both is valid; two URLs make roles obvious when debugging.
- **Screen API**: `GET /api/screen/{slug}` returns schedule and display JSON **without auth** (for TV browsers on the LAN). Treat network access accordingly.
- **Admin POSTs**: no separate CSRF tokens; browsers rely on **SameSite** session cookies. For high-threat deployments, add tokens or restrict origins.
- **Process model**: run **one** uvicorn worker if you rely on in-process PC audio state (`local_audio_worker` globals); multiple workers do not share that state.
- **Code layout**: see [Repository layout](#repository-layout) and [Changelog & versioning](#changelog--versioning). Admin UI: `static/app.js` plus `static/admin/*.js` (`preview.js`, `audio-stream.js`, `data-import.js`, `bells.js`, `widgets.js`, `history.js`, …); `index.html` loads `i18n.js` then `app.js` (module); `app.js` imports `screen_widgets.js` first so `window.GuardSchoolScreen` is ready. **`static/admin/escape-html.js`** centralizes safe HTML escaping.
- **Branding**: logo, `ico.png`, custom copy.
- **Telemetry**: the app does not phone home by default; any analytics would require explicit consent and opt-out.

---

## Русский

**README для GitHub:** репозиторий ориентирован на публичное описание проекта; блок ниже — краткая русская версия для школ, интеграторов и других площадок.

### GuardSchool — что это

**Локально развёртываемое расписание и сигналы (звонки) на экранах в браузере.** Ядро модели — **школа: уроки, классы, звонки**; дальше это тот же принцип **«время + данные»** на экранах: **дежурства**, **смены**, приём по кабинетам или любая таблица, которую вы заводите через тот же импорт и виджеты — не обязательно «уроки».

После установки работает **полностью офлайн**: данные и медиа хранятся у вас, **без обязательного облака и внешних API**. Управление — **внутри вашей сети (LAN)**.

**Экран** — любое устройство с браузером: старый монитор с мини-ПК, Smart TV, планшет на стойке в приёмной; достаточно открыть URL экрана в полноэкранном режиме.

Интерфейс админки: **русский и английский** (переключатель в шапке). В настройках — **часовой пояс** и **сдвиг времени в минутах**, если часы на ТВ расходятся с реальностью.

### Зачем школе

- **Полный контроль**: конфигурация, расписание, звонки, фоны и загрузки в папке `data/`, а не на чужом сервере.
- **Оффлайн**: достаточно одного ПК или встроенного компьютера у панели; интернет для работы не обязателен.
- **Прозрачность**: можно отдать ИТ архив (ZIP) для резервной копии или аудита.

### Быстрый старт

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

- Админка: `http://127.0.0.1:8000`
- Экран ТВ: `http://127.0.0.1:8000/screen/tv-1`

### Структура репозитория

Краткая схема — в разделе **[Repository layout](#repository-layout)** (таблица: `guardschool/`, корневой `app.py`, `static/`, `data/`, `change_log_seed.json`).

### Локализация и время

- Язык: список **«Язык»** в шапке.
- Пояс и сдвиг: блок **«Язык, время и пояс»** в меню **Настройки**.  
  «Сегодня» для расписания и звонков считается **в выбранном поясе**.
- Тексты ошибок при импорте Excel/ZIP на стороне API соответствуют выбранному языку интерфейса (заголовок `X-UI-Locale: en` или `ru`).

### Импорт и экспорт

**Экспорт ZIP** / **Импорт ZIP** в админке — полный снимок настроек, расписаний, звонков и загрузок. Импорт полного архива принимается только если в **корне ZIP** есть **`config.json`** (как в экспорте GuardSchool); пустой или чужой архив не очищает `uploads`.

### Безопасность и эксплуатация

- **PostgreSQL (опционально):** **`GUARDSCHOOL_DATABASE_URL`** использует модуль **`cloud_store`** (снимок JSON / `school_snapshot`). Для таблиц SaaS удобнее **`GUARDSCHOOL_SAAS_DATABASE_URL`**; если она пуста, **`saas_db`** подставляет тот же **`GUARDSCHOOL_DATABASE_URL`**. Один DSN на оба сценария допустим; два URL проще различать при отладке.
- **`GET /api/screen/{slug}`** отдаёт JSON экрана **без входа** — рассчитано на ТВ в LAN; ограничивайте доступ к сети при чувствительных данных.
- Сессия админки: флаг **`Secure`** у cookie включается при HTTPS или заголовке **`X-Forwarded-Proto: https`** у прокси.
- **Один процесс** uvicorn, если используете звук на ПК через `local_audio_worker` — у нескольких воркеров общее состояние не разделяется.
- Скрипты админки: **`i18n.js`**, затем **`app.js` (module)**; в начале **`app.js`** — **`import "./screen_widgets.js"`** и модули из **`static/admin/`** (в т.ч. **`preview.js`**, **`audio-stream.js`**, **`data-import.js`**, **`bells.js`**); порядок гарантирован для превью и локализации.
- Бэкенд — пакет **`guardschool/`** (`gs_*.py`, воркеры звука); в корне лежит только тонкий **`app.py`** для **`uvicorn app:app`**. **`data/`** и **`static/`** — в корне репозитория; **`change_log_seed.json`** — сид для журнала. На фронте — **`static/admin/escape-html.js`** и прочее в `static/admin/`.

### Сборка exe

```powershell
build_exe.bat
```

Результат: `dist/GuardSchool.exe`, рядом создаётся папка `data`.

### Формат Excel (кратко)

Колонки по датам: `Дата`, `Класс`, `Урок1` …  
Пример: `01.04.2026 | 5 | Русский | Английский | Математика`  

Образцы и автоимпорт из `data/import/` — без изменения логики прежних релизов.

### Лицензия

**MIT** — см. [`LICENSE`](LICENSE). Для коммерции (поддержка, хостинг, кастомизация) согласуйте условия с правообладателем при необходимости.

### История версий и журнал в админке

- **Номер сборки** — константа **`APP_VERSION`** в [`guardschool/gs_paths.py`](guardschool/gs_paths.py); тот же номер отдаёт **`GET /api/version`**.
- Во вкладке **«Изменения»** показываются записи из **`data/change_log.json`** (поля `version`, `timestamp`, `message`). Это **не** журнал действий пользователей, а **история релизов** продукта.
- Для пустой/черновой базы записи без `version` приводятся в порядок, а заглушка может заменяться списком из **[`change_log_seed.json`](change_log_seed.json)** в корне репозитория — там же хранится эталонная история для GitHub и свежих установок.
- **Как оформить релиз:** поднять **`APP_VERSION`**, добавить объект в **`change_log_seed.json`** (и при необходимости вызвать **`append_release_note`** в [`guardschool/gs_change_log.py`](guardschool/gs_change_log.py)).

Кратко по веткам **1.02.x** (текущая линия **`APP_VERSION`**) и **1.01.x**:

| Версия | Что вошло |
|--------|-----------|
| **1.02.001** | SaaS и мультитенантность (Host → slug), PostgreSQL public + схемы школ, лицензии/регистрация, режимы **`GUARDSCHOOL_DEPLOYMENT_MODE`**, ориентация экрана и меню виджетов, демо-токены; подробности в **`change_log_seed.json`**. |
| **1.01.004** | Пакет **`guardschool/`**, корневой **`app.py`** для uvicorn; подсветка «текущий урок» по поясу школы и сдвигу часов; фон ТВ после перерисовки сетки; фокус модалок; разнос **`static/admin/*`**. |
| **1.01.003** | Модуль журнала релизов, плавная смена фона, новые анимации карусели. |
| **1.01.002** | «Звук ПК», настройки программы, палитра виджетов, превью. |
| **1.01.001** | Усиление безопасности (ZIP, экран, cookie, XSS), аудит subprocess, вынос модулей из монолита. |
| **1.01.000** | Первая публичная линия: экраны, виджеты, расписание, звонки, ZIP. |

Полная таблица на английском — **[Changelog & versioning](#changelog--versioning)**.

### Что ещё для «продуктового» развития

- Документация для ИТ: порты, бэкап `data/`, обновление версии.
- Контейнер / установщик по запросу заказчика.
- Политика обновлений: changelog, миграции `config.json`.
- Безопасность: HTTPS за прокси, ограничение по IP, сильный пароль админки.
- Телеметрия: сейчас данные никуда не уходят; при добавлении аналитики — явное согласие и отключение по умолчанию.
