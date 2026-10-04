"""Database SQLite wa-cli v2.1. Server hanya menyimpan data terenkripsi."""
import hashlib
import os
import secrets
import sqlite3
import time

INVITE_CHARS = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.environ.get("WA_DB") or os.path.join(BASE_DIR, "data", "wa2.db")
BLOB_DIR = os.path.join(os.path.dirname(DB_PATH), "blobs")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY, nickname TEXT NOT NULL, ik TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE, created_at INTEGER NOT NULL,
    last_seen INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS blocks (
    owner_id TEXT NOT NULL REFERENCES users(id),
    blocked_id TEXT NOT NULL REFERENCES users(id),
    PRIMARY KEY (owner_id, blocked_id)
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id TEXT NOT NULL REFERENCES users(id),
    recipient_id TEXT NOT NULL REFERENCES users(id),
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'sent' CHECK (status IN ('sent', 'delivered')),
    created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_msg_rcpt ON messages(recipient_id, id);
CREATE TABLE IF NOT EXISTS blobs (
    id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id),
    size INTEGER NOT NULL, created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (k TEXT PRIMARY KEY, v TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS invites (
    hash TEXT PRIMARY KEY, max_uses INTEGER NOT NULL, uses INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL
);
"""


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    os.makedirs(BLOB_DIR, exist_ok=True)
    conn = connect()
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
    try:
        os.chmod(DB_PATH, 0o600)
    except OSError:
        pass


def hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ---------- users ----------
def create_user(conn, nickname, ik, invite_hash=None):
    """Buat user. Kalau invite_hash diberikan, kode dipakai atomik; return None bila kode tidak valid."""
    token = secrets.token_urlsafe(32)
    for _ in range(20):
        uid = str(secrets.randbelow(9_000_000_000) + 1_000_000_000)
        try:
            with conn:
                if invite_hash is not None:
                    cur = conn.execute(
                        "UPDATE invites SET uses = uses + 1 WHERE hash = ? AND uses < max_uses AND expires_at > ?",
                        (invite_hash, int(time.time())))
                    if cur.rowcount != 1:
                        return None
                conn.execute(
                    "INSERT INTO users (id, nickname, ik, token_hash, created_at) VALUES (?, ?, ?, ?, ?)",
                    (uid, nickname, ik, hash_token(token), int(time.time())))
            return uid, token
        except sqlite3.IntegrityError:
            continue
    raise RuntimeError("Gagal membuat ID unik")


# ---------- pengaturan & undangan ----------
def get_setting(conn, k, default=None):
    r = conn.execute("SELECT v FROM settings WHERE k = ?", (k,)).fetchone()
    return r["v"] if r else default


def set_setting(conn, k, v):
    with conn:
        conn.execute("INSERT OR REPLACE INTO settings (k, v) VALUES (?, ?)", (k, v))


def invite_hash(code):
    norm = "".join(c for c in str(code).upper() if c in INVITE_CHARS + "01IOL")
    return hashlib.sha256(b"wa-cli/invite" + norm.encode("ascii")).hexdigest()


def create_invite(conn, uses=1, hours=24):
    raw = "".join(secrets.choice(INVITE_CHARS) for _ in range(8))
    code = raw[:4] + "-" + raw[4:]
    now = int(time.time())
    with conn:
        conn.execute("INSERT INTO invites (hash, max_uses, created_at, expires_at) VALUES (?, ?, ?, ?)",
                     (invite_hash(code), uses, now, now + int(hours * 3600)))
    return code


def list_invites(conn):
    return conn.execute("SELECT hash, max_uses, uses, created_at, expires_at FROM invites "
                        "ORDER BY created_at DESC").fetchall()


def revoke_invite(conn, prefix):
    with conn:
        return conn.execute("DELETE FROM invites WHERE hash LIKE ?", (prefix + "%",)).rowcount


def valid_invite_exists(conn):
    return conn.execute("SELECT 1 FROM invites WHERE uses < max_uses AND expires_at > ?",
                        (int(time.time()),)).fetchone() is not None


def count_users(conn):
    return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def list_users(conn):
    return conn.execute("SELECT id, nickname, created_at, last_seen FROM users ORDER BY created_at").fetchall()


def get_user(conn, uid):
    return conn.execute("SELECT id, nickname, ik, last_seen FROM users WHERE id = ?", (uid,)).fetchone()


def get_user_by_token(conn, token):
    return conn.execute("SELECT id, nickname, ik, last_seen FROM users WHERE token_hash = ?",
                        (hash_token(token),)).fetchone()


def touch(conn, uid, now):
    with conn:
        conn.execute("UPDATE users SET last_seen = ? WHERE id = ?", (now, uid))


# ---------- blokir ----------
def set_block(conn, owner, blocked, on):
    with conn:
        if on:
            conn.execute("INSERT OR IGNORE INTO blocks (owner_id, blocked_id) VALUES (?, ?)", (owner, blocked))
        else:
            conn.execute("DELETE FROM blocks WHERE owner_id = ? AND blocked_id = ?", (owner, blocked))


def is_blocked(conn, owner, blocked):
    return conn.execute("SELECT 1 FROM blocks WHERE owner_id = ? AND blocked_id = ?",
                        (owner, blocked)).fetchone() is not None


# ---------- pesan ----------
def insert_message(conn, sender, recipient, body):
    ts = int(time.time())
    with conn:
        cur = conn.execute("INSERT INTO messages (sender_id, recipient_id, body, created_at) VALUES (?, ?, ?, ?)",
                           (sender, recipient, body, ts))
    return cur.lastrowid, ts


def sync_incoming(conn, me, after, limit):
    rows = conn.execute(
        "SELECT id, sender_id, recipient_id, body, created_at FROM messages "
        "WHERE recipient_id = ? AND id > ? ORDER BY id LIMIT ?", (me, after, limit)).fetchall()
    if rows:
        ph = ",".join("?" * len(rows))
        with conn:
            conn.execute("UPDATE messages SET status = 'delivered' WHERE status = 'sent' AND id IN (%s)" % ph,
                         [r["id"] for r in rows])
    return [{"id": r["id"], "from": r["sender_id"], "to": r["recipient_id"],
             "text": r["body"], "created_at": r["created_at"]} for r in rows]


def statuses(conn, me, ids):
    ph = ",".join("?" * len(ids))
    rows = conn.execute("SELECT id, status FROM messages WHERE sender_id = ? AND id IN (%s)" % ph,
                        [me] + ids).fetchall()
    return {r["id"]: r["status"] for r in rows}


# ---------- blob (file terenkripsi) ----------
def add_blob(conn, bid, owner, size):
    with conn:
        conn.execute("INSERT INTO blobs (id, owner_id, size, created_at) VALUES (?, ?, ?, ?)",
                     (bid, owner, size, int(time.time())))


def blob_exists(conn, bid):
    return conn.execute("SELECT 1 FROM blobs WHERE id = ?", (bid,)).fetchone() is not None


def purge(conn):
    """Hapus pesan terkirim >1 jam, pesan tak terambil >14 hari, blob >3 hari."""
    now = int(time.time())
    with conn:
        conn.execute("DELETE FROM messages WHERE status = 'delivered' AND created_at < ?", (now - 3600,))
        conn.execute("DELETE FROM messages WHERE created_at < ?", (now - 14 * 86400,))
        old = conn.execute("SELECT id FROM blobs WHERE created_at < ?", (now - 3 * 86400,)).fetchall()
        for r in old:
            try:
                os.remove(os.path.join(BLOB_DIR, r["id"]))
            except OSError:
                pass
            conn.execute("DELETE FROM blobs WHERE id = ?", (r["id"],))
