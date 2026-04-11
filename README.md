# GuardSchool

**Self-hosted schedules, bells, and signage in the browser.** The product is **designed around a school lesson timetable** (classes, bells, days), but the underlying pattern is generic: **time + structured data** on one or more screens. The same setup can show **duty rosters**, **shift plans**, room booking-style boards, or any other table you feed through the same import and widget flow—not only “lessons.”

Runs **fully offline** after setup: data, settings, and media stay on your machine — **no mandatory cloud or external APIs**. Administration is **inside your network (LAN)**; you choose whether and how to expose HTTP access.

**Clients are just web pages:** a **mini PC + monitor**, a **smart TV** with a built-in browser, a **tablet** on a reception counter — if it can open a URL in fullscreen, it can be a display. No vendor app store required.

Admin UI: **English and Russian** (language switch in the header). Settings include **timezone** (for “today” in schedules and date/time on displays) and **clock offset in minutes** if TV clocks drift.

---

## Contents

- [Features](#features)
- [Quick start](#quick-start)
- [Localization & time](#localization--time)
- [Import / export](#import--export)
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

## Localization & time

- UI language: **Language** dropdown in the header (next to **Settings**).
- Timezone and offset: **Language, time & timezone** inside **Settings**.  
  “Today” for schedules and bells is computed **in the selected timezone**, not silently tied to the server OS clock without configuration.
- Import / Excel / ZIP validation messages from the API follow the selected UI language (the admin page sends `X-UI-Locale: en` or `ru`).

## Import / export

In the admin UI: **Export ZIP** / **Import ZIP** — full snapshot of config, schedules, bells, and uploads. Use for backups and moving between machines **without cloud**.

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
- **Screen API**: `GET /api/screen/{slug}` returns schedule and display JSON **without auth** (for TV browsers on the LAN). Treat network access accordingly.
- **Admin POSTs**: no separate CSRF tokens; browsers rely on **SameSite** session cookies. For high-threat deployments, add tokens or restrict origins.
- **Process model**: run **one** uvicorn worker if you rely on in-process PC audio state (`local_audio_worker` globals); multiple workers do not share that state.
- **Code layout**: admin UI is `static/app.js` (ES module) plus `static/admin/*.js`; load order in `index.html` is **`i18n.js` → `screen_widgets.js` → `app.js` (module)**. `app.py` is split incrementally: **`gs_paths.py`**, **`gs_admin_http.py`**, **`gs_jsonio.py`**, **`gs_fs.py`** (`clear_directory`), **`gs_change_log_bootstrap.py`**, **`gs_weekly_template.py`**, **`gs_ensure_dirs.py`**, **`gs_import_bundle.py`** (full + weekly ZIP). Admin helpers include **`static/admin/escape-html.js`**.
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

### Локализация и время

- Язык: список **«Язык»** в шапке.
- Пояс и сдвиг: блок **«Язык, время и пояс»** в меню **Настройки**.  
  «Сегодня» для расписания и звонков считается **в выбранном поясе**.
- Тексты ошибок при импорте Excel/ZIP на стороне API соответствуют выбранному языку интерфейса (заголовок `X-UI-Locale: en` или `ru`).

### Импорт и экспорт

**Экспорт ZIP** / **Импорт ZIP** в админке — полный снимок настроек, расписаний, звонков и загрузок. Импорт полного архива принимается только если в **корне ZIP** есть **`config.json`** (как в экспорте GuardSchool); пустой или чужой архив не очищает `uploads`.

### Безопасность и эксплуатация

- **`GET /api/screen/{slug}`** отдаёт JSON экрана **без входа** — рассчитано на ТВ в LAN; ограничивайте доступ к сети при чувствительных данных.
- Сессия админки: флаг **`Secure`** у cookie включается при HTTPS или заголовке **`X-Forwarded-Proto: https`** у прокси.
- **Один процесс** uvicorn, если используете звук на ПК через `local_audio_worker` — у нескольких воркеров общее состояние не разделяется.
- Скрипты админки: **`i18n.js` → `screen_widgets.js` → `app.js` (type=module)`** — порядок важен для превью и локализации.
- Бэкенд постепенно выносится из **`app.py`**: `gs_paths.py`, `gs_admin_http.py`, `gs_jsonio.py`, `gs_fs.py`, `gs_change_log_bootstrap.py`, `gs_weekly_template.py`, `gs_ensure_dirs.py`, `gs_import_bundle.py` (ZIP); **`static/admin/escape-html.js`** на фронте.

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

### Журнал версий (`data/change_log.json`)

Файл хранит **историю выпусков программы** (номер версии, дата, короткий текст «что нового»). Он **не** является журналом действий пользователя в админке. При первом запуске создаётся стартовая запись; при каждом релизе поднимайте `APP_VERSION` в `gs_paths.py` и добавляйте новую строку в JSON или вызывайте `append_release_note` из кода.

### Что ещё для «продуктового» развития

- Документация для ИТ: порты, бэкап `data/`, обновление версии.
- Контейнер / установщик по запросу заказчика.
- Политика обновлений: changelog, миграции `config.json`.
- Безопасность: HTTPS за прокси, ограничение по IP, сильный пароль админки.
- Телеметрия: сейчас данные никуда не уходят; при добавлении аналитики — явное согласие и отключение по умолчанию.
