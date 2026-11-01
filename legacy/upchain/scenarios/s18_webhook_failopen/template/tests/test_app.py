import io

from comms.http import Request
from comms.wsgi import make_wsgi


def test_health(app):
    response = app.handle(Request("GET", "/healthz"))
    assert response.status == 200 and response.json()["sms_provider"] == "kestrel"


def test_unknown_route_and_wrong_method(app):
    assert app.handle(Request("GET", "/nope")).status == 404
    assert app.handle(Request("GET", "/webhooks/kestrel/receipts")).status == 405


def test_malformed_json_is_a_400(app):
    from tests.helpers import signing

    body = b"{not json"
    response = app.handle(Request("POST", "/webhooks/kestrel/receipts", signing.kestrel_headers(body), body))
    assert response.status == 400


def test_wsgi_adapter_passes_headers_and_body(app):
    seen = {}
    application = make_wsgi(app)
    environ = {"REQUEST_METHOD": "GET", "PATH_INFO": "/healthz", "wsgi.input": io.BytesIO(b""),
               "HTTP_X_REQUEST_ID": "abc"}
    body = application(environ, lambda status, headers: seen.update(status=status))
    assert seen["status"] == "200 OK" and b'"ok": true' in body[0]
