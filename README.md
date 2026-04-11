# GuardSchool

**Local school schedule and bell system for TVs and PCs in the browser.**  
Runs **fully offline** after setup: data, settings, and media stay on your machine — **no mandatory cloud or external APIs**. Administration is **inside your network (LAN)**; you choose whether and how to expose HTTP access.

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

- Multi-screen admin (tabs per TV), widget grid, schedules, bells, backgrounds
- One URL per display: `/screen/{slug}`
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
- **Security**: HTTPS behind a reverse proxy, IP allowlists, strong admin password.
- **Branding**: logo, `ico.png`, custom copy.
- **Telemetry**: the app does not phone home by default; any analytics would require explicit consent and opt-out.

---

## Русский

**README для GitHub:** репозиторий ориентирован на публичное описание проекта; блок ниже — краткая русская версия для школ и интеграторов.

### GuardSchool — что это

**Локальная система показа школьного расписания и звонка на ТВ и ПК в браузере.**  
После установки работает **полностью офлайн**: данные и медиа хранятся у вас, **без обязательного облака и внешних API**. Управление — **внутри вашей сети (LAN)**.

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

### Импорт и экспорт

**Экспорт ZIP** / **Импорт ZIP** в админке — полный снимок настроек, расписаний, звонков и загрузок.

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

### Что ещё для «продуктового» развития

- Документация для ИТ: порты, бэкап `data/`, обновление версии.
- Контейнер / установщик по запросу заказчика.
- Политика обновлений: changelog, миграции `config.json`.
- Безопасность: HTTPS за прокси, ограничение по IP, сильный пароль админки.
- Телеметрия: сейчас данные никуда не уходят; при добавлении аналитики — явное согласие и отключение по умолчанию.
