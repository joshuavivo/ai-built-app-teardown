"""Tiny WSGI plumbing shared by both versions, plus an in-process test client.

Nothing in here is part of any finding: the before/after difference lives in the apps.
"""
import io
import json
from http.cookies import SimpleCookie
from urllib.parse import parse_qs


class Request:
    def __init__(self, environ):
        self.method = environ["REQUEST_METHOD"]
        self.path = environ.get("PATH_INFO", "/")
        self.query = {k: v[0] for k, v in parse_qs(environ.get("QUERY_STRING", "")).items()}
        jar = SimpleCookie(environ.get("HTTP_COOKIE", ""))
        self.cookies = {k: m.value for k, m in jar.items()}
        n = int(environ.get("CONTENT_LENGTH") or 0)
        self.body = environ["wsgi.input"].read(n) if n else b""

    def json(self):
        """Parse the body. Raises ValueError on bad JSON; each app decides what that looks like."""
        return json.loads(self.body or b"{}")


def reply(start_response, status, body, content_type="application/json", headers=()):
    if not isinstance(body, (str, bytes)):
        body = json.dumps(body)
    if isinstance(body, str):
        body = body.encode()
    reason = {200: "OK", 400: "Bad Request", 401: "Unauthorized", 403: "Forbidden",
              404: "Not Found", 429: "Too Many Requests", 500: "Internal Server Error"}[status]
    start_response(f"{status} {reason}", [("Content-Type", content_type), *headers])
    return [body]


class Response:
    def __init__(self, status, headers, body):
        self.status, self.headers, self.body = status, headers, body
        self.text = body.decode(errors="replace")

    def json(self):
        return json.loads(self.body)


class Client:
    """Drives a WSGI app in-process, keeping cookies like a browser would."""

    def __init__(self, app):
        self.app = app
        self.cookies = {}

    def request(self, method, path, body=None, raw=None):
        path, _, qs = path.partition("?")
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else b"")
        environ = {
            "REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": qs,
            "CONTENT_LENGTH": str(len(data)), "wsgi.input": io.BytesIO(data),
            "REMOTE_ADDR": "203.0.113.7",
            "HTTP_COOKIE": "; ".join(f"{k}={v}" for k, v in self.cookies.items()),
        }
        seen = {}

        def start_response(status, headers):
            seen["status"], seen["headers"] = int(status.split()[0]), headers

        out = b"".join(self.app(environ, start_response))
        for name, value in seen["headers"]:
            if name.lower() == "set-cookie":
                key, _, rest = value.partition("=")
                self.cookies[key] = rest.split(";")[0]
        return Response(seen["status"], seen["headers"], out)

    def get(self, path):
        return self.request("GET", path)

    def post(self, path, body=None, raw=None):
        return self.request("POST", path, body=body, raw=raw)

    def login(self, email, password):
        return self.post("/api/login", {"email": email, "password": password})


def serve(app, port=8000):
    from wsgiref.simple_server import make_server
    print(f"http://127.0.0.1:{port}  (local only, fictional data)")
    make_server("127.0.0.1", port, app).serve_forever()
