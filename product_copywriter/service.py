"""OpenAI-compatible chat completions client and deterministic demo mode."""
from __future__ import annotations
import json
import math
import os
import socket
import time
import urllib.parse
import urllib.error
import urllib.request
from .models import validate_product, validate_output, deterministic_specs
from .prompts import SYSTEM_PROMPT, user_prompt

RETRYABLE = {429, 500, 502, 503, 504}

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def _open_request(request, timeout):
    return urllib.request.build_opener(_NoRedirect()).open(request, timeout=timeout)

def _endpoint() -> str:
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    parsed = urllib.parse.urlparse(base)
    local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if not parsed.hostname or (parsed.scheme != "https" and not (parsed.scheme == "http" and local)):
        raise RuntimeError("OPENAI_BASE_URL должен использовать HTTPS (HTTP допускается только для localhost).")
    return base + "/chat/completions"

def _call_api(product: dict, correction: str = "") -> dict:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("Не задан OPENAI_API_KEY.")
    payload = {"model": os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"), "temperature": 0.6,
               "response_format": {"type": "json_object"}, "messages": [
                   {"role": "system", "content": SYSTEM_PROMPT},
                   {"role": "user", "content": user_prompt(product, correction)}]}
    try:
        timeout = float(os.environ.get("OPENAI_TIMEOUT", "30"))
    except ValueError:
        raise RuntimeError("OPENAI_TIMEOUT должен быть положительным числом.") from None
    if not math.isfinite(timeout) or timeout <= 0:
        raise RuntimeError("OPENAI_TIMEOUT должен быть положительным числом.")
    request = urllib.request.Request(_endpoint(), data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"}, method="POST")
    for attempt in range(3):
        try:
            with _open_request(request, timeout=timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
            content = body["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ValueError("API вернул пустой ответ.")
            result = json.loads(content)
            if not isinstance(result, dict):
                raise ValueError("Ответ модели не является JSON-объектом.")
            return result
        except urllib.error.HTTPError as exc:
            if exc.code in RETRYABLE and attempt < 2:
                time.sleep(0.5 * (2 ** attempt)); continue
            raise RuntimeError(f"API вернул ошибку HTTP {exc.code}.") from None
        except (TimeoutError, socket.timeout):
            raise RuntimeError("Истекло время ожидания ответа API.") from None
        except urllib.error.URLError:
            raise RuntimeError("Не удалось подключиться к API.") from None
        except (KeyError, IndexError, json.JSONDecodeError, UnicodeDecodeError):
            raise ValueError("API вернул ответ в неподдерживаемом формате.") from None
        except (TypeError, AttributeError):
            raise ValueError("API вернул ответ в неподдерживаемом формате.") from None
    raise RuntimeError("API временно недоступен.")

def generate(product: dict, *, demo: bool = False) -> dict:
    normalized = validate_product(product)
    if demo:
        return generate_demo(normalized)
    # Validate timeout and endpoint before entering the structural correction loop.
    _endpoint()
    try:
        configured_timeout = float(os.environ.get("OPENAI_TIMEOUT", "30"))
    except ValueError:
        raise RuntimeError("OPENAI_TIMEOUT должен быть положительным числом.") from None
    if not math.isfinite(configured_timeout) or configured_timeout <= 0:
        raise RuntimeError("OPENAI_TIMEOUT должен быть положительным числом.")
    error = ""
    for attempt in range(2):
        try:
            return validate_output(_call_api(normalized, error), normalized)
        except ValueError as exc:
            if attempt:
                raise RuntimeError("Модель не смогла подготовить корректный ответ: " + str(exc)) from None
            error = str(exc)
    raise RuntimeError("Не удалось создать карточку.")

def generate_demo(product: dict) -> dict:
    """Deterministic illustrative copy; explicitly labeled as non-LLM output."""
    p = validate_product(product)
    title = p["name"][:70]
    facts = "; ".join(f"{k}: {v}" for k, v in p["specs"].items()) or "технические характеристики пока не указаны"
    maker = f" Производитель: {p['manufacturer']}." if p["manufacturer"] else " Производитель не указан в исходных данных."
    source = p["description"].strip()
    if source and source[-1] not in ".!?…":
        source += "."
    sentences = [f"{p['name']}.{(' ' + source) if source else ''}{maker}",
        f"В исходных данных приведены характеристики: {facts}.",
        "Перед закупкой сопоставьте сведения в карточке с требованиями к приобретаемому прибору.",
        "Если нужного параметра нет, запросите его у поставщика и сверьте ответ с документацией производителя.",
        "Уточните назначение, рабочие задачи и необходимые характеристики для выбора подходящей модели.",
        "Проверьте, что описание и переданные характеристики относятся к одной и той же версии товара.",
        "При сравнении предложений используйте только подтверждённые параметры, а неизвестные значения уточняйте отдельно.",
        "Карточка составлена по предоставленным сведениям и не заменяет официальную техническую документацию.",
        "Если для принятия решения нужны дополнительные данные, запросите актуальное описание у продавца.",
        "Так вы сможете оценить соответствие товара своим требованиям до оформления заказа.",
        "Для закупки заранее подготовьте список обязательных требований и сравните с ним сведения, которые продавец подтвердит по документации.",
        "Проверяйте каждое значение отдельно и уточняйте неполные данные до принятия решения."]
    desc = ""
    for sentence in sentences:
        candidate = (desc + " " + sentence).strip()
        if len(candidate) <= 1200:
            desc = candidate
        if len(desc) >= 800:
            break
    specs, missing = deterministic_specs(p)
    return {"seo_title": title, "description": desc, "specs": specs,
            "queries": [p["name"], f"купить {p['name']}", f"{p['name']} для предприятия"],
            "commercial_block": (f"Кому подходит: специалистам по закупке и подбору приборов. Задачи по исходному описанию: {source}" if source
                else "Кому подходит: специалистам по закупке и подбору приборов. Задачи применения: данных нет; уточните назначение и требования у поставщика перед закупкой."),
            "missing_fields": missing, "mode": "DEMO — не LLM"}
