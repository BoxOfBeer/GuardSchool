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
| Публичное демо `/try-demo` (портал) | По умолчанию тенант-песочница `demo` и редирект на `demo.<ваш-домен>` (отдельный каталог `tenants/demo/data` с дефолтным `config.json`). Нужна DNS-запись на этот поддомен. Явный хост: `GUARDSCHOOL_TRY_DEMO_REDIRECT_HOST`. Ссылка `/demo/…` на **боевом** поддомене школы без `GUARDSCHOOL_DEMO_ALLOW_ANY_TENANT=1` отклоняется — гости не видят чужие экраны и расписание. Однократный сброс песочницы к дефолту при каждом старте процесса: `GUARDSCHOOL_TRY_DEMO_RESET_ON_START=1`. Старый вариант «всё на одном `GUARDSCHOOL_PUBLIC_SCHOOL_HOST`»: `GUARDSCHOOL_TRY_DEMO_USE_PUBLIC_SCHOOL_HOST=1` и при необходимости `GUARDSCHOOL_DEMO_TENANT_SLUG=school` (данные общие с этой школой — не рекомендуется). Логин владельца песочницы (не обязателен для гостя): `GUARDSCHOOL_TRY_DEMO_ADMIN_USERNAME` / `GUARDSCHOOL_TRY_DEMO_ADMIN_PASSWORD` (≥8 символов, буквы и цифры). Демо на произвольном `tenant_slug` (выдача провайдером): `GUARDSCHOOL_DEMO_ALLOW_ANY_TENANT=1`. |
| Лимиты (опционально) | `GUARDSCHOOL_SAAS_MAX_SCHEDULE_XLSX_BYTES` (по умолчанию 15 МБ), `GUARDSCHOOL_SAAS_MAX_SCHEDULE_JSON_BYTES` (1 МБ), `GUARDSCHOOL_SAAS_MAX_USER_DATA_BYTES` (15 МБ суммарно JSON), `GUARDSCHOOL_SAAS_MAX_WEEKLY_ZIP_BYTES` (15 МБ) |
| TLS | Прокси (nginx/caddy) с Let's Encrypt на `guarddoc.ru` |
| Выход из демо | После «Выйти из демо» браузер уходит на главную портала: по умолчанию `https://guarddoc.ru`. Переопределение: `GUARDSCHOOL_DEMO_EXIT_URL` или `GUARDSCHOOL_PORTAL_PUBLIC_URL`. |

## TLS (certbot + nginx)

Перед выпуском сертификата **DNS** для всех имён должен указывать на сервер (A-запись), иначе ACME HTTP-01 не пройдёт.

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

Ассистент в Cursor **не подключается** к вашему VPS по SSH. Удобный вход без пароля в файлах репозитория: скопируйте **`ssh-local.example.bat`** → **`ssh-local.bat`** (файл в `.gitignore`), укажите `SSH_TARGET=`, при необходимости настройте **SSH-ключ** на сервере (`~/.ssh/authorized_keys`). Пароли в bat-файлах и в git не храните.

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
