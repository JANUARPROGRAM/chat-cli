#!/usr/bin/env python3
"""Pulihkan akun di database server dari profil client di HP yang sama.

Dipakai kalau database server hilang / ter-reset ("Akun tidak dikenal server") tapi data client
(~/.wa-cli2) masih ada. Akun didaftarkan ulang dengan ID, nickname, kunci publik, dan token yang sama,
jadi riwayat chat dan sesi enkripsi tetap berlaku.

  python server/recover_users.py          # semua profil di ~/.wa-cli2
  python server/recover_users.py a b      # hanya profil tertentu
Hentikan server dulu (bash stop-all.sh), jalankan ini, lalu nyalakan server lagi.
"""
import getpass
import glob
import json
import os
import sqlite3
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "cli"))
import database as db  # noqa: E402
from store import Store  # noqa: E402

CFG_DIR = os.path.join(os.path.expanduser("~"), ".wa-cli2")


def main():
    names = sys.argv[1:] or sorted(os.path.basename(p)[:-5] for p in glob.glob(os.path.join(CFG_DIR, "*.json")))
    if not names:
        sys.exit("Tidak ada profil di %s" % CFG_DIR)
    db.init_db()
    conn = db.connect()
    print("Database server:", db.DB_PATH)
    done = 0
    for name in names:
        cfg_file = os.path.join(CFG_DIR, name + ".json")
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except (OSError, ValueError):
            print("[%s] dilewati: config tidak terbaca" % name)
            continue
        store = Store(os.path.join(CFG_DIR, name + ".db"))
        if store.locked:
            try:
                store.unlock(getpass.getpass("[%s] password kunci aplikasi: " % name))
            except ValueError:
                print("[%s] dilewati: password salah" % name)
                continue
        token = json.loads(store.kv_get("sec") or "{}").get("token") or cfg.get("token")
        if not token or not all(k in cfg for k in ("id", "nickname", "ik_pub")):
            print("[%s] dilewati: data akun tidak lengkap" % name)
            continue
        with conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO users (id, nickname, ik, token_hash, created_at) VALUES (?, ?, ?, ?, ?)",
                (cfg["id"], cfg["nickname"], cfg["ik_pub"], db.hash_token(token), int(time.time())))
        # ID pesan di database baru mulai dari 1: reset penanda supaya pesan baru tidak terlewat
        cfg["last_id"] = 0
        with open(cfg_file, "w", encoding="utf-8") as f:
            json.dump(cfg, f)
        os.chmod(cfg_file, 0o600)
        store.db.execute("UPDATE msgs SET srv_id = NULL")
        store.db.commit()
        print("[%s] %s (%s): %s" % (name, cfg["nickname"], cfg["id"], "dipulihkan" if cur.rowcount else "sudah ada di server"))
        done += cur.rowcount
    conn.close()
    print("Selesai: %d akun dipulihkan. Nyalakan server lagi (bash start-all.sh)." % done)


if __name__ == "__main__":
    main()
