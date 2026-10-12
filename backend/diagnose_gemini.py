"""One-shot Gemini connectivity diagnostic; never prints credentials or response text."""

from __future__ import annotations

import json
import socket
import time
import urllib.error

import main

TIMEOUT_SECONDS = 15


def category_for_status(status: int) -> str:
    if status == 404:
        return "invalid_model_or_endpoint"
    if status in (401, 403):
        return "authentication_failure"
    if status == 429:
        return "quota_or_rate_limit"
    if 500 <= status <= 599:
        return "provider_5xx"
    return "http_rejection"


def main_cli() -> int:
    api_key = main.get_secret("GEMINI_API_KEY")
    model = main.get_gemini_model()
    if not api_key:
        print("result=FAIL;category=not_configured")
        return 2

    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = json.dumps({
        "contents": [{"parts": [{"text": "Reply with the single word OK."}]}],
        "generationConfig": {
            "thinkingConfig": {"thinkingLevel": "low"},
            "maxOutputTokens": 16,
        },
    }).encode("utf-8")
    started = time.monotonic()
    try:
        response = main.external_json(
            endpoint,
            {"Content-Type": "application/json", "x-goog-api-key": api_key},
            payload,
            timeout=TIMEOUT_SECONDS,
        )
    except urllib.error.HTTPError as error:
        category = category_for_status(error.code)
        print(f"result=FAIL;category={category};http_status={error.code};model={model};elapsed_seconds={time.monotonic() - started:.1f}")
        error.close()
        return 1
    except urllib.error.URLError as error:
        reason = error.reason
        if isinstance(reason, (TimeoutError, socket.timeout)):
            category = "network_timeout"
        elif isinstance(reason, socket.gaierror):
            category = "dns_failure"
        else:
            category = "network_connectivity_failure"
        print(f"result=FAIL;category={category};reason_type={type(reason).__name__};model={model};elapsed_seconds={time.monotonic() - started:.1f}")
        return 1
    except (TimeoutError, socket.timeout):
        print(f"result=FAIL;category=network_timeout;model={model};elapsed_seconds={time.monotonic() - started:.1f}")
        return 1
    except json.JSONDecodeError:
        print(f"result=FAIL;category=malformed_json;model={model};elapsed_seconds={time.monotonic() - started:.1f}")
        return 1
    except Exception as error:
        print(f"result=FAIL;category=diagnostic_error;error_type={type(error).__name__};model={model};elapsed_seconds={time.monotonic() - started:.1f}")
        return 1

    try:
        text = response["candidates"][0]["content"]["parts"][0]["text"]
        if not isinstance(text, str) or not text.strip():
            raise ValueError("empty response")
    except (KeyError, IndexError, TypeError, ValueError):
        print(f"result=FAIL;category=malformed_response;http_status=200;model={model};elapsed_seconds={time.monotonic() - started:.1f}")
        return 1

    print(f"result=PASS;category=success;http_status=200;model={model};elapsed_seconds={time.monotonic() - started:.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main_cli())
