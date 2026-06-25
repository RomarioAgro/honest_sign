"""ESP / TCPIoT marking-code checker.

The module provides CheckKMEsp, a compatibility-oriented checker that mirrors
CheckKM's external flow, but sends requests to ESP / TCPIoT API v3 instead of
calling True API CDN endpoints directly.
"""

from __future__ import annotations

import base64
import configparser
import datetime as dt
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
if __package__:
    from .check_km import show_error_message
else:
    from check_km import show_error_message
import requests

try:
    from shtrih.preparation_km_to_honest_sign import preparation_km as km_with_gs
except Exception:  # pragma: no cover - optional project dependency
    km_with_gs = None


DEFAULT_CONFIG_NAME = "esp_check_km.ini"


class EspConfigError(RuntimeError):
    """Raised when ESP checker configuration cannot be loaded."""


class CheckKMEsp:
    """Check marking codes through ESP / TCPIoT with CheckKM-like behavior.

    Expected input dictionary is intentionally compatible with the existing
    CheckKM class:

    {
        "names": ["product name"],
        "km": ["raw marking code"],
        "operation": "sale" | "return_sale" | "status",
        "fn": "optional fiscal drive serial",
        "rec_name": "optional output name",
        "inn": "optional inn"
    }
    """

    def __init__(self, i_dict_km: Dict[str, Any] | None = None, config_path: str | os.PathLike[str] | None = None) -> None:
        i_dict_km = i_dict_km or {}
        self.project_dir = Path(__file__).resolve().parent
        self.config_path = self._resolve_path(config_path or DEFAULT_CONFIG_NAME)
        self.config = self._load_config(self.config_path)
        self.logger = self._setup_logger()

        self.names = i_dict_km.get("names", "names not found")
        if isinstance(self.names, str):
            self.names = [self.names] * len(i_dict_km.get("km", []))
        self.raw_km = i_dict_km.get("km", [])
        self.km = preparation_km(self.raw_km, default_pg=self._get_optional_int("client_info", "default_pg"))
        self.operation = i_dict_km.get("operation", "sale")
        self.fn = i_dict_km.get("fn", None)
        self.file_name = i_dict_km.get("rec_name", "status")
        self.inn = i_dict_km.get("inn", None)

        self.client_info = self._load_client_info()
        self.answer: Optional[Dict[str, Any]] = None
        self.raw_answer: Optional[Dict[str, Any]] = None
        self.status_code: Optional[int] = None
        self.status_requests: Optional[int] = None
        self.last_error: Optional[str] = None

        self.logger.debug("CheckKMEsp initialized: operation=%s, codes=%s", self.operation, len(self.km))

    def check_km_permission_mode(self) -> bool:
        """Send codes to ESP / TCPIoT and normalize response to CheckKM shape."""
        payload = {
            "codes": self.km,
            "client_info": self.client_info,
        }
        url = self._build_url("codes/check")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        timeout = (
            self.config.getfloat("esp", "timeout_connect", fallback=2.0),
            self.config.getfloat("esp", "timeout_read", fallback=2.0),
        )
        verify_ssl = self.config.getboolean("esp", "verify_ssl", fallback=True)

        self._log_payload("ESP request", {"url": url, "headers": headers, "payload": payload})
        started = dt.datetime.now(dt.timezone.utc)
        try:
            response = requests.post(url=url, headers=headers, json=payload, timeout=timeout, verify=verify_ssl)
        except requests.Timeout as exc:
            self.status_code = 1
            self.last_error = f"ESP request timeout: {exc}"
            self.logger.exception(self.last_error)
            self.answer = self._make_error_answer(self.last_error)
            return False
        except requests.RequestException as exc:
            self.status_code = 1
            self.last_error = f"ESP request error: {exc}"
            self.logger.exception(self.last_error)
            self.answer = self._make_error_answer(self.last_error)
            return False

        elapsed_ms = int((dt.datetime.now(dt.timezone.utc) - started).total_seconds() * 1000)
        self.status_requests = response.status_code
        self.logger.debug("ESP response status=%s elapsed_ms=%s", response.status_code, elapsed_ms)
        self.logger.debug("ESP response text=%s", response.text)

        try:
            data = response.json()
        except ValueError as exc:
            self.status_code = 1
            self.last_error = f"ESP returned non-JSON response: {exc}"
            self.logger.exception(self.last_error)
            self.answer = self._make_error_answer(self.last_error)
            return False

        self.raw_answer = data
        self._log_payload("ESP response json", data)

        if response.status_code != 200:
            self.status_code = 1
            self.last_error = f"ESP HTTP status {response.status_code}"
            self.answer = self._normalize_response(data, fallback_error=self.last_error)
            return False

        self.answer = self._normalize_response(data)
        self.status_code = 0 if self.answer.get("codes") else 1
        return True

    def get_info(self) -> Optional[Dict[str, Any]]:
        """Call ESP / TCPIoT info endpoint and return parsed JSON."""
        url = self._build_url("info")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        timeout = (
            self.config.getfloat("esp", "timeout_connect", fallback=2.0),
            self.config.getfloat("esp", "timeout_read", fallback=2.0),
        )
        verify_ssl = self.config.getboolean("esp", "verify_ssl", fallback=True)
        self.logger.debug("ESP info request url=%s", url)
        try:
            response = requests.get(url=url, headers=headers, timeout=timeout, verify=verify_ssl)
            self.logger.debug("ESP info status=%s text=%s", response.status_code, response.text)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            self.logger.exception("ESP info request failed: %s", exc)
            return None

    def pm_show_errors_honest_sign(self) -> Tuple[int, str, Any]:
        """Parse normalized answer and return the same tuple as CheckKM.

        Unlike the legacy implementation, this method does not open a Tkinter
        window. It writes messages to result files and logs, which is safer for
        test contour and non-GUI environments.
        """
        data = self.answer
        errors: List[str] = []
        f_name = f"{self.file_name}_goods_km.txt"
        self.logger.debug("Start parsing normalized ESP response")

        if not data:
            self.status_code = 1
            data = self._make_error_answer("No ESP response")
            self.answer = data
            errors.append("Не удалось получить успешный ответ от ESP / ТС ПИоТ\n ни один КМ не проверен")
        elif not data.get("codes"):
            self.status_code = 1
            description = data.get("description") or self.last_error or "ESP / ТС ПИоТ не вернул проверенные КМ"
            error_code = data.get("code") or self.status_requests or ("timeout" if "timeout" in description.lower() else "unknown")
            errors.append(
                f"Ошибка связи с ESP / ТС ПИоТ\n"
                f"Код: {error_code}\n"
                f"{description}\n"
                "Печать чека прервана"
            )
        else:
            for code_info, name in zip(data.get("codes", []), self.names):
                exp_date_str = code_info.get("expireDate", None)
                if exp_date_str and _is_expired(exp_date_str):
                    self.status_code = 1
                    errors.append(f"{name}\n{code_info.get('cis', '')}\n истек срок годности товара")
                if not code_info.get("found", True):
                    self.status_code = 1
                    errors.append(f"{name}\n{code_info.get('cis', '')}\n не найден в ЧЗ")
                if not code_info.get("utilised", True):
                    self.status_code = 1
                    errors.append(f"{name}\n{code_info.get('cis', '')}\n в ЧЗ нет информации о нанесении кода")
                if not code_info.get("verified", True):
                    self.status_code = 1
                    errors.append(
                        f"{name}\n{code_info.get('cis', '')}\n не подтвержден, надо найти товар с этим кодом, обнулить его,\n"
                        "переключить раскладку на АНГЛИЙСКИЙ язык, заново сканировать товар"
                    )
                if code_info.get("sold", False) and self.operation == "sale":
                    self.status_code = 1
                    errors.append(f"{name}\n{code_info.get('cis', '')}\n продан, выбыл из оборота")
                if not code_info.get("sold", False) and self.operation == "return_sale":
                    self.status_code = 1
                    errors.append(f"{name}\n{code_info.get('cis', '')}\n не продан, не выбывал из оборота")
                if self.operation == "status":
                    if code_info.get("sold", False):
                        self.status_code = 0
                        errors.append(
                            f"{name}\n{code_info.get('cis', '')}\n продан, выбыл из оборота, это значит ДЛЯ ПРОДАЖИ НЕ ПОДХОДИТ"
                        )
                    else:
                        self.status_code = 2
                        errors.append(
                            f"{name}\n{code_info.get('cis', '')}\n не продан, не выбывал из оборота, это значит ДЛЯ ПРОДАЖИ ПОДХОДИТ"
                        )
                if code_info.get("isBlocked", False):
                    self.status_code = 1
                    errors.append(
                        f"{name}\n{code_info.get('cis', '')}\n заблокирован по решению {code_info.get('ogvs', 'ХыЗы кого')}"
                    )
                if not code_info.get("realizable", True) and not code_info.get("sold", True):
                    self.status_code = 1
                    errors.append(f"{name}\n{code_info.get('cis', '')}\n нет информации о вводе кода в оборот")
                if not code_info.get("isOwner", True):
                    self.status_code = 1
                    errors.append(
                        f"{name}\n{code_info.get('cis', '')}\n ваш ИНН и ИНН владельца кода не совпадают\n"
                        "это значит, что КМ не принадлежит организации вашего магазина\nТОРГОВАТЬ ИМ ВЫ НЕ ИМЕЕТЕ ПРАВА"
                    )

        if errors:
            f_name = f"{self.file_name}_errors_km.txt"
            show_error_message(errors)
        else:
            self.status_code = 0
            errors.append(f"{data.get('reqId', 'unknown')};{data.get('reqTimestamp', 0)}")

        self._save_events_to_file(errors, name=f_name)
        req_id = str(data.get("reqId", "unknown"))
        req_ts = data.get("reqTimestamp", 0)
        return int(self.status_code or 0), req_id, req_ts

    def _load_config(self, path: Path) -> configparser.ConfigParser:
        if not path.exists():
            raise EspConfigError(f"Config file not found: {path}")
        parser = configparser.ConfigParser()
        parser.read(path, encoding="utf-8")
        return parser

    def _setup_logger(self) -> logging.Logger:
        log_dir = self._resolve_path(self.config.get("paths", "log_dir", fallback="logs"))
        log_dir.mkdir(parents=True, exist_ok=True)
        level_name = self.config.get("logging", "level", fallback="DEBUG").upper()
        level = getattr(logging, level_name, logging.DEBUG)
        logger = logging.getLogger(f"{__name__}.{id(self)}")
        logger.setLevel(level)
        logger.propagate = False
        request_time = dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_file = log_dir / f"esp_check_km_{request_time}.log"
        handler = logging.FileHandler(log_file, encoding="utf-8")
        handler.setLevel(level)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(filename)s - %(funcName)s:%(lineno)d - %(levelname)s - %(message)s",
            datefmt="%H:%M:%S",
        ))
        logger.handlers.clear()
        logger.addHandler(handler)
        return logger

    def _load_client_info(self) -> Dict[str, Any]:
        client_info_path = self._resolve_path(self.config.get("paths", "client_info", fallback="client-info.json"))
        raw = client_info_path.read_text(encoding="utf-8-sig").strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # The current example file is a JSON fragment: "client_info": {...}
            data = json.loads("{" + raw.strip().rstrip(",") + "}")
        client_info = data.get("client_info", data)
        if not isinstance(client_info, dict):
            raise EspConfigError(f"client_info must be an object in {client_info_path}")
        user_name = self.config.get("client_info", "user_name", fallback="").strip()
        if user_name:
            client_info["user_name"] = user_name
        tz = self._get_optional_int("client_info", "tz")
        if tz is not None:
            client_info["tz"] = tz
        self._log_payload("Loaded client_info", client_info)
        return client_info

    def _build_url(self, method: str) -> str:
        protocol = self.config.get("esp", "protocol", fallback="https").strip().rstrip(":/")
        host = self.config.get("esp", "host", fallback="tspiot.sandbox.crptech.ru").strip().strip("/")
        port = self.config.get("esp", "port", fallback="").strip()
        api_version = self.config.get("esp", "api_version", fallback="v3").strip().strip("/")
        netloc = f"{host}:{port}" if port else host
        return f"{protocol}://{netloc}/api/{api_version}/{method.strip('/')}"

    def _normalize_response(self, data: Dict[str, Any], fallback_error: str | None = None) -> Dict[str, Any]:
        item: Dict[str, Any]
        codes_response = data.get("codesResponse")
        if isinstance(codes_response, dict):
            nested = codes_response.get("codesResponse")
            if isinstance(nested, list) and nested:
                item = nested[0]
            else:
                item = codes_response
        elif isinstance(codes_response, list) and codes_response:
            item = codes_response[0]
        else:
            item = data

        req_id = item.get("reqId") or data.get("reqId") or fallback_error or "unknown"
        req_timestamp = item.get("reqTimestamp") or data.get("reqTimestamp") or int(dt.datetime.now().timestamp() * 1000)
        codes = item.get("codes") or data.get("codes") or []
        normalized = {
            "reqId": req_id,
            "reqTimestamp": req_timestamp,
            "codes": codes,
        }
        for key in ("code", "description", "isCheckedOffline", "version", "inst"):
            if key in item:
                normalized[key] = item[key]
        self.logger.debug("Normalized ESP response=%s", json.dumps(normalized, ensure_ascii=False))
        return normalized

    def _make_error_answer(self, message: str) -> Dict[str, Any]:
        return {
            "reqId": message,
            "reqTimestamp": int(dt.datetime.now().timestamp() * 1000),
            "codes": [],
            "description": message,
        }

    def _save_events_to_file(self, events: Iterable[str], name: str) -> None:
        result_dir = self._resolve_path(self.config.get("paths", "result_dir", fallback=self.config.get("paths", "log_dir", fallback="logs")))
        result_dir.mkdir(parents=True, exist_ok=True)
        filename = result_dir / f"esp_check_km_{name}"
        with filename.open("a", encoding="utf-8") as file:
            for event in events:
                file.write(str(event) + "\n")
        self.logger.debug("Saved events to %s", filename)

    def _resolve_path(self, path_value: str | os.PathLike[str]) -> Path:
        path = Path(path_value)
        if path.is_absolute():
            return path
        return self.project_dir / path

    def _get_optional_int(self, section: str, option: str) -> Optional[int]:
        value = self.config.get(section, option, fallback="").strip()
        if not value:
            return None
        return int(value)

    def _log_payload(self, title: str, payload: Any) -> None:
        if not self.config.getboolean("logging", "log_payload", fallback=True):
            return
        prepared = payload
        if not self.config.getboolean("logging", "log_tokens", fallback=True):
            prepared = _redact_tokens(payload)
        self.logger.debug("%s: %s", title, json.dumps(prepared, ensure_ascii=False, default=str))


def preparation_km(in_km: List[str], default_pg: Optional[int] = None) -> List[Dict[str, Any]]:
    """Prepare marking codes for ESP API v3.

    ESP API v3 expects an array of objects: {"cis": "base64"}.
    If the optional project helper is available, it is used to cut/normalize the
    raw code in the same way as the legacy CheckKM implementation.
    """
    out: List[Dict[str, Any]] = []
    for elem in in_km:
        prepared = km_with_gs(in_km=elem) if km_with_gs else elem
        encoded = base64.b64encode(prepared.encode("utf-8")).decode("ascii")
        item: Dict[str, Any] = {"cis": encoded}
        if default_pg is not None:
            item["pg"] = default_pg
        out.append(item)
    return out


def make_dict_km(f_name: str) -> Dict[str, Any]:
    with open(f_name, "r", encoding="utf-8-sig") as rm_file:
        return json.load(rm_file)


def _is_expired(exp_date_str: str) -> bool:
    try:
        normalized = exp_date_str.replace("Z", "+00:00")
        exp_date = dt.datetime.fromisoformat(normalized)
        if exp_date.tzinfo is None:
            exp_date = exp_date.replace(tzinfo=dt.timezone.utc)
        return exp_date < dt.datetime.now(dt.timezone.utc)
    except ValueError:
        return False


def _redact_tokens(value: Any) -> Any:
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            if key.lower() in {"token", "pass", "password"}:
                redacted[key] = "<redacted>"
            else:
                redacted[key] = _redact_tokens(item)
        return redacted
    if isinstance(value, list):
        return [_redact_tokens(item) for item in value]
    return value


def main(argv: Optional[List[str]] = None) -> int:
    import sys

    argv = list(argv or sys.argv[1:])
    if not argv:
        print("Usage: python esp_check_km.py <km_json> [config_ini]")
        return 2
    km_file = argv[0]
    config_path = argv[1] if len(argv) > 1 else DEFAULT_CONFIG_NAME
    checker = CheckKMEsp(i_dict_km=make_dict_km(km_file), config_path=config_path)
    checker.check_km_permission_mode()
    result = checker.pm_show_errors_honest_sign()
    print(result)
    return result[0]


if __name__ == "__main__":
    raise SystemExit(main())
