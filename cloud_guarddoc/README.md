# Деплой облака GuardSchool (guarddoc.ru)

Каркас не содержит секретов. Скопируйте `.env.example` в `.env` и задайте переменные на сервере.

## Переменные окружения

| Переменная | Назначение |
|------------|------------|
| `GUARDSCHOOL_DATA_DIR` | Каталог `data/` на сервере (вне git) |
| `GUARDSCHOOL_DATABASE_URL` | PostgreSQL (опционально; снимок JSON в БД) |
| `GUARDSCHOOL_SYNC_TOKEN` | Секрет для `GET /api/sync/status` и `/api/sync/bundle` |
| `GUARDSCHOOL_TV_BEARER_TOKEN` | Токен для ТВ: `Authorization: Bearer` на `/api/screen/{slug}` (обязателен для демо из интернета) |
| `GUARDSCHOOL_SAAS_MODE` | `1` — режим облака: без тяжёлых загрузок, но **расписание из Excel** и ZIP недели разрешены с лимитами |
| `GUARDSCHOOL_ADMIN_PASSWORD` | Пароль первого админа (≥8 символов, буквы+цифры); создаётся **автоматически** без `/setup` |
| `GUARDSCHOOL_ADMIN_USERNAME` | Логин (по умолчанию `admin`) |
| `GUARDSCHOOL_SKIP_SAAS_BOOTSTRAP` | `1` — **не** создавать админа из env (удалили `auth.json` → откройте `/setup` и задайте логин/пароль вручную) |
| Публичное демо `/try-demo` (портал) | По умолчанию тенант-песочница **`demo`** (`GUARDSCHOOL_DEMO_TENANT_SLUG`, каталог `tenants/demo/data`). **Не задавайте slug песочницы равным боевой школе** (например `school`): иначе плашка «Демо» и cookie `/demo/…` окажутся на том же `school.*`, что и рабочий кабинет. Редирект на `demo.<домен>`; явный хост: `GUARDSCHOOL_TRY_DEMO_REDIRECT_HOST`. Ссылка `/demo/…` на **другом** поддомене школы без `GUARDSCHOOL_DEMO_ALLOW_ANY_TENANT=1` отклоняется. Однократный сброс песочницы при старте: `GUARDSCHOOL_TRY_DEMO_RESET_ON_START=1`. «Всё на одном хосте» (`GUARDSCHOOL_TRY_DEMO_USE_PUBLIC_SCHOOL_HOST` + `GUARDSCHOOL_PUBLIC_SCHOOL_HOST`) — только если осознанно смешиваете хосты; иначе гости и демо-cookie попадут на URL боевой школы. Логин владельца песочницы: `GUARDSCHOOL_TRY_DEMO_ADMIN_USERNAME` / `GUARDSCHOOL_TRY_DEMO_ADMIN_PASSWORD`. Провайдер: `GUARDSCHOOL_DEMO_ALLOW_ANY_TENANT=1`. |
| Лимиты (опционально) | `GUARDSCHOOL_SAAS_MAX_SCHEDULE_XLSX_BYTES` (по умолчанию 15 МБ), `GUARDSCHOOL_SAAS_MAX_SCHEDULE_JSON_BYTES` (1 МБ), `GUARDSCHOOL_SAAS_MAX_USER_DATA_BYTES` (15 МБ суммарно JSON), `GUARDSCHOOL_SAAS_MAX_WEEKLY_ZIP_BYTES` (15 МБ) |
| TLS | Прокси (nginx/caddy) с Let's Encrypt на `guarddoc.ru` |
| Выход из демо | После «Выйти из демо» браузер уходит на главную портала: по умолчанию `https://guarddoc.ru`. Переопределение: `GUARDSCHOOL_DEMO_EXIT_URL` или `GUARDSCHOOL_PORTAL_PUBLIC_URL`. |
| Библиотека для песочницы демо | `GUARDSCHOOL_TRY_DEMO_LIBRARY_DIR` — абсолютный путь к каталогу с такой же структурой, как у `data/` основной школи (подкаталоги `uploads/` и при необходимости `break_music/`). При старте процесса они копируются в `tenants/<demo>/data` (слияние файлов). |
| Лицензии: срок по умолчанию | `GUARDSCHOOL_LICENSE_DEFAULT_TERM_YEARS` — если при `POST /api/provider/licenses` не указаны `expires_years` и `expires_days`, выставить срок в календарных годах от момента выдачи (например `1`). |

## ADM (лицензии, провайдер)

Страница **`/ADM`** (заглавными буквами). Запрос **`/adm`** перенаправляется на `/ADM` (302).

Если вместо страницы приходит JSON `{"detail":"Not found"}` на **`/ADM`**: приложение не считает запрос порталом — чаще всего до uvicorn доходит **`Host: 127.0.0.1`** без внешнего имени. В `location /` для портала обязательно **`proxy_set_header Host $host;`** и желательно **`proxy_set_header X-Forwarded-Host $host;`** (см. пример в этом каталоге), затем `nginx -t` и reload.

Чтобы не видеть «ADM не настроен» и иметь возможность создавать лицензии, в окружении сервиса задайте **один** из вариантов:

1. **Логин и пароль** для формы входа: `GUARDSCHOOL_PORTAL_ADM_USERNAME` и `GUARDSCHOOL_PORTAL_ADM_PASSWORD` (требования к паролю как у админа школы: ≥8 символов, буквы и цифры).
2. **Токен провайдера** для страницы с полем Bearer: `GUARDSCHOOL_PROVIDER_ADMIN_TOKEN`.

Это **не** логин админки школы на `school.*`: ADM — отдельный провайдерский вход на корневом домене портала (`guarddoc.ru` / `www`), данные для него только в переменных окружения сервиса.

**API лицензий (провайдер / ADM):** `GET …/licenses` — список (`tenant_slug`, `registered`, таймштампы `issued_at` / `expires_at`, поля **`issued_year`** и **`expires_year`** для отчётности); `GET …/{key_hash}`; `POST …` — тело: `plan_id`, `notes`, опционально **`expires_years`** (календарных лет от момента выдачи) или **`expires_days`**; если не задано ни то ни другое, при установленном **`GUARDSCHOOL_LICENSE_DEFAULT_TERM_YEARS`** (целое &gt;0) срок выставляется автоматически. **`PATCH …/{key_hash}`** — в т.ч. **`plan_id`** (разрешена смена плана после регистрации: SaaS ↔ полный комплект и т.д.), **`expires_years_from_issue`** (лет от **`issued_at`** в БД; `0` — снять срок), **`expires_years_from_now`** (лет от текущего UTC). Приоритет полей срока в одном запросе: `expires_at` → `expires_years_from_issue` → `expires_years_from_now` → `expires_days`. `DELETE` — только неиспользованная лицензия.

## TLS (certbot + nginx)

Перед выпуском сертификата **DNS** у регистратора для всех имён должен указывать на ваш сервер (A-запись), иначе ACME HTTP-01 не пройдёт; сами записи не «включают» HTTPS — сертификат выпускаете вы на машине (certbot/nginx).

Пример **расширения** существующего сертификата новыми поддоменами (подставьте свой путь к конфигу nginx):

```bash
sudo certbot --nginx -d guarddoc.ru -d www.guarddoc.ru -d school.guarddoc.ru -d demo.guarddoc.ru
```

Если используете `certonly` + webroot:

```bash
sudo certbot certonly --webroot -w /var/www/html -d guarddoc.ru -d www.guarddoc.ru -d school.guarddoc.ru -d demo.guarddoc.ru
```

После успешной выдачи перезагрузите nginx (`sudo nginx -t && sudo systemctl reload nginx`). В `server_name` каждого блока должны быть перечислены нужные хосты, либо отдельные `server` на каждый поддомен с одним и тем же `ssl_certificate` (путь к fullchain из `/etc/letsencrypt/live/...`).

Если в браузере по-прежнему «Не защищено»: проверьте, что открытое имя **входит** в SAN сертификата (вкладка «Сведения о сертификате»), сертификат не просрочен, цепочка до Let's Encrypt полная. Строка «Вы отключили предупреждения…» в Chrome относится к **настройке сайта в браузере**, а не к серверу — включите предупреждения обратно для честной проверки.

### «Welcome to nginx!» вместо сайта

Certbot **не настраивает** проксирование на uvicorn: в блоке `server` для `guarddoc.ru` / `demo.guarddoc.ru` должен быть **`location / { proxy_pass http://127.0.0.1:<порт>; }`**, а не корень с дефолтным `index.html` nginx.

1. Узнайте порт процесса GuardSchool: `sudo systemctl cat guardschool`, `sudo ss -tlnp | grep -E '8000|uvicorn|python'`, либо `curl -sS http://127.0.0.1:8000/api/version` (если отказ — смотрите `journalctl -xeu guardschool -n 80`).
2. В `/etc/nginx/sites-enabled/default` (или отдельном файле под портал) внутри `server { ... ssl ... }` для нужных `server_name` добавьте:

```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

(Подставьте порт из unit-файла, если не `8000`.)

3. `sudo nginx -t && sudo systemctl reload nginx`.

Готовый пример блоков `server` для **guarddoc.ru**, **www**, **demo** (редирект с 80, HTTPS, `proxy_pass`): файл **`nginx-portal-proxy.example.conf`** в этом каталоге. Скопируйте в `/etc/nginx/sites-available/`, включите через `sites-enabled`.

Если в логе `nginx -t` есть **«conflicting server name … ignored»**, второй конфиг **не работает**: обычно certbot добавил те же имена в **`sites-available/default`**. Удалите или закомментируйте в `default` соответствующие блоки `server { … }` (с пометкой managed by Certbot для портала), чтобы для портала остался только `guarddoc-portal.conf` с `proxy_pass`.

Если после правок появилось **`server_name directive is not allowed here`** — сломана структура фигурных скобок в `default`. Восстановите резервную копию (если делали):  
`sudo cp /etc/nginx/sites-available/default.bak-certbot /etc/nginx/sites-available/default`  
затем `sudo nginx -t` и правьте снова, удаляя **целиком** блоки `server { … }`, а не отдельные строки внутри.

### SSH с вашего ПК

Ассистент в Cursor **не подключается** к вашему VPS по SSH. Удобный вход без пароля:

1. **Один раз** в PowerShell из корня репозитория (подставьте свой `user@host` при необходимости):
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\cloud_guarddoc\setup-ssh-key-windows.ps1
   ```
   Скрипт создаст `%USERPROFILE%\.ssh\id_ed25519_guarddoc`, затем запросит **пароль SSH один раз** и добавит публичный ключ в `authorized_keys` на сервере. Флаг `-SkipInstall` — только создать ключ и показать `.pub` для ручной вставки.  
   Сообщения в скрипте на **английском**, чтобы Windows PowerShell 5.1 не ломал разбор из‑за кодировки UTF‑8 без BOM.

2. Скопируйте **`ssh-local.example.bat`** → **`ssh-local.bat`** (в `.gitignore`); при наличии ключа bat вызовет `ssh -i ...`. Фрагмент для `~/.ssh/config`: **`ssh-config-snippet.example.txt`**.

Пароли в bat-файлах и в git не храните.

## Демо заказчику (за час)

1. Поднять процесс с `GUARDSCHOOL_SAAS_MODE=1`, `GUARDSCHOOL_DATA_DIR`, `GUARDSCHOOL_ADMIN_PASSWORD`, `GUARDSCHOOL_TV_BEARER_TOKEN`, HTTPS.
2. Открыть `https://ваш-домен/` — войти **admin** / пароль из env.
3. Загрузить Excel расписания или сдвинуть звонок (переопределения / звонки в админке).
4. Открыть на ТВ или в браузере:  
   `https://ваш-домен/screen/tv-1?gs_tv_token=<тот же GUARDSCHOOL_TV_BEARER_TOKEN>`  
   Через `poll_interval_sec` экран подтянет новые данные с **того же сервера** (без локальной копии).

## Запуск

Из корня репозитория GuardSchool (установлены зависимости из `requirements.txt`):

```bash
set GUARDSCHOOL_DATA_DIR=/var/lib/guardschool/data
set GUARDSCHOOL_DATABASE_URL=postgresql://...
set GUARDSCHOOL_SYNC_TOKEN=...
set GUARDSCHOOL_TV_BEARER_TOKEN=...
set GUARDSCHOOL_SAAS_MODE=1
python -m uvicorn app:app --host 0.0.0.0 --port 8000
```

При первом старте таблица `school_snapshot` создаётся автоматически; начальные данные — из файлов в `GUARDSCHOOL_DATA_DIR` или пустые JSON после первого сохранения в админке.

## Клиент (школа)

Локальный ПК: задать `cloud_base_url`, токен синхронизации (или `GUARDSCHOOL_CLOUD_SYNC_TOKEN`), интервал. ТВ: открыть `/screen/{slug}?gs_fallback_base=https://guarddoc.ru&gs_tv_token=...`.

## Не в этой версии

WebSocket/SSE push и отдельный слой «глобальной аварийки» PAK — при необходимости отдельные задачи поверх текущего API.
