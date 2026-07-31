# Развёртывание и эксплуатация (community / local)

Краткий runbook для ИТ: порты, данные, обновление, прокси и ограничения процесса.

## Порты и URL

| Сервис | По умолчанию | Назначение |
|--------|--------------|------------|
| HTTP | **8000** | Админка `/`, экраны `/screen/{slug}`, API `/api/*` |
| LAN | `0.0.0.0:8000` | Доступ с ТВ и рабочих станций в сети |

Типичные URL после установки:

- Админка: `http://<server>:8000/`
- Экран: `http://<server>:8000/screen/tv-1` (slug из `config.json`)

Проверка живости: `GET /api/health` (версия, режим, запись в `data/`).

## Переменные окружения (local)

| Переменная | Значение | Описание |
|------------|----------|----------|
| `GUARDSCHOOL_DEPLOYMENT_MODE` | `local` | Community edition без SaaS |
| `GUARDSCHOOL_DATA_DIR` | путь | Каталог данных (по умолчанию `./data` рядом с приложением) |
| `GUARDSCHOOL_TV_BEARER_TOKEN` | секрет (опц.) | Если задан — `GET /api/screen/*` требует `Authorization: Bearer …` |
| `GUARDSCHOOL_SKIP_DEMO_SEED` | `1` (опц.) | Не создавать demo-данные при `/api/setup` |

Hybrid/SaaS — см. [architecture.md](architecture.md), [private_modules.md](private_modules.md).

## Один процесс uvicorn (PC audio)

Модуль **`local_audio_worker`** держит состояние звонков **в памяти одного процесса**.

- Запускайте **один worker**: `uvicorn app:app --host 0.0.0.0 --port 8000` **без** `--workers 2+`.
- В Docker и systemd — один экземпляр приложения на машину с PC audio.
- Если PC audio не используется, несколько workers теоретически возможны, но не тестировались для community.

## Резервное копирование

Критичный каталог — **`data/`** (или `GUARDSCHOOL_DATA_DIR`):

| Файл / папка | Содержимое |
|--------------|------------|
| `config.json` | Экраны, виджеты, настройки, пароль админки (хэш) |
| `schedule.json`, `full_schedule.json`, `bell_schedules.json` | Расписания |
| `uploads/` | Фоны, звуки звонков, медиа |
| `auth.json` | Сессии (можно не бэкапить, но безопаснее включать в ZIP) |

**Рекомендуемый способ:** в админке **Экспорт ZIP** — полный снимок для миграции и бэкапа.

Восстановление: **Импорт ZIP** (в корне архива обязан быть `config.json`).

Ручной бэкап: остановить сервер → скопировать каталог `data/` → запустить снова.

## Обновление версии

1. Остановить uvicorn / службу / контейнер.
2. Сделать **ZIP-экспорт** или копию `data/`.
3. Обновить код (git pull, новый exe, новый образ Docker).
4. Запустить приложение; при первом входе проверить вкладку **«Изменения»** (`change_log.json`).
5. При смене схемы `config.json` приложение применяет `sanitize_config` при загрузке — сохраните конфиг через админку после проверки экранов.

Версия продукта: `APP_VERSION` в `guardschool/gs_paths.py`, также `GET /api/version` и `GET /api/health`.

## Reverse proxy (HTTPS)

GuardSchool слушает HTTP. В продакшене — TLS на nginx, Caddy или IIS ARR:

```nginx
server {
    listen 443 ssl;
    server_name school.example.local;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

Cookie сессии админки получает флаг **`Secure`**, если запрос HTTPS или `X-Forwarded-Proto: https`.

## Безопасность в LAN

- `GET /api/screen/{slug}` — **без авторизации** (для браузеров ТВ). Ограничивайте доступ к порту 8000 файрволом/VLAN.
- Задайте **сильный пароль** админки при первой настройке.
- Опционально: `GUARDSCHOOL_TV_BEARER_TOKEN` + заголовок на ТВ (если поддерживается клиентом/прокси).

## Docker (community)

Из корня репозитория:

```bash
docker compose up -d --build
```

Данные — volume `guardschool-data` → `/data` (`GUARDSCHOOL_DATA_DIR`).

При **первой настройке** (`POST /api/setup`, community/local) создаётся demo-конфиг: экран `tv-1`, недельное расписание группы «5», шаблон сигналов, приветственное объявление. Отключить: `GUARDSCHOOL_SKIP_DEMO_SEED=1`.

Подробности: [`docker-compose.yml`](../docker-compose.yml), [`Dockerfile`](../Dockerfile).

## Windows exe

```powershell
build_exe.bat
```

Результат: `dist/GuardSchool.exe`, каталог `data/` создаётся **рядом с exe**. Бэкап и обновление — как для `data/` выше. В spec: `static/`, `widgets/`, `change_log_seed.json` (`GuardSchool.spec`, `GuardSchool_full.spec`).

## Мониторинг

| Endpoint | Назначение |
|----------|------------|
| `GET /api/health` | `status`, `version`, `deployment_mode`, `data_dir_writable` |
| `GET /api/version` | Только версия продукта |

Пример: опрос `data_dir_writable: false` — диск переполнен или нет прав на `GUARDSCHOOL_DATA_DIR`.
