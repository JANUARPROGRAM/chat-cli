"""Logika API wa-cli v2.1: routing, validasi, autentikasi, undangan, long polling."""
import base64
import os
import re
import secrets
import sys
import threading
import time
import traceback
import unicodedata
from collections import defaultdict, deque

import database as db

MAX_NICK_LEN = 20
MAX_WIRE_LEN = 4096
MAX_BLOB = 2 * 1024 * 1024
ONLINE_WINDOW = 45

ID_RE = re.compile(r"^\d{10}$")
NICK_RE = re.compile(r"^[\w .\-]+$")
IK_RE = re.compile(r"^[A-Za-z0-9_-]{43}$")
WIRE_RE = re.compile(r"^e2:[A-Za-z0-9_-]{100,}$")
USERS_RE = re.compile(r"^/users/(\d{10})$")
MESSAGES_RE = re.compile(r"^/messages/(\d{10})$")
BLOBS_RE = re.compile(r"^/blobs/([A-Za-z0-9_-]{22})$")
CTRL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f\u200e\u200f\u202a-\u202e\u2066-\u2069]")


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


class RateLimiter:
    def __init__(self):
        self.hits = defaultdict(deque)
        self.lock = threading.Lock()

    def check(self, key, limit, window):
        now = time.monotonic()
        with self.lock:
            q = self.hits[key]
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= limit:
                raise ApiError(429, "Terlalu banyak permintaan, coba lagi sebentar lagi")
            q.append(now)
            self._gc(now)

    def blocked(self, key, limit, window):
        now = time.monotonic()
        with self.lock:
            q = self.hits[key]
            while q and now - q[0] > window:
                q.popleft()
            return len(q) >= limit

    def add(self, key):
        with self.lock:
            self.hits[key].append(time.monotonic())

    def _gc(self, now):
        if len(self.hits) > 5000:
            for k in [k for k, v in self.hits.items() if not v or now - v[-1] > 3600]:
                del self.hits[k]


LIMITER = RateLimiter()

# --- long polling: request menunggu sampai versi berubah ---
_CV = threading.Condition()
_VERSION = [0]
_WAIT_LOCK = threading.Lock()
_WAITERS = defaultdict(int)


def wake():
    with _CV:
        _VERSION[0] += 1
        _CV.notify_all()


# ---------- validasi ----------
def clean_nickname(value):
    if not isinstance(value, str) or len(value) > 200:
        raise ApiError(400, "nickname wajib berupa teks")
    s = " ".join(CTRL_RE.sub("", unicodedata.normalize("NFC", value)).split())
    if not 2 <= len(s) <= MAX_NICK_LEN:
        raise ApiError(400, "Nickname harus 2-%d karakter" % MAX_NICK_LEN)
    if not NICK_RE.match(s):
        raise ApiError(400, "Nickname hanya boleh huruf, angka, spasi, titik, minus, dan underscore")
    return s


def clean_id(value, field):
    if not isinstance(value, str) or not ID_RE.match(value):
        raise ApiError(400, "%s harus ID 10 digit angka" % field)
    return value


def clean_ik(value):
    if not isinstance(value, str) or not IK_RE.match(value):
        raise ApiError(400, "ik harus kunci publik X25519 (43 karakter base64url)")
    try:
        if len(base64.urlsafe_b64decode(value + "=")) != 32:
            raise ValueError
    except ValueError:
        raise ApiError(400, "ik tidak valid")
    return value


def int_param(query, name, default, lo, hi):
    raw = query.get(name)
    if raw is None:
        return default
    try:
        val = int(raw)
    except ValueError:
        raise ApiError(400, "Parameter %s harus angka" % name)
    if not lo <= val <= hi:
        raise ApiError(400, "Parameter %s harus antara %d dan %d" % (name, lo, hi))
    return val


def authenticate(conn, headers):
    auth = headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise ApiError(401, "Butuh header 'Authorization: Bearer <token>'")
    token = auth[7:].strip()
    user = db.get_user_by_token(conn, token) if 0 < len(token) <= 200 else None
    if not user:
        raise ApiError(401, "Token tidak valid")
    now = int(time.time())
    if now - user["last_seen"] >= 5:
        db.touch(conn, user["id"], now)
    return user


# ---------- handler ----------
def h_register(conn, body, ip):
    LIMITER.check("reg:" + ip, 10, 3600)
    nick = clean_nickname(body.get("nickname"))
    ik = clean_ik(body.get("ik"))
    inv = None
    if db.get_setting(conn, "registration", "invite") == "invite":
        if LIMITER.blocked("regfail", 50, 3600):
            raise ApiError(429, "Terlalu banyak kode salah, pendaftaran dikunci sementara")
        code = body.get("invite")
        if not isinstance(code, str) or len(code) > 40:
            LIMITER.add("regfail")
            raise ApiError(403, "Kode undangan salah atau kedaluwarsa")
        inv = db.invite_hash(code)
    res = db.create_user(conn, nick, ik, inv)
    if res is None:
        LIMITER.add("regfail")
        raise ApiError(403, "Kode undangan salah atau kedaluwarsa")
    return 201, {"id": res[0], "nickname": nick, "token": res[1]}


def h_user(conn, user, uid):
    LIMITER.check("usr:" + user["id"], 60, 60)
    u = db.get_user(conn, uid)
    if not u:
        raise ApiError(404, "ID tidak ditemukan")
    return 200, {"id": u["id"], "nickname": u["nickname"], "ik": u["ik"], "last_seen": u["last_seen"],
                 "online": time.time() - u["last_seen"] < ONLINE_WINDOW}


def h_block(conn, user, body, on):
    target = clean_id(body.get("id"), "id")
    if target == user["id"] or not db.get_user(conn, target):
        raise ApiError(400, "ID tidak valid")
    db.set_block(conn, user["id"], target, on)
    return 200, {"id": target, "blocked": on}


def h_send(conn, user, body):
    LIMITER.check("msg:" + user["id"], 120, 60)
    to = clean_id(body.get("to"), "to")
    text = body.get("text")
    if not isinstance(text, str) or len(text) > MAX_WIRE_LEN or not WIRE_RE.match(text):
        raise ApiError(400, "Pesan harus terenkripsi end-to-end (format e2:...) dan maks %d karakter" % MAX_WIRE_LEN)
    if to == user["id"]:
        raise ApiError(400, "Tidak bisa mengirim pesan ke diri sendiri")
    if not db.get_user(conn, to):
        raise ApiError(404, "Penerima tidak ditemukan")
    if db.is_blocked(conn, to, user["id"]):  # diam-diam dibuang, pengirim tidak tahu
        return 201, {"id": 0, "status": "sent", "created_at": int(time.time())}
    mid, ts = db.insert_message(conn, user["id"], to, text)
    wake()
    return 201, {"id": mid, "status": "sent", "created_at": ts}


def h_sync(conn, user, uid, query):
    if uid != user["id"]:
        raise ApiError(403, "Hanya boleh membaca pesan sendiri")
    after = int_param(query, "after", 0, 0, 2 ** 62)
    limit = int_param(query, "limit", 50, 1, 100)
    wait = int_param(query, "wait", 0, 0, 25)
    track = []
    for part in query.get("track", "").split(",")[:50]:
        if part:
            if not part.isdigit() or len(part) > 15:
                raise ApiError(400, "track tidak valid")
            track.append(int(part))
    if wait:
        with _WAIT_LOCK:
            if _WAITERS[uid] >= 3:
                raise ApiError(429, "Terlalu banyak koneksi polling")
            _WAITERS[uid] += 1
    deadline = time.monotonic() + wait
    try:
        while True:
            seen = _VERSION[0]
            msgs = db.sync_incoming(conn, uid, after, limit)
            status = db.statuses(conn, uid, track) if track else {}
            left = deadline - time.monotonic()
            if msgs or left <= 0 or any(s != "sent" for s in status.values()):
                break
            with _CV:
                _CV.wait_for(lambda: _VERSION[0] != seen, timeout=min(left, 5))
    finally:
        if wait:
            with _WAIT_LOCK:
                _WAITERS[uid] -= 1
    if msgs:
        wake()  # bangunkan pengirim yang menunggu status "delivered"
    db.touch(conn, uid, int(time.time()))
    return 200, {"messages": msgs, "last_id": max([m["id"] for m in msgs], default=after),
                 "status": {str(k): v for k, v in status.items()}}


def h_blob_put(conn, user, body):
    LIMITER.check("blob:" + user["id"], 20, 3600)
    if not isinstance(body, (bytes, bytearray)) or not 1 <= len(body) <= MAX_BLOB:
        raise ApiError(400, "Blob kosong atau lebih dari %d byte" % MAX_BLOB)
    bid = secrets.token_urlsafe(16)
    fd = os.open(os.path.join(db.BLOB_DIR, bid), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(body)
    db.add_blob(conn, bid, user["id"], len(body))
    return 201, {"id": bid, "size": len(body)}


def h_blob_get(conn, user, bid):
    LIMITER.check("blobg:" + user["id"], 60, 3600)
    if not db.blob_exists(conn, bid):
        raise ApiError(404, "File tidak ditemukan / sudah kedaluwarsa")
    try:
        with open(os.path.join(db.BLOB_DIR, bid), "rb") as f:
            return 200, f.read()
    except OSError:
        raise ApiError(404, "File tidak ditemukan")


# ---------- router ----------
def handle(method, path, query, headers, body, ip):
    try:
        return _route(method, path, query, headers, body, ip)
    except ApiError as e:
        return e.status, {"error": e.message}
    except Exception:
        traceback.print_exc(file=sys.stderr)
        return 500, {"error": "Kesalahan internal server"}


def _need(method, allowed):
    if method != allowed:
        raise ApiError(405, "Method tidak diizinkan, gunakan %s" % allowed)


def _route(method, path, query, headers, body, ip):
    path = path.rstrip("/") or "/"
    conn = db.connect()
    try:
        if path == "/":
            _need(method, "GET")
            return 200, {"name": "wa-cli", "version": "2.1", "status": "ok",
                         "registration": db.get_setting(conn, "registration", "invite")}
        if path == "/health":
            _need(method, "GET")
            conn.execute("SELECT 1").fetchone()
            return 200, {"status": "ok", "time": int(time.time())}
        if path == "/register":
            _need(method, "POST")
            return h_register(conn, body, ip)
        if path == "/messages/send":
            _need(method, "POST")
            return h_send(conn, authenticate(conn, headers), body)
        if path in ("/block", "/unblock"):
            _need(method, "POST")
            return h_block(conn, authenticate(conn, headers), body, path == "/block")
        if path == "/blobs":
            _need(method, "POST")
            return h_blob_put(conn, authenticate(conn, headers), body)
        m = BLOBS_RE.match(path)
        if m:
            _need(method, "GET")
            return h_blob_get(conn, authenticate(conn, headers), m.group(1))
        m = USERS_RE.match(path)
        if m:
            _need(method, "GET")
            return h_user(conn, authenticate(conn, headers), m.group(1))
        m = MESSAGES_RE.match(path)
        if m:
            _need(method, "GET")
            return h_sync(conn, authenticate(conn, headers), m.group(1), query)
        raise ApiError(404, "Endpoint tidak ditemukan")
    finally:
        conn.close()
