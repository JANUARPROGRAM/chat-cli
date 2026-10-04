#!/usr/bin/env python3
"""wa-cli client v2.1: E2E (X25519 + Double Ratchet + AES-256-GCM), grup, file, long polling.

  python cli/client.py -s https://xxxx.trycloudflare.com
  python cli/client.py -p b            # akun/profil kedua di HP yang sama
  python cli/client.py -i ABCD-EFGH    # kode undangan dari pemilik server
"""
import argparse
import getpass
import http.client
import json
import os
import re
import secrets
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

import secure
from secure import b64d, b64e
from store import Store

try:
    import readline  # noqa: F401
except ImportError:
    readline = None

HOME = os.path.expanduser("~")
CONFIG_DIR = os.path.join(HOME, ".wa-cli2")
DOWNLOAD_DIR = os.path.join(HOME, "wa-downloads")
DEFAULT_SERVER = "http://127.0.0.1:8080"
WAIT = max(0, min(25, int(os.environ.get("WA_WAIT", "25"))))
MAX_FILE = 1_500_000
ID_RE = re.compile(r"^\d{10}$")
UID_RE = re.compile(r"^[0-9a-f]{16}$")
PROFILE_RE = re.compile(r"^[A-Za-z0-9_-]{1,30}$")
GNAME_RE = re.compile(r"^[\w.\-]{2,20}$")
CTRL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f\u202a-\u202e\u2066-\u2069]")
SECRET_KEYS = ("token", "ik_priv")
TICKS = {"sent": "✓", "delivered": "✓✓", "read": "✓✓ dibaca", "failed": "✗ gagal"}

HELP = """Command:
  me                          ID, nickname, server
  add [id] [nama]             tambah kontak
  contacts                    daftar kontak (✓ = terverifikasi)
  chat <id|nama|#grup>        buka chat (di dalam chat: /help)
  send <id|nama|#grup> <teks> kirim tanpa masuk chat
  status <id|nama>            online / terakhir dilihat
  verify <id|nama>            cocokkan safety number (anti-penyadapan)
  trust <id|nama>             terima kunci baru kontak (setelah peringatan)
  block / unblock <id|nama>   blokir / buka blokir
  group new <nama> <id>...    buat grup | group list | group leave <nama>
  get <no>                    unduh file dari pesan #no
  clear <id|nama|#grup>       hapus riwayat lokal
  notif on|hide|off           notifikasi Android (butuh termux-api)
  lock on|off|passwd          kunci aplikasi: enkripsi data lokal dengan password
  backup [file] / restore <file>   cadangan terenkripsi password
  server [url]                lihat / ganti URL server
  exit                        keluar"""
CHAT_HELP = """Di dalam chat:
  <teks>                kirim pesan
  /reply <no> <teks>    balas pesan #no
  /del <no>             hapus pesanmu #no (untuk semua orang)
  /file <path> [teks]   kirim file (maks 1.5 MB, terenkripsi)
  /get <no>             unduh file dari pesan #no
  /exp <off|30s|5m|1h|1d>   pesan yang kamu kirim hilang otomatis
  /info                 info chat | /back  keluar chat"""


# ---------- util ----------
def safe(text):
    return CTRL_RE.sub("", str(text).replace("\n", " / ").replace("\t", " "))


def fmt_time(ts):
    return time.strftime("%H:%M", time.localtime(ts))


def fmt_ago(ts):
    if not ts:
        return "belum pernah"
    d = max(0, int(time.time()) - ts)
    if d < 60:
        return "baru saja"
    for size, name in ((86400, "hari"), (3600, "jam"), (60, "menit")):
        if d >= size:
            return "%d %s lalu" % (d // size, name)


def human_size(n):
    return "%.1f KB" % (n / 1024) if n < 1024 * 1024 else "%.2f MB" % (n / 1048576)


def normalize_url(url):
    url = (url or "").strip().rstrip("/")
    if not url:
        return None
    if not re.match(r"^https?://", url, re.I):
        url = ("http://" if re.match(r"^(127\.|localhost|192\.168\.|10\.)", url) else "https://") + url
    return url


def parse_duration(s):
    s = s.strip().lower()
    if s in ("off", "0", "mati"):
        return 0
    m = re.fullmatch(r"(\d{1,5})([smhd])", s)
    if not m:
        return None
    v = int(m.group(1)) * {"s": 1, "m": 60, "h": 3600, "d": 86400}[m.group(2)]
    return v if 1 <= v <= 30 * 86400 else None


def safe_filename(name):
    name = CTRL_RE.sub("", os.path.basename(name.replace("\\", "/"))).strip().lstrip(".")
    return re.sub(r"[^\w.\- ()]", "_", name)[:60] or "file"


def cfg_path(profile):
    return os.path.join(CONFIG_DIR, profile + ".json")


def db_path(profile):
    return os.path.join(CONFIG_DIR, profile + ".db")


def load_config(profile):
    try:
        with open(cfg_path(profile), "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if all(k in cfg for k in ("server", "id", "nickname", "ik_pub")):
            return cfg
    except (OSError, ValueError):
        pass
    return None


def save_config(profile, cfg, strip=True):
    """Simpan config. Rahasia (token, kunci privat) TIDAK ditulis; mereka ada di database lokal."""
    os.makedirs(CONFIG_DIR, mode=0o700, exist_ok=True)
    tmp = cfg_path(profile) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in cfg.items() if not (strip and k in SECRET_KEYS)}, f)
    os.chmod(tmp, 0o600)
    os.replace(tmp, cfg_path(profile))


# ---------- HTTP ----------
class ApiFail(Exception):
    def __init__(self, message, status=0):
        super().__init__(message)
        self.status = status


class KeyChanged(Exception):
    pass


class Retry(Exception):
    pass


def request(cfg, method, path, body=None, raw=None, timeout=10, binary=False):
    url = cfg["server"].rstrip("/") + path
    data = raw if raw is not None else (json.dumps(body).encode("utf-8") if body is not None else None)
    try:
        req = urllib.request.Request(url, data=data, method=method)
    except ValueError:
        raise ApiFail("URL server tidak valid: %s" % cfg["server"])
    req.add_header("User-Agent", "wa-cli/2.0")
    if data is not None:
        req.add_header("Content-Type", "application/octet-stream" if raw is not None else "application/json")
    if cfg.get("token"):
        req.add_header("Authorization", "Bearer " + cfg["token"])
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content, status = resp.read(4_000_000), resp.status
    except urllib.error.HTTPError as e:
        content, status = e.read(1_000_000), e.code
    except urllib.error.URLError as e:
        raise ApiFail("Tidak bisa terhubung ke server (%s)" % e.reason)
    except (OSError, http.client.HTTPException) as e:
        raise ApiFail("Koneksi terputus/timeout (%s)" % e.__class__.__name__)
    except ValueError:
        raise ApiFail("URL server tidak valid: %s" % cfg["server"])
    if binary and status < 400:
        return content
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        payload = None
    if status >= 400 or not isinstance(payload, dict):
        if isinstance(payload, dict) and payload.get("error"):
            msg = safe(payload["error"])
        else:
            msg = "Respons bukan dari wa-cli server (HTTP %d). Tunnel mati / URL salah?" % status
        raise ApiFail(msg, status)
    return payload


def ask_new_password():
    while True:
        p1 = getpass.getpass("Password baru (min 8 karakter): ")
        if len(p1) < 8:
            print("[!] Minimal 8 karakter.")
        elif p1 != getpass.getpass("Ulangi password: "):
            print("[!] Tidak sama.")
        else:
            return p1


def unlock_store(store):
    for _ in range(3):
        try:
            store.unlock(getpass.getpass("🔒 Password kunci aplikasi: "))
            return True
        except ValueError:
            print("[!] Password salah.")
    return False


def do_register(server, invite=None):
    """Daftar akun baru. Return cfg lengkap (termasuk rahasia), atau None bila gagal."""
    try:
        mode = request({"server": server}, "GET", "/").get("registration")
    except ApiFail as e:
        print("[!] %s" % e)
        return None
    priv, pub = secure.gen_keypair()
    while True:
        if mode == "invite" and not invite:
            invite = input("Kode undangan (minta ke pemilik server): ").strip()
        nick = input("Buat nickname (2-20 karakter): ").strip()
        body = {"nickname": nick, "ik": pub}
        if mode == "invite":
            body["invite"] = invite
        try:
            r = request({"server": server}, "POST", "/register", body)
        except ApiFail as e:
            print("[!] %s" % e)
            if e.status == 0 or e.status >= 500 or e.status == 429:
                return None
            if e.status == 403:
                invite = None
            continue
        return {"server": server, "id": r["id"], "nickname": r["nickname"], "token": r["token"],
                "ik_priv": priv, "ik_pub": pub, "last_id": 0}


# ---------- aplikasi ----------
class App:
    def __init__(self, profile, cfg, store):
        self.profile, self.cfg = profile, cfg
        self.db = store
        self.sec = secure.Secure(self.db, cfg["id"], cfg["ik_priv"], cfg["ik_pub"])
        self.chat = None
        self.last_id = int(cfg.get("last_id", 0))
        self.stop = threading.Event()
        self.print_lock = threading.Lock()
        self.cfg_lock = threading.Lock()
        self.in_input, self.cur_prompt = False, ""
        self.tty = sys.stdout.isatty()
        self.rc_queue = []
        self.has_notif = shutil.which("termux-notification") is not None

    # -- dasar --
    @property
    def me(self):
        return self.cfg["id"]

    def api(self, method, path, body=None, **kw):
        return request(self.cfg, method, path, body, **kw)

    def save_cfg(self):
        with self.cfg_lock:
            save_config(self.profile, self.cfg)

    def pname(self, uid):
        p = self.db.peer(uid)
        if p and p["nick"]:
            return p["nick"]
        return "~" + safe(p["snick"]) if p and p["snick"] else uid

    def title(self, chat):
        if chat.startswith("g:"):
            g = self.db.group(chat[2:])
            return "#" + g["name"] if g else chat
        return self.pname(chat)

    def prompt(self):
        return "[%s]> " % self.title(self.chat) if self.chat else "wa> "

    def out(self, text=""):
        with self.print_lock:
            redraw = self.in_input and self.tty
            if redraw:
                sys.stdout.write("\r\033[K")
            sys.stdout.write(text + "\n")
            if redraw:
                sys.stdout.write(self.cur_prompt + (readline.get_line_buffer() if readline else ""))
            sys.stdout.flush()

    def read(self, prompt=None):
        self.cur_prompt = prompt if prompt is not None else self.prompt()
        self.in_input = True
        try:
            return input(self.cur_prompt)
        finally:
            self.in_input = False

    def resolve(self, target, groups=True):
        t = target.strip()
        if t.startswith("#"):
            g = self.db.group_by_name(t[1:])
            if g and groups:
                return "g:" + g["gid"]
            self.out("[!] Grup '%s' %s." % (safe(t), "tidak ditemukan" if not g else "tidak berlaku di sini"))
            return None
        if ID_RE.match(t):
            return t
        for uid, nick in self.db.contacts():
            if nick.lower() == t.lower():
                return uid
        self.out("[!] '%s' bukan ID 10 digit dan tidak ada di kontak." % safe(t))
        return None

    def ensure_peer(self, uid, check=False):
        p = self.db.peer(uid)
        if p and p["ik"] and not check:
            return p
        u = self.api("GET", "/users/" + uid)
        if p and p["ik"] and p["ik"] != u["ik"]:
            raise KeyChanged("KUNCI %s BERUBAH! Server mungkin dimanipulasi. Cek 'verify %s', lalu 'trust %s' bila yakin."
                             % (self.pname(uid), uid, uid))
        self.db.peer_set(uid, ik=u["ik"], snick=safe(u["nickname"]))
        return self.db.peer(uid)

    # -- kirim --
    def transmit(self, peer, payload):
        p = self.ensure_peer(peer)
        wire = self.sec.encrypt(peer, p["ik"], payload)
        for attempt in range(3):
            try:
                return self.api("POST", "/messages/send", {"to": peer, "text": wire})["id"]
            except ApiFail as e:
                if (e.status and e.status < 500) or attempt == 2:
                    raise
                time.sleep(1.5)

    def broadcast(self, chat, payload):
        """Kirim ke semua tujuan chat (grup = fan-out lewat sesi masing-masing)."""
        group = chat.startswith("g:")
        if group:
            g = self.db.group(chat[2:])
            targets = [m for m in g["members"] if m != self.me] if g else []
            payload = dict(payload, g=chat[2:])
        else:
            targets = [chat]
        ok, srv = bool(targets), None
        for peer in targets:
            try:
                srv = self.transmit(peer, payload)
            except (ApiFail, KeyChanged, ValueError) as e:
                ok = False
                self.out("[!] Gagal kirim ke %s: %s" % (self.pname(peer), e))
        return ok, (None if group else srv)

    def deliver(self, chat, payload, kind, body, meta):
        uid = secrets.token_hex(8)
        payload = dict(payload, u=uid)
        exp = int(self.db.kv_get("exp:" + chat, 0))
        if exp:
            payload["e"] = exp
        ok, srv = self.broadcast(chat, payload)
        now = int(time.time())
        n = self.db.msg_add(uid, chat, self.me, kind, body, meta, now, srv, "sent" if ok else "failed",
                            now + exp if exp else 0)
        return self.db.msg(n)

    def send_message(self, chat, text, reply_n=None):
        if len(text) > 1000:
            self.out("[!] Pesan terlalu panjang (maks 1000 karakter).")
            return None
        payload, meta = {"t": "m", "x": text}, {}
        if reply_n:
            o = self.db.msg(reply_n)
            if not o or o["chat"] != chat:
                self.out("[!] Pesan #%s tidak ada di chat ini." % reply_n)
                return None
            payload["r"] = meta["r"] = o["uid"]
        return self.deliver(chat, payload, "m", text, meta)

    def send_file(self, chat, path, caption):
        path = os.path.expanduser(path)
        try:
            size = os.path.getsize(path)
            if size > MAX_FILE or size == 0:
                return self.out("[!] Ukuran file harus 1 byte - %s." % human_size(MAX_FILE))
            with open(path, "rb") as f:
                data = f.read()
        except OSError as e:
            return self.out("[!] Tidak bisa membaca file: %s" % e.strerror)
        key, blob = secure.file_encrypt(data)
        try:
            bid = self.api("POST", "/blobs", raw=blob, timeout=90)["id"]
        except ApiFail as e:
            return self.out("[!] Upload gagal: %s" % e)
        meta = {"b": bid, "k": key, "n": safe_filename(path), "z": size}
        m = self.deliver(chat, dict(meta, t="f", x=caption), "f", caption, meta)
        if m:
            self.out(self.fmt(m))

    def get_file(self, n):
        m = self.db.msg(n) if n else None
        if not m or m["kind"] != "f":
            return self.out("[!] Pesan #%s bukan file." % n)
        meta = json.loads(m["meta"])
        try:
            blob = self.api("GET", "/blobs/" + meta["b"], binary=True, timeout=90)
            data = secure.file_decrypt(meta["k"], blob)
        except (ApiFail, ValueError) as e:
            return self.out("[!] Gagal mengunduh: %s" % e)
        os.makedirs(DOWNLOAD_DIR, mode=0o700, exist_ok=True)
        dest, i = os.path.join(DOWNLOAD_DIR, meta["n"]), 1
        while os.path.exists(dest):
            dest, i = os.path.join(DOWNLOAD_DIR, "%d_%s" % (i, meta["n"])), i + 1
        with open(dest, "wb") as f:
            f.write(data)
        self.out("✓ Tersimpan: %s" % dest)

    # -- tampilan --
    def preview(self, m):
        if m["kind"] == "x":
            return "(pesan dihapus)"
        if m["kind"] == "f":
            return "📎 " + safe(json.loads(m["meta"]).get("n", "file"))
        t = safe(m["body"])
        return t if len(t) <= 60 else t[:57] + "..."

    def fmt(self, m):
        mine = m["sender"] == self.me
        meta = json.loads(m["meta"])
        if m["kind"] == "x":
            body = "🗑 pesan ini dihapus"
        elif m["kind"] == "f":
            body = "📎 %s (%s)" % (safe(meta.get("n", "file")), human_size(meta.get("z", 0)))
            if m["body"]:
                body += " - " + safe(m["body"])
            if not mine:
                body += "  [/get %d]" % m["n"]
        else:
            body = safe(m["body"])
        line = "%s #%d %s: %s" % (fmt_time(m["ts"]), m["n"], "kamu" if mine else self.pname(m["sender"]), body)
        if m["exp"]:
            line += " ⏳"
        if mine:
            line += "  " + TICKS.get(m["status"], "")
        if meta.get("r"):
            o = self.db.msg_uid(m["chat"], meta["r"])
            if o:
                line = "   ↩ %s: %s\n%s" % ("kamu" if o["sender"] == self.me else self.pname(o["sender"]),
                                             self.preview(o), line)
        return line

    def os_notify(self, title, text, chat="x"):
        mode = self.db.kv_get("notif", "on")
        if mode == "off" or not self.has_notif:
            return
        if mode == "hide":
            title, text = "wa-cli", "Pesan baru"

        def run():
            try:
                kw = dict(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
                subprocess.run(["termux-notification", "--title", title, "--content", text, "--id", "wacli-" + re.sub(r"\W", "_", chat)], **kw)
                if shutil.which("termux-vibrate"):
                    subprocess.run(["termux-vibrate", "-d", "150"], **kw)
            except Exception:
                pass
        threading.Thread(target=run, daemon=True).start()

    # -- terima --
    def show_new(self, n):
        m = self.db.msg(n)
        if m["chat"] == self.chat:
            self.db.set_status(n, "read")
            if not m["chat"].startswith("g:"):
                self.rc_queue.append((m["sender"], m["uid"]))
            return self.out(self.fmt(m))
        group = m["chat"].startswith("g:")
        who = self.pname(m["sender"]) + (" @" + self.title(m["chat"]) if group else "")
        self.out("📩 %s: %s" % (who, self.preview(m)))
        p = self.db.peer(m["sender"])
        hint = "chat " + (self.title(m["chat"]) if group else m["sender"])
        if not group and not (p and p["nick"]):
            hint += "   (simpan: add %s <nama>)" % m["sender"]
        self.out("     -> " + hint)
        self.os_notify(who, self.preview(m), m["chat"])

    def flush_receipts(self):
        queue, self.rc_queue = self.rc_queue, []
        by = {}
        for s, u in queue:
            by.setdefault(s, []).append(u)
        for s, us in by.items():
            try:
                self.transmit(s, {"t": "rc", "us": us})
            except (ApiFail, KeyChanged, ValueError):
                pass

    def on_payload(self, sender, p):
        t = p.get("t")
        now = int(time.time())
        if t in ("m", "f"):
            uid = str(p.get("u", ""))
            if not UID_RE.match(uid):
                return
            if p.get("g") is not None:
                g = self.db.group(str(p["g"]))
                if not g or sender not in g["members"]:
                    return
                chat = "g:" + g["gid"]
            else:
                chat = sender
            meta, r = {}, p.get("r")
            if isinstance(r, str) and UID_RE.match(r):
                meta["r"] = r
            if t == "f":
                b, k = str(p.get("b", "")), str(p.get("k", ""))
                if not (re.fullmatch(r"[A-Za-z0-9_-]{22}", b) and re.fullmatch(r"[A-Za-z0-9_-]{43}", k)):
                    return
                try:
                    z = int(p.get("z", 0))
                except (TypeError, ValueError):
                    z = 0
                meta.update({"b": b, "k": k, "n": safe_filename(str(p.get("n", "file"))), "z": z})
            try:
                e = int(p.get("e", 0))
            except (TypeError, ValueError):
                e = 0
            e = e if 0 < e <= 30 * 86400 else 0
            n = self.db.msg_add(uid, chat, sender, t, str(p.get("x", ""))[:3000], meta, now, None, "unread",
                                now + e if e else 0)
            if n:
                self.show_new(n)
        elif t == "d":
            self.db.delete_msg(sender, str(p.get("u", "")))
        elif t == "rc" and isinstance(p.get("us"), list):
            self.db.mark_read_uids(sender, [str(u) for u in p["us"]])
        elif t == "gc":
            gid, members = str(p.get("g", "")), p.get("m")
            if not re.fullmatch(r"[0-9a-f]{8}", gid) or not isinstance(members, list) or len(members) > 20:
                return
            members = [str(x) for x in members]
            if not all(ID_RE.match(x) for x in members) or self.me not in members or sender not in members:
                return
            if self.db.group(gid):
                return
            name = re.sub(r"[^\w.\-]", "", str(p.get("n", "grup")))[:20]
            name = name if len(name) >= 2 else "grup"
            if self.db.group_by_name(name):
                name = name[:15] + "_" + gid[:4]
            try:
                self.db.group_set(gid, name, members)
            except sqlite3.IntegrityError:
                return
            self.out("[i] %s menambahkanmu ke grup #%s (%d anggota)" % (self.pname(sender), name, len(members)))
        elif t == "gl":
            g = self.db.group(str(p.get("g", "")))
            if g and sender in g["members"]:
                self.db.group_set(g["gid"], g["name"], [x for x in g["members"] if x != sender])
                self.out("[i] %s keluar dari grup #%s" % (self.pname(sender), g["name"]))

    def process(self, m):
        sender = m["from"]
        if not ID_RE.match(sender):
            return
        p = self.db.peer(sender)
        if p and p["blocked"]:
            return
        try:
            peer = self.ensure_peer(sender)
        except ApiFail as e:
            if e.status == 404:
                return
            raise Retry()
        try:
            payload = self.sec.decrypt(sender, peer["ik"], m["text"])
        except ValueError as e:
            return self.out("[!] Pesan dari %s tidak bisa dibuka (%s)." % (self.pname(sender), e))
        if isinstance(payload, dict):
            self.on_payload(sender, payload)

    def poll_loop(self):
        fails = 0
        while not self.stop.is_set():
            t0 = time.monotonic()
            track = self.db.pending_tracks()
            path = "/messages/%s?after=%d&limit=50&wait=%d" % (self.me, self.last_id, WAIT)
            if track:
                path += "&track=" + ",".join(map(str, track))
            try:
                data = self.api("GET", path, timeout=WAIT + 15)
            except ApiFail as e:
                if e.status == 401:
                    return self.out("[!] Token ditolak server (database server direset?). Hapus profil: "
                                    "rm ~/.wa-cli2/%s.*" % self.profile)
                fails += 1
                if fails == 1:
                    self.out("[!] Koneksi bermasalah: %s -- mencoba lagi otomatis..." % e)
                self.stop.wait(min(30, 2 * fails))
                continue
            if fails:
                self.out("[i] Tersambung kembali.")
                fails = 0
            st = data.get("status", {})
            for sid in track:
                if st.get(str(sid), "delivered") == "delivered":
                    self.db.mark_delivered(sid)
            try:
                for m in data["messages"]:
                    self.process(m)
                    self.last_id = max(self.last_id, m["id"])
                    self.cfg["last_id"] = self.last_id
                self.save_cfg()
            except Retry:
                self.save_cfg()
                self.stop.wait(3)
            self.flush_receipts()
            self.db.purge_expired(time.time())
            if time.monotonic() - t0 < 0.3:
                self.stop.wait(0.5)

    # -- command --
    def need_peer(self, arg):
        if not arg.strip():
            self.out("[!] Sebutkan ID atau nama kontak.")
            return None
        return self.resolve(arg, groups=False)

    def cmd_me(self, _):
        self.out("ID       : %s\nNickname : %s\nServer   : %s\nProfil   : %s\nKunci app: %s"
                 % (self.me, self.cfg["nickname"], self.cfg["server"], self.profile,
                    "AKTIF 🔒" if self.db.locked else "mati (aktifkan: lock on)"))

    def cmd_add(self, arg):
        parts = arg.split(None, 1)
        cid = parts[0] if parts else self.read("ID kontak (10 digit): ").strip()
        if not ID_RE.match(cid) or cid == self.me:
            return self.out("[!] ID harus 10 digit angka dan bukan ID kamu.")
        nick = parts[1].strip() if len(parts) > 1 else self.read("Nama kontak (kosong = nama asli): ").strip()
        try:
            u = self.api("GET", "/users/" + cid)
        except ApiFail as e:
            return self.out("[!] %s" % e)
        p = self.db.peer(cid)
        if p and p["ik"] and p["ik"] != u["ik"]:
            return self.out("[!] KUNCI BERUBAH untuk %s. Gunakan: trust %s" % (cid, cid))
        nick = safe(nick or u["nickname"])[:30].strip() or cid
        self.db.peer_set(cid, nick=nick, snick=safe(u["nickname"]), ik=u["ik"])
        self.out("✓ Kontak disimpan: %s (%s)\n  Lanjut: verify %s (cocokkan safety number)" % (nick, cid, cid))

    def cmd_contacts(self, _):
        rows = self.db.contacts()
        if not rows:
            return self.out("Belum ada kontak. Tambah: add <id> <nama>")
        for uid, nick in rows:
            p = self.db.peer(uid)
            self.out("  %-20s %s %s%s" % (nick, uid, "✓" if p["verified"] else " ", " [diblokir]" if p["blocked"] else ""))

    def cmd_chat(self, arg):
        chat = self.resolve(arg) if arg.strip() else None
        if not chat:
            return self.out("Pemakaian: chat <id|nama|#grup>") if not arg.strip() else None
        if chat == self.me:
            return self.out("[!] Tidak bisa chat dengan diri sendiri.")
        head = ""
        if chat.startswith("g:"):
            g = self.db.group(chat[2:])
            head = "grup, %d anggota" % len(g["members"])
        else:
            try:
                p = self.ensure_peer(chat, check=True)
                head = "🔒 terverifikasi" if p["verified"] else "🔓 belum diverifikasi (ketik: verify %s)" % chat
            except KeyChanged as e:
                return self.out("[!] %s" % e)
            except ApiFail as e:
                if not (self.db.peer(chat) or {}).get("ik"):
                    return self.out("[!] %s" % e)
                head = "offline, memakai kunci tersimpan"
        exp = int(self.db.kv_get("exp:" + chat, 0))
        self.out("--- %s | %s%s | /help ---" % (self.title(chat), head, " | ⏳ %ds" % exp if exp else ""))
        for m in self.db.msgs(chat, 20):
            self.out(self.fmt(m))
        for r in self.db.unread(chat):
            if not chat.startswith("g:"):
                self.rc_queue.append((r["sender"], r["uid"]))
        self.db.mark_read(chat)
        self.chat = chat
        self.flush_receipts()

    def cmd_send(self, arg):
        parts = arg.split(None, 1)
        if len(parts) < 2:
            return self.out("Pemakaian: send <id|nama|#grup> <pesan>")
        chat = self.resolve(parts[0])
        if chat:
            m = self.send_message(chat, parts[1])
            if m and m["status"] != "failed":
                self.out("✓ Terkirim ke %s (#%d)" % (self.title(chat), m["n"]))

    def cmd_status(self, arg):
        uid = self.need_peer(arg)
        if uid:
            try:
                u = self.api("GET", "/users/" + uid)
            except ApiFail as e:
                return self.out("[!] %s" % e)
            self.out("%s: %s" % (self.pname(uid), "🟢 online" if u["online"] else "terakhir dilihat " + fmt_ago(u["last_seen"])))

    def cmd_verify(self, arg):
        uid = self.need_peer(arg)
        if not uid:
            return
        try:
            p = self.ensure_peer(uid, check=True)
        except (ApiFail, KeyChanged) as e:
            return self.out("[!] %s" % e)
        self.out("Safety number kamu & %s:\n\n  %s\n\nBacakan/bandingkan dengan yang tampil di HP dia\n"
                 "(telepon atau ketemu langsung). Harus SAMA persis." % (self.pname(uid),
                                                                          secure.safety_number(self.cfg["ik_pub"], p["ik"])))
        if self.read("Sama persis? [y/N] ").strip().lower() == "y":
            self.db.peer_set(uid, verified=1)
            self.out("✓ %s ditandai terverifikasi." % self.pname(uid))

    def cmd_trust(self, arg):
        uid = self.need_peer(arg)
        if not uid:
            return
        try:
            u = self.api("GET", "/users/" + uid)
        except ApiFail as e:
            return self.out("[!] %s" % e)
        p = self.db.peer(uid)
        if p and p["ik"] == u["ik"]:
            return self.out("Tidak ada perubahan kunci untuk %s." % self.pname(uid))
        self.out("Kunci baru. Safety number: %s" % secure.safety_number(self.cfg["ik_pub"], u["ik"]))
        if self.read("Terima kunci baru & reset sesi enkripsi? [y/N] ").strip().lower() == "y":
            self.db.peer_set(uid, ik=u["ik"], snick=safe(u["nickname"]), verified=0)
            self.db.del_sessions(uid)
            self.out("✓ Kunci diperbarui (belum terverifikasi).")

    def cmd_block(self, arg, on=True):
        uid = self.need_peer(arg)
        if uid:
            try:
                self.api("POST", "/block" if on else "/unblock", {"id": uid})
            except ApiFail as e:
                return self.out("[!] %s" % e)
            self.db.peer_set(uid, blocked=1 if on else 0)
            self.out("✓ %s %s." % (self.pname(uid), "diblokir" if on else "dibuka blokirnya"))

    def cmd_clear(self, arg):
        chat = self.resolve(arg) if arg.strip() else None
        if chat:
            self.db.clear_chat(chat)
            self.out("✓ Riwayat %s dihapus (lokal)." % self.title(chat))

    def cmd_notif(self, arg):
        if arg.strip() in ("on", "hide", "off"):
            self.db.kv_set("notif", arg.strip())
        self.out("Notifikasi: %s%s" % (self.db.kv_get("notif", "on"),
                                      "" if self.has_notif else "  (termux-api belum terpasang)"))

    def cmd_group(self, arg):
        parts = arg.split()
        sub = parts[0].lower() if parts else ""
        if sub == "new" and len(parts) >= 3:
            name = parts[1]
            if not GNAME_RE.match(name) or self.db.group_by_name(name):
                return self.out("[!] Nama grup 2-20 karakter (huruf/angka/._-) dan belum dipakai.")
            ids = []
            for t in parts[2:]:
                uid = self.resolve(t, groups=False)
                if not uid:
                    return
                if uid != self.me and uid not in ids:
                    ids.append(uid)
            if not ids or len(ids) > 19:
                return self.out("[!] Anggota 1-19 orang.")
            for uid in ids:
                try:
                    self.ensure_peer(uid)
                except (ApiFail, KeyChanged) as e:
                    return self.out("[!] %s" % e)
            gid, members = secrets.token_hex(4), [self.me] + ids
            self.db.group_set(gid, name, members)
            for uid in ids:
                try:
                    self.transmit(uid, {"t": "gc", "g": gid, "n": name, "m": members})
                except (ApiFail, KeyChanged, ValueError) as e:
                    self.out("[!] Gagal mengundang %s: %s" % (self.pname(uid), e))
            self.out("✓ Grup #%s dibuat (%d anggota). Buka: chat #%s" % (name, len(members), name))
        elif sub == "list":
            gs = self.db.groups()
            for g in gs:
                self.out("  #%-20s %s" % (g["name"], ", ".join(self.pname(m) if m != self.me else "kamu" for m in g["members"])))
            if not gs:
                self.out("Belum ada grup. Buat: group new <nama> <id|nama> ...")
        elif sub == "leave" and len(parts) == 2:
            g = self.db.group_by_name(parts[1].lstrip("#"))
            if not g:
                return self.out("[!] Grup tidak ditemukan.")
            for uid in g["members"]:
                if uid != self.me:
                    try:
                        self.transmit(uid, {"t": "gl", "g": g["gid"]})
                    except (ApiFail, KeyChanged, ValueError):
                        pass
            self.db.group_del(g["gid"])
            self.out("✓ Keluar dari grup #%s." % g["name"])
        else:
            self.out("Pemakaian: group new <nama> <id|nama>... | group list | group leave <nama>")

    def cmd_backup(self, arg):
        path = os.path.expanduser(arg.strip() or "wa-backup.wabk")
        pw = getpass.getpass("Password backup (min 8 karakter): ")
        if len(pw) < 8 or pw != getpass.getpass("Ulangi password: "):
            return self.out("[!] Password terlalu pendek / tidak sama.")
        with open(cfg_path(self.profile), "r", encoding="utf-8") as f:
            disk_cfg = json.load(f)
        blob = json.dumps({"cfg": disk_cfg, "db": b64e(self.db.snapshot())}).encode("utf-8")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(secure.seal_backup(pw, blob))
        self.out("✓ Backup tersimpan: %s\n  Jangan dipakai di dua HP sekaligus (sesi enkripsi akan bentrok)." % path)

    def cmd_restore(self, arg):
        if not arg.strip():
            return self.out("Pemakaian: restore <file>")
        try:
            with open(os.path.expanduser(arg.strip()), "rb") as f:
                blob = f.read()
        except OSError as e:
            return self.out("[!] %s" % e.strerror)
        if self.read("Ini MENIMPA akun profil '%s'. Lanjut? [y/N] " % self.profile).strip().lower() != "y":
            return
        try:
            data = json.loads(secure.open_backup(getpass.getpass("Password backup: "), blob))
            cfg, dbbytes = data["cfg"], b64d(data["db"])
            assert all(k in cfg for k in ("server", "id", "ik_pub"))
        except (ValueError, KeyError, AssertionError) as e:
            return self.out("[!] Backup tidak valid: %s" % e)
        tmp = db_path(self.profile) + ".tmp"
        with open(tmp, "wb") as f:
            f.write(dbbytes)
        os.replace(tmp, db_path(self.profile))
        save_config(self.profile, cfg, strip=False)
        self.out("✓ Restore selesai. Jalankan ulang client.")
        return "quit"

    def cmd_lock(self, arg):
        sub = arg.strip().lower()
        if not sub:
            return self.out("Kunci aplikasi: %s\n  lock on | lock off | lock passwd" % ("AKTIF 🔒" if self.db.locked else "mati"))
        if sub == "on":
            if self.db.locked:
                return self.out("Sudah aktif.")
            self.db.enable_lock(ask_new_password())
            return self.out("✓ Kunci aplikasi aktif: pesan, kontak, sesi, token & kunci privat kini terenkripsi.\n"
                            "  Password diminta tiap client dibuka. Lupa password = data TIDAK bisa dipulihkan.")
        if not self.db.locked:
            return self.out("Kunci aplikasi belum aktif. Aktifkan: lock on")
        try:
            self.db.verify_password(getpass.getpass("Password saat ini: "))
        except ValueError:
            return self.out("[!] Password salah.")
        if sub == "off":
            self.db.disable_lock()
            self.out("✓ Kunci aplikasi dimatikan (data lokal kembali tidak terenkripsi).")
        elif sub == "passwd":
            old = getpass.getpass("Ulangi password saat ini: ")
            try:
                self.db.change_password(old, ask_new_password())
            except ValueError:
                return self.out("[!] Password salah.")
            self.out("✓ Password diganti.")
        else:
            self.out("Pemakaian: lock on | lock off | lock passwd")

    def cmd_server(self, arg):
        if arg.strip():
            self.cfg["server"] = normalize_url(arg)
            self.save_cfg()
        self.out("Server: %s" % self.cfg["server"])

    def cmd_get(self, arg):
        self.get_file(int(arg) if arg.strip().isdigit() else None)

    # -- di dalam chat --
    def chat_cmd(self, cmd, rest):
        if cmd in ("back", "q", "exit"):
            self.out("Keluar dari chat.")
            self.chat = None
        elif cmd == "help":
            self.out(CHAT_HELP)
        elif cmd == "reply":
            n, _, text = rest.partition(" ")
            if n.isdigit() and text.strip():
                self.chat_send(text.strip(), int(n))
            else:
                self.out("Pemakaian: /reply <no> <teks>")
        elif cmd == "del":
            m = self.db.msg(int(rest)) if rest.isdigit() else None
            if not m or m["chat"] != self.chat or m["sender"] != self.me or m["kind"] == "x":
                return self.out("[!] Hanya bisa menghapus pesanmu sendiri di chat ini: /del <no>")
            self.broadcast(self.chat, {"t": "d", "u": m["uid"]})
            self.db.delete_msg(self.me, m["uid"])
            self.out("✓ Pesan #%d dihapus." % m["n"])
        elif cmd == "file":
            path, _, caption = rest.partition(" ")
            self.send_file(self.chat, path, caption.strip()) if path else self.out("Pemakaian: /file <path> [teks]")
        elif cmd == "get":
            self.cmd_get(rest)
        elif cmd == "exp":
            v = parse_duration(rest)
            if v is None:
                return self.out("Pemakaian: /exp off | 30s | 5m | 1h | 1d (maks 30d)")
            self.db.kv_set("exp:" + self.chat, v)
            self.out("⏳ Pesan yang kamu kirim %s." % ("hilang otomatis setelah %ds" % v if v else "tidak lagi hilang otomatis"))
        elif cmd == "info":
            if self.chat.startswith("g:"):
                g = self.db.group(self.chat[2:])
                self.out("Grup #%s: %s" % (g["name"], ", ".join(self.pname(m) if m != self.me else "kamu" for m in g["members"])))
            else:
                p = self.db.peer(self.chat) or {}
                self.out("%s (%s) | %s | sesi aktif: %d" % (self.pname(self.chat), self.chat,
                         "terverifikasi" if p.get("verified") else "BELUM diverifikasi", len(self.db.sessions(self.chat))))
        else:
            self.out("Command chat tidak dikenal. Ketik /help")

    def chat_send(self, text, reply_n=None):
        if self.tty:
            sys.stdout.write("\033[1A\r\033[K")
            sys.stdout.flush()
        m = self.send_message(self.chat, text, reply_n)
        if m:
            self.out(self.fmt(m))

    # -- loop utama --
    def handle_line(self, line):
        if self.chat:
            if line.startswith("/"):
                cmd, _, rest = line[1:].partition(" ")
                self.chat_cmd(cmd.lower(), rest.strip())
            else:
                self.chat_send(line)
            return True
        cmd, _, arg = line.partition(" ")
        cmd, arg = cmd.lower(), arg.strip()
        if cmd in ("exit", "quit", "q"):
            return False
        table = {"help": lambda a: self.out(HELP), "me": self.cmd_me, "add": self.cmd_add,
                 "contacts": self.cmd_contacts, "chat": self.cmd_chat, "send": self.cmd_send,
                 "status": self.cmd_status, "verify": self.cmd_verify, "trust": self.cmd_trust,
                 "block": lambda a: self.cmd_block(a, True), "unblock": lambda a: self.cmd_block(a, False),
                 "clear": self.cmd_clear, "notif": self.cmd_notif, "group": self.cmd_group,
                 "lock": self.cmd_lock, "backup": self.cmd_backup, "restore": self.cmd_restore, "server": self.cmd_server,
                 "get": self.cmd_get}
        fn = table.get(cmd)
        if not fn:
            self.out("Command tidak dikenal. Ketik 'help'.")
            return True
        return fn(arg) != "quit"

    def run(self):
        print("=" * 36)
        print(" wa-cli v2.1 (E2E: X25519 + Double Ratchet + AES-256-GCM)")
        print(" ID       : %s" % self.me)
        print(" Nickname : %s" % self.cfg["nickname"])
        print(" Server   : %s" % self.cfg["server"])
        print("=" * 36)
        try:
            self.api("GET", "/users/" + self.me)
        except ApiFail as e:
            if e.status == 401:
                return print("[!] Akun tidak dikenal server (DB server direset?). Hapus profil: rm ~/.wa-cli2/%s.*" % self.profile)
            print("[!] %s\n    Poller akan mencoba lagi otomatis." % e)
        for chat, c in self.db.unread_summary():
            print("📩 %d pesan belum dibaca dari %s" % (c, self.title(chat)))
        print("Ketik 'help' untuk daftar command.\n")
        threading.Thread(target=self.poll_loop, daemon=True).start()
        while not self.stop.is_set():
            try:
                line = self.read().strip()
            except EOFError:
                break
            except KeyboardInterrupt:
                print("\n(ketik 'exit' untuk keluar)")
                continue
            if line and not self.handle_line(line):
                break
        self.stop.set()
        print("Sampai jumpa!")


def main():
    ap = argparse.ArgumentParser(description="wa-cli client v2.1")
    ap.add_argument("-s", "--server", help="URL server, mis. https://xxxx.trycloudflare.com")
    ap.add_argument("-p", "--profile", default="default", help="nama profil akun (default: default)")
    ap.add_argument("-i", "--invite", help="kode undangan dari pemilik server (untuk pendaftaran)")
    args = ap.parse_args()
    if not PROFILE_RE.match(args.profile):
        sys.exit("Nama profil hanya boleh huruf/angka/_/- (maks 30 karakter).")
    override = normalize_url(args.server or os.environ.get("WA_SERVER"))
    try:
        store = Store(db_path(args.profile))
        if store.locked and not unlock_store(store):
            sys.exit("Gagal membuka kunci aplikasi.")
        cfg = load_config(args.profile)
        if cfg is None:
            server = override or normalize_url(input("URL server [%s]: " % DEFAULT_SERVER)) or DEFAULT_SERVER
            cfg = do_register(server, args.invite or os.environ.get("WA_INVITE"))
            if cfg is None:
                sys.exit("Gagal daftar. Cek server/tunnel/kode undangan lalu coba lagi.")
            store.kv_set("sec", json.dumps({k: cfg[k] for k in SECRET_KEYS}))
            save_config(args.profile, cfg)
            print("✓ Terdaftar. ID kamu: %s" % cfg["id"])
            if not store.locked and input("Pasang kunci aplikasi (password) sekarang? [y/N] ").strip().lower() == "y":
                store.enable_lock(ask_new_password())
                print("✓ Kunci aplikasi aktif.")
        else:
            if any(k in cfg for k in SECRET_KEYS):  # migrasi dari v2.0: pindahkan rahasia ke database
                if not store.kv_get("sec"):
                    store.kv_set("sec", json.dumps({k: cfg[k] for k in SECRET_KEYS if k in cfg}))
                save_config(args.profile, cfg)
            sec = json.loads(store.kv_get("sec") or "{}")
            if not all(k in sec for k in SECRET_KEYS):
                sys.exit("Profil rusak (rahasia tidak ditemukan). Hapus: rm ~/.wa-cli2/%s.*" % args.profile)
            cfg.update(sec)
            if override and override != cfg["server"]:
                cfg["server"] = override
                save_config(args.profile, cfg)
        App(args.profile, cfg, store).run()
    except (KeyboardInterrupt, EOFError):
        print("\nSampai jumpa!")


if __name__ == "__main__":
    main()
