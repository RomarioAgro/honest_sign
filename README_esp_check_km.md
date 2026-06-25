# esp_check_km.py

`esp_check_km.py` проверяет коды маркировки через ESP / TCPIoT API v3 и
сохраняет совместимость с обычным `CheckKM`: на вход принимает тот же словарь,
а наружу возвращает кортеж `(status_code, req_id, req_timestamp)`.

## Когда используется

В проекте `cheque` выбор проверяющего класса задается в `D:\PythonProject\cheque\.env`:

```env
tcpiot=true
```

При `tcpiot=true` импортируется:

```python
honest_sign.esp_check_km.CheckKMEsp
```

При `tcpiot=false` используется старый вариант:

```python
honest_sign.check_km.CheckKM
```

## Конфигурация

Основной файл настроек лежит рядом с модулем:

```text
D:\PythonProject\honest_sign\esp_check_km.ini
```

Секции:

```ini
[esp]
protocol = https
host = 192.168.7.88
port = 51000
api_version = v3
timeout_connect = 30
timeout_read = 30
verify_ssl = false

[paths]
client_info = client-info.json
log_dir = d:\files\esp-logs
result_dir = d:\files\esp-logs

[logging]
level = DEBUG
log_payload = true
log_tokens = true

[client_info]
user_name =
tz =
default_pg =
```

`client_info` по умолчанию читается из:

```text
D:\PythonProject\honest_sign\client-info.json
```

Не храните реальные токены, ключи и пароли в README.

## Что отправляется

Метод `check_km_permission_mode()` отправляет POST-запрос:

```text
{protocol}://{host}:{port}/api/{api_version}/codes/check
```

Тело запроса:

```json
{
  "codes": [
    {"cis": "base64-code"}
  ],
  "client_info": {}
}
```

Коды маркировки перед отправкой приводятся к формату ESP: значение `cis`
кодируется в Base64. Если доступен helper `preparation_km`, он используется для
нормализации кода перед кодированием.

## Логи и результаты

На каждый созданный объект проверки пишется отдельный лог:

```text
esp_check_km_YYYY-MM-DD_HH-MM-SS.log
```

Папка задается параметром:

```ini
[paths]
log_dir = d:\files\esp-logs
```

Результаты проверки и ошибки сохраняются в `result_dir` с префиксом
`esp_check_km_`.

## Ошибки и остановка печати

Если ESP не вернул проверенные коды (`codes` пустой или отсутствует), проверка
считается неуспешной. Это касается:

- таймаута запроса;
- сетевых ошибок `requests`;
- HTTP-ответов не `200`;
- ответов ESP с кодами вроде `514` или `120`;
- ответа без JSON.

В этом случае показывается окно ошибки, в лог пишется причина, а метод
`pm_show_errors_honest_sign()` возвращает ненулевой статус. В `check.py` это
останавливает печать через существующий путь `exit(98)`.

## Ручной запуск

Можно проверить модуль отдельно:

```powershell
python D:\PythonProject\honest_sign\esp_check_km.py D:\path\to\km.json
```

Или с явным конфигом:

```powershell
python D:\PythonProject\honest_sign\esp_check_km.py D:\path\to\km.json D:\PythonProject\honest_sign\esp_check_km.ini
```

Минимальный пример входного JSON:

```json
{
  "names": ["Товар"],
  "km": ["raw-marking-code"],
  "operation": "sale",
  "fn": "optional-fn",
  "rec_name": "test"
}
```

## Быстрая проверка синтаксиса

```powershell
.\.venv\Scripts\python.exe -m py_compile D:\PythonProject\honest_sign\esp_check_km.py
```
