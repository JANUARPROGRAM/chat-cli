#!/usr/bin/env python3
"""Admin lokal wa-cli: kelola kode undangan & user. Jalankan di HP tempat server berjalan.

  python server/admin.py invite            # 1 kode, 1x pakai, berlaku 24 jam
  python server/admin.py invite -n 5 -t 72 # 5x pakai, berlaku 72 jam
  python server/admin.py invites           # daftar kode (hanya hash singkat, kode asli tak tersimpan)
  python server/admin.py revoke a1b2c3     # cabut kode berdasarkan id
  python server/admin.py users             # daftar user
  python server/admin.py mode [open|invite]
"""
import argparse
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import database as db  # noqa: E402


def fmt(ts):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts)) if ts else "-"


def main():
    ap = argparse.ArgumentParser(description="Admin wa-cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("invite", help="buat kode undangan")
    p.add_argument("-n", "--uses", type=int, default=1, help="berapa kali bisa dipakai (default 1)")
    p.add_argument("-t", "--hours", type=float, default=24, help="masa berlaku, jam (default 24)")
    sub.add_parser("invites", help="daftar kode undangan")
    p = sub.add_parser("revoke", help="cabut kode undangan")
    p.add_argument("id", help="id kode dari 'invites' (4-16 karakter hex)")
    sub.add_parser("users", help="daftar user")
    p = sub.add_parser("mode", help="lihat/ubah mode pendaftaran")
    p.add_argument("value", nargs="?", choices=["open", "invite"])
    a = ap.parse_args()

    db.init_db()
    conn = db.connect()
    try:
        if a.cmd == "invite":
            if not 1 <= a.uses <= 1000 or not 0.01 <= a.hours <= 24 * 365:
                sys.exit("Nilai -n harus 1-1000 dan -t 0.01-8760.")
            code = db.create_invite(conn, a.uses, a.hours)
            print("Kode undangan: %s   (%dx pakai, berlaku %g jam)" % (code, a.uses, a.hours))
            print("Kirim ke temanmu lewat jalur aman. Kode ini tidak tersimpan utuh di server.")
        elif a.cmd == "invites":
            rows = db.list_invites(conn)
            now = int(time.time())
            for r in rows:
                state = "aktif" if r["uses"] < r["max_uses"] and r["expires_at"] > now else "habis/kedaluwarsa"
                print("%s  dipakai %d/%d  berlaku s/d %s  [%s]" % (
                    r["hash"][:8], r["uses"], r["max_uses"], fmt(r["expires_at"]), state))
            if not rows:
                print("Belum ada kode. Buat: python server/admin.py invite")
        elif a.cmd == "revoke":
            if not re.fullmatch(r"[0-9a-f]{4,16}", a.id):
                sys.exit("id harus 4-16 karakter hex (lihat 'invites').")
            print("%d kode dicabut." % db.revoke_invite(conn, a.id))
        elif a.cmd == "users":
            for r in db.list_users(conn):
                print("%s  %-20s daftar %s  terakhir online %s" % (
                    r["id"], r["nickname"], fmt(r["created_at"]), fmt(r["last_seen"])))
        elif a.cmd == "mode":
            if a.value:
                db.set_setting(conn, "registration", a.value)
            print("Mode pendaftaran: %s" % db.get_setting(conn, "registration", "invite"))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
