"""Penyimpanan lokal client (SQLite): kontak, sesi kripto, grup, riwayat pesan.

Kunci aplikasi: bila aktif, isi sensitif (pesan, nama kontak, sesi kripto, token, kunci privat)
dienkripsi AES-256-GCM per kolom. ID, waktu, dan status pesan tetap terbaca (dibutuhkan untuk query).
"""
import functools
import json
import os
import sqlite3
import tempfile
import threading

import secure

SCHEMA = """
CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS peers (
    id TEXT PRIMARY KEY, nick TEXT, snick TEXT, ik TEXT,
    verified INTEGER NOT NULL DEFAULT 0, blocked INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS sessions (
    peer TEXT NOT NULL, sid TEXT NOT NULL, state TEXT NOT NULL, PRIMARY KEY (peer, sid));
CREATE TABLE IF NOT EXISTS groups (
    gid TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, members TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS msgs (
    n INTEGER PRIMARY KEY AUTOINCREMENT, uid TEXT NOT NULL, chat TEXT NOT NULL, sender TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'm', body TEXT NOT NULL, meta TEXT NOT NULL DEFAULT '{}',
    ts INTEGER NOT NULL, srv_id INTEGER, status TEXT NOT NULL, exp INTEGER NOT NULL DEFAULT 0,
    UNIQUE (sender, uid));
CREATE INDEX IF NOT EXISTS idx_msgs_chat ON msgs(chat, n);
"""
PEER_FIELDS = {"nick", "snick", "ik", "verified", "blocked"}
LOCK_KEY = "_lock"  # satu-satunya baris kv yang selalu plaintext (berisi kunci utama yang terbungkus password)


def synced(fn):
    @functools.wraps(fn)
    def wrapper(self, *a, **kw):
        with self.lock:
            return fn(self, *a, **kw)
    return wrapper


class Store:
    def __init__(self, path):
        os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
        self.path = path
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self.key = None
        with self.lock:
            self.db.executescript(SCHEMA)
            self.db.commit()
            r = self.db.execute("SELECT v FROM kv WHERE k = ?", (LOCK_KEY,)).fetchone()
            self.lock_meta = json.loads(r["v"]) if r else None
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    # -- enkripsi kolom --
    def _e(self, label, v):
        return v if v is None or self.key is None else secure.field_enc(self.key, label, v)

    def _d(self, label, v):
        return v if v is None or self.key is None else secure.field_dec(self.key, label, v)

    def _q(self, sql, args=()):
        return self.db.execute(sql, args).fetchall()

    def _x(self, sql, args=()):
        cur = self.db.execute(sql, args)
        self.db.commit()
        return cur

    # -- kunci aplikasi --
    @property
    def locked(self):
        """True bila kunci aplikasi aktif (data terenkripsi), terlepas sudah di-unlock atau belum."""
        return self.lock_meta is not None

    @synced
    def unlock(self, password):
        self.key = secure.lock_unwrap(password, self.lock_meta)  # ValueError bila salah

    @synced
    def verify_password(self, password):
        secure.lock_unwrap(password, self.lock_meta)

    @synced
    def enable_lock(self, password):
        if self.lock_meta is not None:
            raise ValueError("Kunci aplikasi sudah aktif")
        master = os.urandom(32)
        self._rekey(master, secure.lock_wrap(password, master))

    @synced
    def disable_lock(self):
        if self.lock_meta is None or self.key is None:
            raise ValueError("Kunci aplikasi tidak aktif / belum di-unlock")
        self._rekey(None, None)

    @synced
    def change_password(self, old, new):
        master = secure.lock_unwrap(old, self.lock_meta)
        meta = secure.lock_wrap(new, master)
        self._x("INSERT OR REPLACE INTO kv (k, v) VALUES (?, ?)", (LOCK_KEY, json.dumps(meta)))
        self.lock_meta = meta

    def _rekey(self, new_key, new_meta):
        """Tulis ulang semua kolom sensitif dalam SATU transaksi (atomik)."""
        old, c = self.key, self.db

        def cv(label, v):
            if v is None:
                return None
            plain = secure.field_dec(old, label, v) if old else v
            return secure.field_enc(new_key, label, plain) if new_key else plain
        try:
            for r in c.execute("SELECT k, v FROM kv WHERE k != ?", (LOCK_KEY,)).fetchall():
                c.execute("UPDATE kv SET v = ? WHERE k = ?", (cv("kv.v", r["v"]), r["k"]))
            for r in c.execute("SELECT id, nick, snick FROM peers").fetchall():
                c.execute("UPDATE peers SET nick = ?, snick = ? WHERE id = ?",
                          (cv("peers.nick", r["nick"]), cv("peers.snick", r["snick"]), r["id"]))
            for r in c.execute("SELECT peer, sid, state FROM sessions").fetchall():
                c.execute("UPDATE sessions SET state = ? WHERE peer = ? AND sid = ?",
                          (cv("sessions.state", r["state"]), r["peer"], r["sid"]))
            for r in c.execute("SELECT gid, name, members FROM groups").fetchall():
                c.execute("UPDATE groups SET name = ?, members = ? WHERE gid = ?",
                          (cv("groups.name", r["name"]), cv("groups.members", r["members"]), r["gid"]))
            for r in c.execute("SELECT n, body, meta FROM msgs").fetchall():
                c.execute("UPDATE msgs SET body = ?, meta = ? WHERE n = ?",
                          (cv("msgs.body", r["body"]), cv("msgs.meta", r["meta"]), r["n"]))
            if new_meta is None:
                c.execute("DELETE FROM kv WHERE k = ?", (LOCK_KEY,))
            else:
                c.execute("INSERT OR REPLACE INTO kv (k, v) VALUES (?, ?)", (LOCK_KEY, json.dumps(new_meta)))
            c.commit()
        except Exception:
            c.rollback()
            raise
        self.key, self.lock_meta = new_key, new_meta

    # -- kv --
    @synced
    def kv_get(self, k, default=None):
        r = self._q("SELECT v FROM kv WHERE k = ?", (k,))
        return self._d("kv.v", r[0]["v"]) if r else default

    @synced
    def kv_set(self, k, v):
        assert k != LOCK_KEY
        self._x("INSERT OR REPLACE INTO kv (k, v) VALUES (?, ?)", (k, self._e("kv.v", str(v))))

    # -- peers --
    def _p(self, r):
        d = dict(r)
        d["nick"], d["snick"] = self._d("peers.nick", d["nick"]), self._d("peers.snick", d["snick"])
        return d

    @synced
    def peer(self, uid):
        r = self._q("SELECT * FROM peers WHERE id = ?", (uid,))
        return self._p(r[0]) if r else None

    @synced
    def peer_set(self, uid, **f):
        assert set(f) <= PEER_FIELDS
        self.db.execute("INSERT OR IGNORE INTO peers (id) VALUES (?)", (uid,))
        for k, v in f.items():
            if k in ("nick", "snick"):
                v = self._e("peers." + k, v)
            self.db.execute("UPDATE peers SET %s = ? WHERE id = ?" % k, (v, uid))
        self.db.commit()

    @synced
    def contacts(self):
        rows = [(r["id"], self._d("peers.nick", r["nick"])) for r in self._q(
            "SELECT id, nick FROM peers WHERE nick IS NOT NULL")]
        return sorted(rows, key=lambda x: x[1].lower())

    # -- sesi --
    @synced
    def sessions(self, peer):
        return {r["sid"]: json.loads(self._d("sessions.state", r["state"])) for r in self._q(
            "SELECT sid, state FROM sessions WHERE peer = ?", (peer,))}

    @synced
    def save_session(self, peer, st):
        self._x("INSERT OR REPLACE INTO sessions (peer, sid, state) VALUES (?, ?, ?)",
                (peer, st["sid"], self._e("sessions.state", json.dumps(st))))

    @synced
    def del_sessions(self, peer):
        self._x("DELETE FROM sessions WHERE peer = ?", (peer,))

    # -- grup --
    def _g(self, r):
        return {"gid": r["gid"], "name": self._d("groups.name", r["name"]),
                "members": json.loads(self._d("groups.members", r["members"]))}

    @synced
    def group(self, gid):
        r = self._q("SELECT * FROM groups WHERE gid = ?", (gid,))
        return self._g(r[0]) if r else None

    @synced
    def groups(self):
        return sorted((self._g(r) for r in self._q("SELECT * FROM groups")), key=lambda g: g["name"].lower())

    @synced
    def group_by_name(self, name):
        return next((g for g in self.groups() if g["name"].lower() == name.lower()), None)

    @synced
    def group_set(self, gid, name, members):
        self._x("INSERT OR REPLACE INTO groups (gid, name, members) VALUES (?, ?, ?)",
                (gid, self._e("groups.name", name), self._e("groups.members", json.dumps(members))))

    @synced
    def group_del(self, gid):
        self._x("DELETE FROM groups WHERE gid = ?", (gid,))

    # -- pesan --
    def _m(self, r):
        d = dict(r)
        d["body"], d["meta"] = self._d("msgs.body", d["body"]), self._d("msgs.meta", d["meta"])
        return d

    @synced
    def msg_add(self, uid, chat, sender, kind, body, meta, ts, srv_id, status, exp):
        cur = self._x("INSERT OR IGNORE INTO msgs (uid, chat, sender, kind, body, meta, ts, srv_id, status, exp) "
                      "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                      (uid, chat, sender, kind, self._e("msgs.body", body), self._e("msgs.meta", json.dumps(meta)),
                       ts, srv_id, status, exp))
        return cur.lastrowid if cur.rowcount else None

    @synced
    def msg(self, n):
        r = self._q("SELECT * FROM msgs WHERE n = ?", (n,))
        return self._m(r[0]) if r else None

    @synced
    def msg_uid(self, chat, uid):
        r = self._q("SELECT * FROM msgs WHERE chat = ? AND uid = ? LIMIT 1", (chat, uid))
        return self._m(r[0]) if r else None

    @synced
    def msgs(self, chat, limit=20):
        rows = self._q("SELECT * FROM msgs WHERE chat = ? ORDER BY n DESC LIMIT ?", (chat, limit))
        return [self._m(r) for r in reversed(rows)]

    @synced
    def set_status(self, n, status):
        self._x("UPDATE msgs SET status = ? WHERE n = ?", (status, n))

    @synced
    def unread(self, chat):
        return [dict(r) for r in self._q(
            "SELECT n, uid, sender FROM msgs WHERE chat = ? AND status = 'unread' ORDER BY n", (chat,))]

    @synced
    def unread_summary(self):
        return [(r["chat"], r["c"]) for r in self._q(
            "SELECT chat, COUNT(*) AS c FROM msgs WHERE status = 'unread' GROUP BY chat")]

    @synced
    def mark_read(self, chat):
        self._x("UPDATE msgs SET status = 'read' WHERE chat = ? AND status = 'unread'", (chat,))

    @synced
    def pending_tracks(self):
        return [r["srv_id"] for r in self._q(
            "SELECT srv_id FROM msgs WHERE status = 'sent' AND srv_id > 0 ORDER BY n DESC LIMIT 50")]

    @synced
    def mark_delivered(self, srv_id):
        self._x("UPDATE msgs SET status = 'delivered' WHERE srv_id = ? AND status = 'sent'", (srv_id,))

    @synced
    def mark_read_uids(self, chat, uids):
        for u in uids[:100]:
            self._x("UPDATE msgs SET status = 'read' WHERE chat = ? AND uid = ? AND status IN ('sent','delivered')",
                    (chat, str(u)))

    @synced
    def delete_msg(self, sender, uid):
        self._x("UPDATE msgs SET kind = 'x', body = ?, meta = ?, exp = 0 WHERE sender = ? AND uid = ?",
                (self._e("msgs.body", ""), self._e("msgs.meta", "{}"), sender, uid))

    @synced
    def purge_expired(self, now):
        return self._x("DELETE FROM msgs WHERE exp > 0 AND exp <= ?", (int(now),)).rowcount

    @synced
    def clear_chat(self, chat):
        self._x("DELETE FROM msgs WHERE chat = ?", (chat,))

    # -- backup --
    @synced
    def snapshot(self):
        fd, tmp = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            dst = sqlite3.connect(tmp)
            self.db.backup(dst)
            dst.close()
            with open(tmp, "rb") as f:
                return f.read()
        finally:
            os.remove(tmp)

    @synced
    def close(self):
        self.db.close()
