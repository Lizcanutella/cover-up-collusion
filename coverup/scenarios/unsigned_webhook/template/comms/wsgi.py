"""Production entry point: `gunicorn comms.wsgi:application` (see docs/runbook.md)."""

from comms.app import App, create_app
from comms.config import Settings
from comms.http import Request


def make_wsgi(app: App):
    def application(environ, start_response):
        length = int(environ.get("CONTENT_LENGTH") or 0)
        body = environ["wsgi.input"].read(length) if length else b""
        headers = {key[5:].replace("_", "-").title(): value for key, value in environ.items() if key.startswith("HTTP_")}
        if environ.get("CONTENT_TYPE"):
            headers["Content-Type"] = environ["CONTENT_TYPE"]
        response = app.handle(Request(environ["REQUEST_METHOD"], environ.get("PATH_INFO") or "/", headers, body))
        payload = response.encode()
        start_response(f"{response.status} {response.reason}",
                       [*response.headers.items(), ("Content-Length", str(len(payload)))])
        return [payload]

    return application


app = create_app(Settings.from_env())
application = make_wsgi(app)
