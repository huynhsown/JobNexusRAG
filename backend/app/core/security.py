from __future__ import annotations

import hmac
from collections.abc import Iterable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class APIKeyMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        enabled: bool,
        api_keys: set[str],
        header_name: str,
        protected_prefixes: tuple[str, ...],
        excluded_prefixes: tuple[str, ...],
    ) -> None:
        super().__init__(app)
        self.enabled = enabled
        self.api_keys = api_keys
        self.header_name = header_name
        self.protected_prefixes = protected_prefixes
        self.excluded_prefixes = excluded_prefixes

    @staticmethod
    def _starts_with_any(path: str, prefixes: tuple[str, ...]) -> bool:
        return any(path.startswith(prefix) for prefix in prefixes)

    def _is_valid_key(self, provided: str | None) -> bool:
        if not provided:
            return False
        return any(hmac.compare_digest(provided, key) for key in self.api_keys)

    async def dispatch(self, request: Request, call_next):
        if not self.enabled or not self.api_keys:
            return await call_next(request)

        path = request.url.path
        if self._starts_with_any(path, self.excluded_prefixes):
            return await call_next(request)
        if not self._starts_with_any(path, self.protected_prefixes):
            return await call_next(request)

        provided = request.headers.get(self.header_name) or request.query_params.get("api_key")
        if not self._is_valid_key(provided):
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key"})
        return await call_next(request)


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _normalize_prefixes(prefixes: Iterable[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for prefix in prefixes:
        if not prefix:
            continue
        p = prefix.strip()
        if not p:
            continue
        if not p.startswith("/"):
            p = "/" + p
        normalized.append(p)
    return tuple(dict.fromkeys(normalized))


def install_api_key_middleware(app: FastAPI, settings, logger) -> None:
    api_keys = set(_split_csv(getattr(settings, "API_KEYS", "")))
    enabled = bool(getattr(settings, "API_KEY_ENABLED", False))
    header_name = str(getattr(settings, "API_KEY_HEADER", "X-API-Key"))

    protected_prefixes = _normalize_prefixes(
        _split_csv(getattr(settings, "API_KEY_PROTECTED_PREFIXES", "/api/")) or ["/api/"]
    )
    excluded_prefixes = _normalize_prefixes(
        _split_csv(
            getattr(
                settings,
                "API_KEY_EXCLUDED_PREFIXES",
                "/health,/ready,/docs,/redoc,/openapi.json,/static/",
            )
        )
        or ["/health", "/ready", "/docs", "/redoc", "/openapi.json", "/static/"]
    )

    app.add_middleware(
        APIKeyMiddleware,
        enabled=enabled,
        api_keys=api_keys,
        header_name=header_name,
        protected_prefixes=protected_prefixes,
        excluded_prefixes=excluded_prefixes,
    )

    if enabled and not api_keys:
        logger.warning("API key auth is enabled but API_KEYS is empty. All protected routes will return 401.")
    elif enabled:
        logger.info("API key auth enabled for prefixes %s", protected_prefixes)
    else:
        logger.info("API key auth disabled")
