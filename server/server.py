#!/usr/bin/env python3
"""HTTP server wa-cli v2.1. Jalankan: python server/server.py"""
import json
import os
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qsl, urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import api  # noqa: E402
import database  # noqa: E402

HOST = os.environ.get("WA_HOST", "127.0.0.1")
PORT = int(os.environ.get("WA_PORT", "8080"))
MAX_BODY = 8192


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 64


class Handler(BaseHTTPRequestHandler):
    server_version = "wa-cli"
    sys_version = ""
    timeout = 30

    def _ip(self):
        return self.headers.get("CF-Connecting-IP") or self.client_address[0]

    def _send(self, status, payload):
        if isinstance(payload, (bytes, bytearray)):
            data, ctype = bytes(payload), "application/octet-stream"
        else:
            data, ctype = json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8"
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def _dispatch(self):
        if len(self.path) > 2048:
            return self._send(414, {"error": "URL terlalu panjang"})
        parts = urlsplit(self.path)
        query = dict(parse_qsl(parts.query))
        body = {}
        if self.command == "POST":
            is_blob = parts.path.rstrip("/") == "/blobs"
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self._send(400, {"error": "Content-Length tidak valid"})
            limit = api.MAX_BLOB if is_blob else MAX_BODY
            if length < 0:
                return self._send(400, {"error": "Content-Length tidak valid"})
            if length > limit:
                return self._send(413, {"error": "Body terlalu besar (maks %d byte)" % limit})
            try:
                raw = self.rfile.read(length) if length else b""
            except OSError:
                return self._send(408, {"error": "Timeout membaca request"})
            if is_blob:
                body = raw
            else:
                try:
                    body = json.loads(raw.decode("utf-8")) if raw else {}
                except (UnicodeDecodeError, ValueError):
                    return self._send(400, {"error": "Body harus JSON yang valid"})
                if not isinstance(body, dict):
                    return self._send(400, {"error": "Body harus berupa objek JSON"})
        status, payload = api.handle(self.command, parts.path, query, self.headers, body, self._ip())
        self._send(status, payload)

    do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = _dispatch

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s %s\n" % (time.strftime("%H:%M:%S"), self._ip(), fmt % args))


def janitor():
    while True:
        try:
            conn = database.connect()
            try:
                database.purge(conn)
            finally:
                conn.close()
        except Exception:
            traceback.print_exc()
        time.sleep(600)


def main():
    database.init_db()
    try:
        httpd = Server((HOST, PORT), Handler)
    except OSError as e:
        sys.exit("Gagal listen di %s:%d -> %s\n(Port dipakai proses lain? coba: pkill -f server.py)" % (HOST, PORT, e))
    threading.Thread(target=janitor, daemon=True).start()
    conn = database.connect()
    try:
        if (database.get_setting(conn, "registration", "invite") == "invite"
                and database.count_users(conn) == 0 and not database.valid_invite_exists(conn)):
            print("*** KODE UNDANGAN PERTAMA: %s (berlaku 24 jam, 1x pakai) ***" % database.create_invite(conn, 1, 24))
    finally:
        conn.close()
    print("wa-cli server v2.1 jalan di http://%s:%d  (DB: %s)" % (HOST, PORT, database.DB_PATH))
    print("Tekan Ctrl+C untuk berhenti.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer berhenti.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
