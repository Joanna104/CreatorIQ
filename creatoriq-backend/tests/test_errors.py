import logging

import pytest
from fastapi import HTTPException

from app.core.errors import AppError


def _add_routes(app):
    @app.get("/_t/boom")
    def boom():
        raise RuntimeError("internal detail password=hunter2")

    @app.get("/_t/validate")
    def validate(n: int):
        return {"n": n}

    @app.get("/_t/app-error")
    def app_error():
        raise AppError(
            "Name already taken.",
            status_code=409,
            code="conflict",
            fields=[{"field": "name", "message": "duplicate", "type": "conflict"}],
            headers={"X-Extra": "1"},
        )

    @app.get("/_t/http-error")
    def http_error():
        raise HTTPException(status_code=403, detail="private detail")


@pytest.fixture
def client(make_client, settings):
    return make_client(settings, extra_routes=_add_routes)


def _assert_envelope(response, status, code):
    assert response.status_code == status
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert list(body) == ["error"]
    error = body["error"]
    assert error["code"] == code
    assert isinstance(error["message"], str) and error["message"]
    # the id in the body matches the header, so a reported error can be traced in the logs
    assert error["request_id"] == response.headers["X-Request-ID"]
    return error


def test_unknown_route_returns_json_404(client):
    error = _assert_envelope(client.get("/nope"), 404, "not_found")
    assert error["message"] == "Not Found"
    assert "fields" not in error


def test_wrong_method_returns_405_and_keeps_allow_header(client):
    response = client.post("/health")
    _assert_envelope(response, 405, "method_not_allowed")
    assert "GET" in response.headers["allow"]


def test_validation_error_lists_fields_without_echoing_input(client):
    response = client.get("/_t/validate", params={"n": "SUBMITTED-VALUE"})
    error = _assert_envelope(response, 422, "validation_error")
    assert error["message"] == "Request validation failed."
    assert error["fields"][0]["field"] == "query.n"
    assert set(error["fields"][0]) == {"field", "message", "type"}
    assert "SUBMITTED-VALUE" not in response.text


def test_missing_required_parameter_is_a_validation_error(client):
    error = _assert_envelope(client.get("/_t/validate"), 422, "validation_error")
    assert error["fields"][0]["field"] == "query.n"


def test_http_exception_uses_the_envelope_and_hides_detail(client):
    response = client.get("/_t/http-error")
    error = _assert_envelope(response, 403, "forbidden")
    assert error["message"] == "Forbidden"
    assert "private detail" not in response.text


def test_app_error_carries_code_fields_and_headers(client):
    response = client.get("/_t/app-error")
    error = _assert_envelope(response, 409, "conflict")
    assert error["message"] == "Name already taken."
    assert error["fields"] == [{"field": "name", "message": "duplicate", "type": "conflict"}]
    assert response.headers["X-Extra"] == "1"


def test_unhandled_exception_returns_generic_500_and_logs_the_cause(client, caplog):
    with caplog.at_level(logging.ERROR):
        response = client.get("/_t/boom")
    error = _assert_envelope(response, 500, "internal_error")
    assert error["message"] == "An unexpected error occurred."
    assert "hunter2" not in response.text and "RuntimeError" not in response.text
    # ...but the real cause is in the server log, tagged with the same request id
    assert "internal detail" in caplog.text
    assert error["request_id"] in caplog.text


def test_all_error_kinds_share_one_shape(client):
    responses = [
        client.get("/nope"),
        client.post("/health"),
        client.get("/_t/validate"),
        client.get("/_t/http-error"),
        client.get("/_t/app-error"),
        client.get("/_t/boom"),
    ]
    for response in responses:
        body = response.json()
        assert list(body) == ["error"]
        assert {"code", "message"} <= set(body["error"])
        assert set(body["error"]) <= {"code", "message", "fields", "request_id"}


def test_successful_responses_are_not_wrapped(client):
    assert client.get("/health").json()["status"] == "ok"
