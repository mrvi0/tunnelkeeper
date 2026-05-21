# TunnelKeeper REST API

Базовый URL: `http://<bastion-host>:<port>/api/v1`

Интерактивная схема (если API включён): `http://<host>:<port>/docs`

---

## Включение API

В `.env` на бастионе:

```env
ENABLE_API=true
API_TOKEN=your-secret-at-least-16-chars
```

Опционально только API без веб-панели:

```env
ENABLE_WEB_UI=false
ENABLE_API=true
```

Запуск в foreground:

```bash
sudo -E make run
# или API-only:
sudo -E make run-api
```

Запуск как служба (systemd):

```bash
make install
cp .env.example .env   # настроить API_TOKEN, APP_HOST, APP_PORT
sudo make install-service
```

После установки:

```bash
sudo systemctl status tunnelkeeper
sudo systemctl restart tunnelkeeper
sudo journalctl -u tunnelkeeper -f
```

---

## Авторизация

Каждый запрос к `/api/v1/*` должен содержать токен из `API_TOKEN`.

**Вариант 1 — заголовок Bearer (рекомендуется):**

```http
Authorization: Bearer <API_TOKEN>
```

**Вариант 2 — заголовок X-API-Key:**

```http
X-API-Key: <API_TOKEN>
```

Для примеров ниже задайте переменные в shell:

```bash
export BASE_URL="http://127.0.0.1:8090"
export API_TOKEN="your-secret-at-least-16-chars"
```

Шаблон для `curl`:

```bash
curl -s -H "Authorization: Bearer ${API_TOKEN}" \
  -H "Content-Type: application/json" \
  "${BASE_URL}/api/v1/..."
```

---

## Коды ответов

| Код | Значение |
|-----|----------|
| 200 | Успех (GET, PATCH, DELETE с телом) |
| 201 | Создано (POST) |
| 400 | Ошибка валидации / бизнес-правило |
| 401 | Нет или неверный API-токен |
| 403 | Readonly mode (`READONLY_MODE=true`) |
| 404 | Сущность не найдена |
| 500 | Ошибка Linux / неожиданный сбой |

Тело ошибки:

```json
{"detail": "описание ошибки"}
```

---

## Рекомендуемый порядок действий

Типичный сценарий на новом бастионе:

1. `GET /health` — проверить доступ и sshd  
2. `POST /destinations` — добавить цели (host:port)  
3. `POST /users` — создать tunnel-пользователя с `destination_ids`  
4. `POST /users/{id}/keys` — добавить SSH-ключ  
5. При сбое файлов — `POST /users/{id}/regenerate`  

При изменении destinations у пользователя — `PATCH /users/{id}` с новым списком `destination_ids`.

---

## Health

### Проверить состояние агента

**Команда:** `GET /api/v1/health`

**Пример:**

```bash
curl -s -H "Authorization: Bearer ${API_TOKEN}" \
  "${BASE_URL}/api/v1/health"
```

**Пример ответа:**

```json
{
  "status": "ok",
  "readonly_mode": false,
  "enable_web_ui": true,
  "enable_api": true,
  "sshd_warning": null
}
```

Если `sshd_warning` не `null` — на хосте не настроен Include в `sshd_config` (см. `make setup-sshd`).

---

## Destinations (глобальный каталог PermitOpen)

### Список всех destinations

**Команда:** `GET /api/v1/destinations`

**Пример:**

```bash
curl -s -H "Authorization: Bearer ${API_TOKEN}" \
  "${BASE_URL}/api/v1/destinations"
```

**Пример ответа:**

```json
[
  {
    "id": 1,
    "alias": "prod-db",
    "host": "10.10.10.10",
    "port": 5432,
    "comment": "PostgreSQL prod",
    "enabled": true,
    "created_at": "2026-05-21T12:00:00"
  }
]
```

---

### Создать destination

**Команда:** `POST /api/v1/destinations`  
**Тело (JSON):** `alias`, `host`, `port`, опционально `comment`, `enabled` (по умолчанию `true`).

**Пример:**

```bash
curl -s -X POST -H "Authorization: Bearer ${API_TOKEN}" \
  -H "Content-Type: application/json" \
  "${BASE_URL}/api/v1/destinations" \
  -d '{
    "alias": "staging-api",
    "host": "10.20.30.40",
    "port": 443,
    "comment": "HTTPS staging",
    "enabled": true
  }'
```

**Пример ответа (201):**

```json
{
  "id": 2,
  "alias": "staging-api",
  "host": "10.20.30.40",
  "port": 443,
  "comment": "HTTPS staging",
  "enabled": true,
  "created_at": "2026-05-21T12:05:00"
}
```

Пара `host` + `port` уникальна. Дубликат → `400`.

---

### Получить destination по ID

**Команда:** `GET /api/v1/destinations/{dest_id}`

**Пример:**

```bash
curl -s -H "Authorization: Bearer ${API_TOKEN}" \
  "${BASE_URL}/api/v1/destinations/2"
```

---

### Изменить destination

**Команда:** `PATCH /api/v1/destinations/{dest_id}`  
**Тело:** любое подмножество полей `alias`, `host`, `port`, `comment`, `enabled`.

**Только включить/выключить:**

```bash
curl -s -X PATCH -H "Authorization: Bearer ${API_TOKEN}" \
  -H "Content-Type: application/json" \
  "${BASE_URL}/api/v1/destinations/2" \
  -d '{"enabled": false}'
```

**Изменить alias и comment:**

```bash
curl -s -X PATCH -H "Authorization: Bearer ${API_TOKEN}" \
  -H "Content-Type: application/json" \
  "${BASE_URL}/api/v1/destinations/2" \
  -d '{
    "alias": "staging-api-v2",
    "comment": "updated label"
  }'
```

При изменении полей destination пересобираются sshd-конфиги у всех пользователей, у которых она привязана.

---

### Удалить destination

**Команда:** `DELETE /api/v1/destinations/{dest_id}`

**Пример:**

```bash
curl -s -X DELETE -H "Authorization: Bearer ${API_TOKEN}" \
  "${BASE_URL}/api/v1/destinations/2"
```

**Пример ответа:**

```json
{"message": "Destination deleted"}
```

---

## Tunnel users

### Список пользователей

**Команда:** `GET /api/v1/users`

**Пример:**

```bash
curl -s -H "Authorization: Bearer ${API_TOKEN}" \
  "${BASE_URL}/api/v1/users"
```

**Пример ответа:**

```json
[
  {
    "id": 1,
    "username": "tunnel-alex",
    "comment": "Alex dev tunnel",
    "linux_home": "/home/tunnel-alex",
    "linux_shell": "/usr/sbin/nologin",
    "supplementary_groups": "docker",
    "allow_tcp_forwarding": true,
    "permit_tty": false,
    "x11_forwarding": false,
    "allow_agent_forwarding": false,
    "force_command": "echo \"Tunnel only\";exit",
    "created_at": "2026-05-21T12:10:00",
    "destination_ids": [1, 2],
    "sshd_config_path": "/etc/ssh/sshd_config.d/generated/tunnel-alex.conf"
  }
]
```

---

### Создать tunnel-пользователя

**Команда:** `POST /api/v1/users`  
**Действие на хосте:** `useradd`, привязка destinations, запись `authorized_keys` и `sshd` snippet, `reload sshd`.

**Тело (JSON):**

| Поле | Тип | По умолчанию | Описание |
|------|-----|--------------|----------|
| `username` | string | — | Linux-имя, например `tunnel-alex` |
| `comment` | string | `""` | Комментарий |
| `linux_home` | string | `/home/<username>` | Домашний каталог |
| `linux_shell` | string | `/usr/sbin/nologin` | Или ключ: `nologin`, `bash`, `false`, `sh` |
| `supplementary_groups` | string | `""` | Через запятую, напр. `docker,sudo` |
| `allow_tcp_forwarding` | bool | `true` | sshd Match |
| `permit_tty` | bool | `false` | Разрешить TTY |
| `x11_forwarding` | bool | `false` | |
| `allow_agent_forwarding` | bool | `false` | |
| `force_command` | string | `echo "Tunnel only";exit` | Пусто при `tunnel_only: false` |
| `tunnel_only` | bool | `true` | `true` → nologin + ForceCommand если не задан |
| `destination_ids` | int[] | `[]` | ID из `/destinations` (только enabled) |

**Пример — tunnel-only с двумя destinations:**

```bash
curl -s -X POST -H "Authorization: Bearer ${API_TOKEN}" \
  -H "Content-Type: application/json" \
  "${BASE_URL}/api/v1/users" \
  -d '{
    "username": "tunnel-alex",
    "comment": "Alex dev tunnel",
    "supplementary_groups": "docker",
    "tunnel_only": true,
    "destination_ids": [1, 2]
  }'
```

**Пример — разрешить интерактивный login (bash):**

```bash
curl -s -X POST -H "Authorization: Bearer ${API_TOKEN}" \
  -H "Content-Type: application/json" \
  "${BASE_URL}/api/v1/users" \
  -d '{
    "username": "tunnel-qa",
    "comment": "QA with shell",
    "linux_shell": "bash",
    "tunnel_only": false,
    "permit_tty": true,
    "force_command": "",
    "destination_ids": [1]
  }'
```

**Пример ответа (201):** объект как в списке users (см. выше).

---

### Получить пользователя (детально)

**Команда:** `GET /api/v1/users/{user_id}`  
**Ответ:** пользователь + вложенные `keys` и `destinations`.

**Пример:**

```bash
curl -s -H "Authorization: Bearer ${API_TOKEN}" \
  "${BASE_URL}/api/v1/users/1"
```

**Пример ответа:**

```json
{
  "id": 1,
  "username": "tunnel-alex",
  "comment": "Alex dev tunnel",
  "linux_home": "/home/tunnel-alex",
  "linux_shell": "/usr/sbin/nologin",
  "supplementary_groups": "docker",
  "allow_tcp_forwarding": true,
  "permit_tty": false,
  "x11_forwarding": false,
  "allow_agent_forwarding": false,
  "force_command": "echo \"Tunnel only\";exit",
  "created_at": "2026-05-21T12:10:00",
  "destination_ids": [1, 2],
  "sshd_config_path": "/etc/ssh/sshd_config.d/generated/tunnel-alex.conf",
  "keys": [],
  "destinations": [
    {
      "id": 1,
      "alias": "prod-db",
      "host": "10.10.10.10",
      "port": 5432,
      "comment": "PostgreSQL prod",
      "enabled": true,
      "created_at": "2026-05-21T12:00:00"
    }
  ]
}
```

---

### Обновить пользователя

**Команда:** `PATCH /api/v1/users/{user_id}`  
**Тело:** те же поля, что при создании, кроме `username` (не меняется). Передаётся полный набор настроек (как в UI).

**Пример — сменить destinations и группы:**

```bash
curl -s -X PATCH -H "Authorization: Bearer ${API_TOKEN}" \
  -H "Content-Type: application/json" \
  "${BASE_URL}/api/v1/users/1" \
  -d '{
    "comment": "Alex — prod only",
    "supplementary_groups": "docker",
    "tunnel_only": true,
    "linux_shell": "nologin",
    "allow_tcp_forwarding": true,
    "permit_tty": false,
    "x11_forwarding": false,
    "allow_agent_forwarding": false,
    "force_command": "echo \"Tunnel only\";exit",
    "destination_ids": [1]
  }'
```

**Пример — разрешить login:**

```bash
curl -s -X PATCH -H "Authorization: Bearer ${API_TOKEN}" \
  -H "Content-Type: application/json" \
  "${BASE_URL}/api/v1/users/1" \
  -d '{
    "comment": "Alex with shell",
    "tunnel_only": false,
    "linux_shell": "bash",
    "permit_tty": true,
    "force_command": "",
    "destination_ids": [1, 2]
  }'
```

На хосте: `usermod`, пересборка `authorized_keys` и sshd snippet, reload.

---

### Удалить пользователя

**Команда:** `DELETE /api/v1/users/{user_id}`  
**Действие:** `userdel -r`, удаление home, sshd snippet, reload.

**Пример:**

```bash
curl -s -X DELETE -H "Authorization: Bearer ${API_TOKEN}" \
  "${BASE_URL}/api/v1/users/1"
```

**Пример ответа:**

```json
{"message": "User deleted"}
```

---

### Пересобрать файлы пользователя (regenerate)

**Команда:** `POST /api/v1/users/{user_id}/regenerate`  
**Когда использовать:** после ручных правок на диске, сбоя provision, для проверки синхронизации БД → `authorized_keys` + sshd conf.

**Пример:**

```bash
curl -s -X POST -H "Authorization: Bearer ${API_TOKEN}" \
  "${BASE_URL}/api/v1/users/1/regenerate"
```

**Пример ответа:**

```json
{"message": "Provisioned"}
```

---

## SSH keys (на пользователя)

Ключи пишутся в `~<user>/.ssh/authorized_keys` **без** `permitopen` в строке ключа. Ограничения — только в sshd `Match User`.

### Список ключей пользователя

**Команда:** `GET /api/v1/users/{user_id}/keys`

**Пример:**

```bash
curl -s -H "Authorization: Bearer ${API_TOKEN}" \
  "${BASE_URL}/api/v1/users/1/keys"
```

---

### Добавить SSH-ключ

**Команда:** `POST /api/v1/users/{user_id}/keys`  
**Тело:** `name`, `public_key`, опционально `enabled` (default `true`).

Поддерживаются типы: `ssh-ed25519`, `ssh-rsa`.

**Пример:**

```bash
curl -s -X POST -H "Authorization: Bearer ${API_TOKEN}" \
  -H "Content-Type: application/json" \
  "${BASE_URL}/api/v1/users/1/keys" \
  -d '{
    "name": "alex-laptop",
    "public_key": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleKeyMaterialForDocsOnly9xQ test@example.com",
    "enabled": true
  }'
```

**Пример ответа (201):**

```json
{
  "id": 3,
  "tunnel_user_id": 1,
  "name": "alex-laptop",
  "public_key": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleKeyMaterialForDocsOnly9xQ test@example.com",
  "fingerprint": "SHA256:xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "enabled": true,
  "created_at": "2026-05-21T12:20:00"
}
```

Дубликат того же `public_key` для пользователя → `400`.

---

### Включить / выключить ключ

**Команда:** `PATCH /api/v1/keys/{key_id}`  
**Тело:** `{"enabled": true}` или `{"enabled": false}`

**Пример (отключить):**

```bash
curl -s -X PATCH -H "Authorization: Bearer ${API_TOKEN}" \
  -H "Content-Type: application/json" \
  "${BASE_URL}/api/v1/keys/3" \
  -d '{"enabled": false}'
```

Пересобирается `authorized_keys` пользователя.

---

### Удалить ключ

**Команда:** `DELETE /api/v1/keys/{key_id}`

**Пример:**

```bash
curl -s -X DELETE -H "Authorization: Bearer ${API_TOKEN}" \
  "${BASE_URL}/api/v1/keys/3"
```

**Пример ответа:**

```json
{"message": "Key deleted"}
```

---

## Audit log

### Последние события

**Команда:** `GET /api/v1/audit?limit=<N>`  
**Параметр:** `limit` — от 1 до 500, по умолчанию 50.

**Пример:**

```bash
curl -s -H "Authorization: Bearer ${API_TOKEN}" \
  "${BASE_URL}/api/v1/audit?limit=10"
```

**Пример ответа:**

```json
[
  {
    "id": 42,
    "actor": "api",
    "action": "create_tunnel_user",
    "target": "user:tunnel-alex",
    "details": "destinations=[1, 2]",
    "created_at": "2026-05-21T12:10:05"
  }
]
```

Все мутации через API пишутся с `actor: "api"`.

---

## Полный тестовый сценарий (copy-paste)

Подставьте свой токен и URL. Предполагается пустая БД и права root на хосте.

```bash
export BASE_URL="http://127.0.0.1:8090"
export API_TOKEN="your-secret-at-least-16-chars"

# 1. Health
curl -s -H "Authorization: Bearer ${API_TOKEN}" "${BASE_URL}/api/v1/health" | jq .

# 2. Destination
curl -s -X POST -H "Authorization: Bearer ${API_TOKEN}" -H "Content-Type: application/json" \
  "${BASE_URL}/api/v1/destinations" \
  -d '{"alias":"test-db","host":"10.0.0.5","port":5432,"comment":"test"}' | jq .
# Запомните id из ответа, например DEST_ID=1

# 3. User
curl -s -X POST -H "Authorization: Bearer ${API_TOKEN}" -H "Content-Type: application/json" \
  "${BASE_URL}/api/v1/users" \
  -d '{"username":"tunnel-test","comment":"API test","tunnel_only":true,"destination_ids":[1]}' | jq .
# USER_ID=1

# 4. Key
curl -s -X POST -H "Authorization: Bearer ${API_TOKEN}" -H "Content-Type: application/json" \
  "${BASE_URL}/api/v1/users/1/keys" \
  -d '{"name":"test-key","public_key":"ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleKeyMaterialForDocsOnly9xQ test@example.com"}' | jq .

# 5. Detail
curl -s -H "Authorization: Bearer ${API_TOKEN}" "${BASE_URL}/api/v1/users/1" | jq .

# 6. Audit
curl -s -H "Authorization: Bearer ${API_TOKEN}" "${BASE_URL}/api/v1/audit?limit=5" | jq .
```

---

## Ошибки авторизации

**Без заголовка:**

```bash
curl -s "${BASE_URL}/api/v1/health"
```

→ `401` `{"detail":"Invalid or missing API token..."}`

**Неверный токен:**

```bash
curl -s -H "Authorization: Bearer wrong-token" "${BASE_URL}/api/v1/health"
```

→ `401`

---

## Readonly mode

При `READONLY_MODE=true` все `POST`, `PATCH`, `DELETE` возвращают `403`. `GET` работает.

```bash
curl -s -X POST -H "Authorization: Bearer ${API_TOKEN}" \
  -H "Content-Type: application/json" \
  "${BASE_URL}/api/v1/destinations" \
  -d '{"alias":"x","host":"1.2.3.4","port":22}'
```

→ `403` `{"detail":"Readonly mode is enabled."}`

---

## Сводная таблица эндпоинтов

| Метод | Путь | Действие |
|-------|------|----------|
| GET | `/api/v1/health` | Статус агента |
| GET | `/api/v1/destinations` | Список destinations |
| POST | `/api/v1/destinations` | Создать destination |
| GET | `/api/v1/destinations/{id}` | Получить destination |
| PATCH | `/api/v1/destinations/{id}` | Изменить destination |
| DELETE | `/api/v1/destinations/{id}` | Удалить destination |
| GET | `/api/v1/users` | Список tunnel users |
| POST | `/api/v1/users` | Создать user + Linux + provision |
| GET | `/api/v1/users/{id}` | User + keys + destinations |
| PATCH | `/api/v1/users/{id}` | Обновить user + provision |
| DELETE | `/api/v1/users/{id}` | Удалить user |
| POST | `/api/v1/users/{id}/regenerate` | Пересобрать файлы |
| GET | `/api/v1/users/{id}/keys` | Список ключей |
| POST | `/api/v1/users/{id}/keys` | Добавить ключ |
| PATCH | `/api/v1/keys/{id}` | Вкл/выкл ключ |
| DELETE | `/api/v1/keys/{id}` | Удалить ключ |
| GET | `/api/v1/audit?limit=N` | Журнал аудита |
