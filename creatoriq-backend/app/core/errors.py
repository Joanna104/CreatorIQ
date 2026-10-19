"""One error format for the whole API, and the global exception handlers.

Every error response has this shape::

    {"error": {"code": "...", "message": "...", "fields": [...], "request_id": "..."}}

``fields`` appears only for validation errors. Internal details (stack traces, exception
text, connection strings, request input values) are never put in a response; they go to the
server log instead.
"""

from __future__ import annotations

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

_HTTP_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    422: "unprocessable_entity",
    429: "too_many_requests",
}


class FieldError(BaseModel):
    field: str
    message: str
    type: str


class ErrorBody(BaseModel):
    code: str
    message: str
    fields: list[FieldError] | None = None
    request_id: str | None = None


class ErrorResponse(BaseModel):
    """Documented in OpenAPI for endpoints that can fail."""

    error: ErrorBody


class AppError(Exception):
    """Raise this for expected, client-meaningful failures."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 500,
        code: str = "internal_error",
        fields: list[dict[str, str]] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.fields = fields
        self.headers = headers


def get_request_id(request: Request) -> str | None:
    return request.scope.get("state", {}).get("request_id")


def error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    fields: list[dict[str, str]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {"code": code, "message": message}
    if fields:
        body["fields"] = fields
    response_headers = dict(headers or {})
    request_id = get_request_id(request)
    if request_id:
        body["request_id"] = request_id
        response_headers["X-Request-ID"] = request_id
    return JSONResponse(
        status_code=status_code, content={"error": body}, headers=response_headers or None
    )


async def _handle_app_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    return error_response(
        request,
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        fields=exc.fields,
        headers=exc.headers,
    )


async def _handle_http_exception(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    try:
        message = HTTPStatus(exc.status_code).phrase
    except ValueError:
        message = "Error"
    return error_response(
        request,
        status_code=exc.status_code,
        code=_HTTP_CODES.get(exc.status_code, "http_error"),
        message=message,
        headers=dict(exc.headers) if exc.headers else None,
    )


async def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    # Only location, message and type are returned - never the submitted input value.
    fields = [
        {
            "field": ".".join(str(part) for part in err["loc"]),
            "message": str(err["msg"]),
            "type": str(err["type"]),
        }
        for err in exc.errors()
    ]
    return error_response(
        request,
        status_code=422,
        code="validation_error",
        message="Request validation failed.",
        fields=fields,
    )


async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled exception (request_id=%s) on %s %s",
        get_request_id(request),
        request.method,
        request.url.path,
        exc_info=exc,
    )
    return error_response(
        request,
        status_code=500,
        code="internal_error",
        message="An unexpected error occurred.",
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(Exception, _handle_unexpected_error)
