import json
from typing import Any

from polychat.model.auth.parsed_auth_payload import ParsedAuthPayload


class AuthPayloadParser:
    @classmethod
    def parse(cls, content: str) -> ParsedAuthPayload:
        raw_content = (content or "").strip()
        if not raw_content:
            raise ValueError("Login payload mancante o vuoto")

        if cls._looks_like_json(raw_content):
            return cls._parse_json_payload(raw_content)

        if cls._looks_like_netscape(raw_content):
            return ParsedAuthPayload(
                cookies=cls._parse_netscape_payload(raw_content),
                raw_text=raw_content,
            )

        return ParsedAuthPayload(raw_text=raw_content)

    @staticmethod
    def _looks_like_json(content: str) -> bool:
        return content.startswith("{") or content.startswith("[") or content.startswith('"')

    @staticmethod
    def _looks_like_netscape(content: str) -> bool:
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        if not lines:
            return False
        if lines[0].startswith("# Netscape HTTP Cookie File"):
            return True
        return any(line.count("\t") >= 6 for line in lines if not line.startswith("#"))

    @classmethod
    def _parse_json_payload(cls, content: str) -> ParsedAuthPayload:
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError("Login payload JSON non valido") from exc

        if isinstance(parsed, list):
            return ParsedAuthPayload(
                cookies=[cls._normalize_cookie(cookie) for cookie in parsed],
                raw_json_value=parsed,
                raw_text=content,
            )

        if cls._is_cookie_mapping(parsed):
            return ParsedAuthPayload(
                cookies=[cls._normalize_cookie(parsed)],
                raw_json_value=parsed,
                raw_text=content,
            )

        return ParsedAuthPayload(
            raw_json_value=parsed,
            raw_text=content,
        )

    @staticmethod
    def _is_cookie_mapping(value: Any) -> bool:
        return isinstance(value, dict) and "name" in value and "value" in value

    @classmethod
    def _normalize_cookie(cls, cookie: Any) -> dict[str, Any]:
        if not isinstance(cookie, dict):
            raise ValueError("Cookie JSON non valido: atteso oggetto")

        name = str(cookie.get("name", "")).strip()
        value = str(cookie.get("value", ""))
        if not name:
            raise ValueError("Cookie JSON non valido: campo 'name' mancante")

        normalized: dict[str, Any] = {
            "name": name,
            "value": value,
            "domain": str(cookie.get("domain", "")).strip(),
            "path": str(cookie.get("path", "/") or "/"),
        }

        secure = cookie.get("secure")
        if isinstance(secure, bool):
            normalized["secure"] = secure

        http_only = cookie.get("httpOnly")
        if isinstance(http_only, bool):
            normalized["httpOnly"] = http_only

        same_site = cls._normalize_same_site(cookie.get("sameSite"))
        if same_site:
            normalized["sameSite"] = same_site

        expires = cookie.get("expirationDate", cookie.get("expires"))
        if expires not in (None, "", 0, "0"):
            normalized["expires"] = int(float(expires))

        return normalized

    @classmethod
    def _parse_netscape_payload(cls, content: str) -> list[dict[str, Any]]:
        cookies: list[dict[str, Any]] = []
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            parts = raw_line.split("\t")
            if len(parts) != 7:
                raise ValueError("Formato Netscape cookie non valido")

            domain, _include_subdomains, path, secure, expires, name, value = parts
            cookie: dict[str, Any] = {
                "name": name.strip(),
                "value": value.strip(),
                "domain": domain.strip(),
                "path": path.strip() or "/",
                "secure": secure.strip().upper() == "TRUE",
            }
            if expires.strip() not in {"", "0"}:
                cookie["expires"] = int(expires.strip())
            cookies.append(cookie)

        if not cookies:
            raise ValueError("Nessun cookie trovato nel payload Netscape")

        return cookies

    @staticmethod
    def _normalize_same_site(value: Any) -> str | None:
        if value is None:
            return None

        normalized = str(value).strip().lower()
        if normalized in {"none", "no_restriction"}:
            return "None"
        if normalized == "lax":
            return "Lax"
        if normalized == "strict":
            return "Strict"
        return None
