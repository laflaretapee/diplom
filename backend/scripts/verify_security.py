from __future__ import annotations

import http.cookiejar
import json
import sys
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:8000/api/v1"
ADMIN_EMAIL = "admin@japonica.example.com"
ADMIN_PASSWORD = "Admin1234!"


def _opener() -> urllib.request.OpenerDirector:
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def _cookie_value(opener: urllib.request.OpenerDirector, name: str) -> str | None:
    for handler in opener.handlers:
        if isinstance(handler, urllib.request.HTTPCookieProcessor):
            for cookie in handler.cookiejar:
                if cookie.name == name:
                    return cookie.value
    return None


def _request(
    opener: urllib.request.OpenerDirector,
    method: str,
    url: str,
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
):
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    if payload is not None:
        request.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    return opener.open(request)


def _load_json(response):
    return json.loads(response.read().decode())


def main() -> None:
    opener = _opener()

    login_response = _request(
        opener,
        "POST",
        f"{BASE_URL}/auth/login",
        {
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD,
        },
        headers={"Origin": "http://localhost:5173", "X-Forwarded-For": "10.20.30.40"},
    )
    login_payload = _load_json(login_response)
    assert login_payload["access_token"]
    set_cookie_headers = login_response.headers.get_all("Set-Cookie", [])
    joined_cookies = " ".join(set_cookie_headers)
    assert "refresh_token=" in joined_cookies
    assert "HttpOnly" in joined_cookies
    assert "SameSite=lax" in joined_cookies or "SameSite=Lax" in joined_cookies
    assert "csrf_token=" in joined_cookies

    csrf_token = _cookie_value(opener, "csrf_token")
    assert csrf_token, "csrf_token cookie was not set"

    try:
        _request(
            opener,
            "POST",
            f"{BASE_URL}/auth/refresh",
            headers={"X-Forwarded-For": "10.20.30.40"},
        )
        raise AssertionError("refresh without CSRF header must fail")
    except urllib.error.HTTPError as exc:
        assert exc.code == 403, exc.code

    refresh_response = _request(
        opener,
        "POST",
        f"{BASE_URL}/auth/refresh",
        headers={
            "X-CSRF-Token": csrf_token,
            "X-Forwarded-For": "10.20.30.40",
        },
    )
    refresh_payload = _load_json(refresh_response)
    assert refresh_payload["access_token"]

    preflight_allowed = _request(
        opener,
        "OPTIONS",
        f"{BASE_URL}/auth/login",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert (
        preflight_allowed.headers.get("Access-Control-Allow-Origin")
        == "http://localhost:5173"
    )

    try:
        _request(
            opener,
            "OPTIONS",
            f"{BASE_URL}/auth/login",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        raise AssertionError("disallowed origin preflight should not pass")
    except urllib.error.HTTPError as exc:
        assert exc.code in {400, 403}, exc.code

    rl_opener = _opener()
    last_error = None
    for _ in range(6):
        try:
            _request(
                rl_opener,
                "POST",
                f"{BASE_URL}/auth/login",
                {
                    "email": ADMIN_EMAIL,
                    "password": ADMIN_PASSWORD,
                },
                headers={"X-Forwarded-For": "55.66.77.88"},
            )
        except urllib.error.HTTPError as exc:
            last_error = exc
            break
    assert last_error is not None, "rate limit did not trigger"
    assert last_error.code == 429, last_error.code

    print("PASS: rate limiting, cookie flags, CSRF and CORS policy are active")


if __name__ == "__main__":
    main()
