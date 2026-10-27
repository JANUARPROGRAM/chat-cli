"""Kripto wa-cli v2.1: identitas X25519, X3DH-lite, Double Ratchet, AES-256-GCM, kunci aplikasi."""
import base64
import copy
import hashlib
import hmac
import json
import os
import struct
import sys
import threading

try:
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
except ImportError:
    sys.exit("Butuh paket 'cryptography'. Jalankan: pkg install python-cryptography")

PREFIX = "e2:"
MAX_SKIP = 100
MAX_PLAIN = 2800


def b64e(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def b64d(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


# ---------- primitif ----------
def gen_keypair():
    k = X25519PrivateKey.generate()
    priv = k.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                           serialization.NoEncryption())
    pub = k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return b64e(priv), b64e(pub)


def dh(priv, pub):
    return X25519PrivateKey.from_private_bytes(b64d(priv)).exchange(X25519PublicKey.from_public_bytes(b64d(pub)))


def hkdf(ikm, salt, info, n):
    return HKDF(algorithm=hashes.SHA256(), length=n, salt=salt, info=info).derive(ikm)


def kdf_rk(rk, dh_out):
    out = hkdf(dh_out, b64d(rk), b"wa-cli/rk", 64)
    return b64e(out[:32]), b64e(out[32:])


def kdf_ck(ck):
    c = b64d(ck)
    return b64e(hmac.new(c, b"\x02", "sha256").digest()), hmac.new(c, b"\x01", "sha256").digest()


def aead_keys(mk):
    out = hkdf(mk, None, b"wa-cli/mk", 44)
    return out[:32], out[32:]


def pad(data):
    data = struct.pack(">H", len(data)) + data
    return data + b"\0" * (-len(data) % 128)


def unpad(data):
    n = struct.unpack(">H", data[:2])[0]
    if n > len(data) - 2:
        raise ValueError("padding rusak")
    return data[2:2 + n]


def sid_of(ek_pub):
    return b64e(hashlib.sha256(b64d(ek_pub)).digest()[:8])


# ---------- sesi ----------
def _new_state(sid, role, rk, dhs, dhr, cks, ek, acked):
    return {"sid": sid, "role": role, "ek": ek, "acked": acked, "rk": rk, "dhs": list(dhs), "dhr": dhr,
            "cks": cks, "ckr": None, "ns": 0, "nr": 0, "pn": 0, "skipped": {}}


def start_initiator(my_ik_priv, peer_ik):
    ek_priv, ek_pub = gen_keypair()
    sk = hkdf(dh(my_ik_priv, peer_ik) + dh(ek_priv, peer_ik), b"\0" * 32, b"wa-cli/x3dh", 32)
    dhs = gen_keypair()
    rk, cks = kdf_rk(b64e(sk), dh(dhs[0], peer_ik))
    return _new_state(sid_of(ek_pub), "i", rk, dhs, peer_ik, cks, ek_pub, False)


def start_responder(my_ik_priv, my_ik_pub, peer_ik, ek_pub):
    sk = hkdf(dh(my_ik_priv, peer_ik) + dh(my_ik_priv, ek_pub), b"\0" * 32, b"wa-cli/x3dh", 32)
    return _new_state(sid_of(ek_pub), "r", b64e(sk), (my_ik_priv, my_ik_pub), None, None, None, True)


def ratchet_encrypt(st, plaintext, ad):
    st["cks"], mk = kdf_ck(st["cks"])
    flags = 0 if st["acked"] else 1
    hdr = b64d(st["sid"]) + bytes([flags]) + b64d(st["dhs"][1]) + struct.pack(">HH", st["pn"], st["ns"])
    if flags:
        hdr += b64d(st["ek"])
    key, nonce = aead_keys(mk)
    ct = AESGCM(key).encrypt(nonce, pad(plaintext), ad + hdr)
    st["ns"] += 1
    return hdr + ct


def parse_header(data):
    if len(data) < 45 + 16:
        raise ValueError("pesan terlalu pendek")
    sid, flags, dhp = data[:8], data[8], data[9:41]
    pn, n = struct.unpack(">HH", data[41:45])
    off, ek = 45, None
    if flags & 1:
        ek, off = data[45:77], 77
        if len(data) < off + 16:
            raise ValueError("pesan terlalu pendek")
    return sid, ek, dhp, pn, n, off


def _skip(s, until):
    if s["ckr"] is None:
        return
    if until - s["nr"] > MAX_SKIP:
        raise ValueError("terlalu banyak pesan terlewat")
    while s["nr"] < until:
        s["ckr"], mk = kdf_ck(s["ckr"])
        s["skipped"]["%s:%d" % (s["dhr"], s["nr"])] = b64e(mk)
        s["nr"] += 1
    while len(s["skipped"]) > 2 * MAX_SKIP:
        s["skipped"].pop(next(iter(s["skipped"])))


def _dh_ratchet(s, dh_pub):
    s["pn"], s["ns"], s["nr"], s["dhr"] = s["ns"], 0, 0, dh_pub
    s["rk"], s["ckr"] = kdf_rk(s["rk"], dh(s["dhs"][0], dh_pub))
    s["dhs"] = list(gen_keypair())
    s["rk"], s["cks"] = kdf_rk(s["rk"], dh(s["dhs"][0], dh_pub))


def ratchet_decrypt(st, data, ad):
    """Atomik: state hanya berubah kalau dekripsi sukses."""
    _, _, dhp, pn, n, off = parse_header(data)
    hdr, ct = data[:off], data[off:]
    s = copy.deepcopy(st)
    dh_pub = b64e(dhp)
    stored = s["skipped"].pop("%s:%d" % (dh_pub, n), None)
    if stored is not None:
        mk = b64d(stored)
    else:
        if s["dhr"] != dh_pub:
            _skip(s, pn)
            _dh_ratchet(s, dh_pub)
        _skip(s, n)
        if s["ckr"] is None:
            raise ValueError("state tidak valid")
        s["ckr"], mk = kdf_ck(s["ckr"])
        s["nr"] += 1
    key, nonce = aead_keys(mk)
    try:
        pt = unpad(AESGCM(key).decrypt(nonce, ct, ad + hdr))
    except InvalidTag:
        raise ValueError("gagal dekripsi")
    s["acked"] = True
    st.clear()
    st.update(s)
    return pt


class Secure:
    """Lapisan tingkat tinggi: pilih/buat sesi per kontak, simpan state ke store."""

    def __init__(self, store, my_id, ik_priv, ik_pub):
        self.store, self.me, self.ik_priv, self.ik_pub = store, my_id, ik_priv, ik_pub
        self.lock = threading.Lock()  # baca-ubah-simpan state ratchet harus atomik antar thread

    def encrypt(self, peer, peer_ik, payload):
        pt = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        if len(pt) > MAX_PLAIN:
            raise ValueError("Pesan terlalu panjang")
        with self.lock:
            sessions = self.store.sessions(peer)
            if sessions:
                st = max(sessions.values(), key=lambda x: (x.get("rx", 0), x["sid"]))  # sesi paling baru aktif
            else:
                st = start_initiator(self.ik_priv, peer_ik)
                st["rx"] = 1
            wire = ratchet_encrypt(st, pt, ("%s>%s" % (self.me, peer)).encode())
            self.store.save_session(peer, st)  # simpan SEBELUM kirim: kunci pesan tidak boleh dipakai ulang
        return PREFIX + b64e(wire)

    def decrypt(self, peer, peer_ik, wire):
        if not wire.startswith(PREFIX):
            raise ValueError("bukan pesan e2")
        data = b64d(wire[len(PREFIX):])
        sid, ek, *_ = parse_header(data)
        sid_s = b64e(sid)
        with self.lock:
            sessions = self.store.sessions(peer)
            st = sessions.get(sid_s)
            if st is None:
                if ek is None:
                    raise ValueError("sesi tidak dikenal")
                if sid_of(b64e(ek)) != sid_s:
                    raise ValueError("header tidak valid")
                st = start_responder(self.ik_priv, self.ik_pub, peer_ik, b64e(ek))
            pt = ratchet_decrypt(st, data, ("%s>%s" % (peer, self.me)).encode())
            st["rx"] = max([x.get("rx", 0) for x in sessions.values()], default=0) + 1
            self.store.save_session(peer, st)
        return json.loads(pt.decode("utf-8"))


# ---------- utilitas ----------
def safety_number(ik_a, ik_b):
    a, b = sorted([ik_a, ik_b])
    h = hashlib.sha256(b"wa-cli/safety" + b64d(a) + b64d(b)).digest()
    n = "%030d" % (int.from_bytes(h, "big") % 10 ** 30)
    return " ".join(n[i:i + 5] for i in range(0, 30, 5))


def file_encrypt(data):
    key, nonce = os.urandom(32), os.urandom(12)
    return b64e(key), nonce + AESGCM(key).encrypt(nonce, data, b"wa-cli/file")


def file_decrypt(key_b64, blob):
    try:
        return AESGCM(b64d(key_b64)).decrypt(blob[:12], blob[12:], b"wa-cli/file")
    except (InvalidTag, ValueError):
        raise ValueError("file rusak / kunci salah")


# ---------- kunci aplikasi: enkripsi data lokal ----------
def field_enc(key, label, text):
    nonce = os.urandom(12)
    return "x1:" + b64e(nonce + AESGCM(key).encrypt(nonce, text.encode("utf-8"), label.encode()))


def field_dec(key, label, blob):
    try:
        raw = b64d(blob[3:])
        return AESGCM(key).decrypt(raw[:12], raw[12:], label.encode()).decode("utf-8")
    except (InvalidTag, ValueError):
        raise ValueError("data lokal rusak atau kunci salah")


def _kek(password, salt):
    return Scrypt(salt=salt, length=32, n=2 ** 16, r=8, p=1).derive(password.encode("utf-8"))


def lock_wrap(password, master):
    """Bungkus kunci utama (32 byte) dengan password. Return dict untuk disimpan."""
    salt, nonce = os.urandom(16), os.urandom(12)
    return {"salt": b64e(salt), "nonce": b64e(nonce),
            "wk": b64e(AESGCM(_kek(password, salt)).encrypt(nonce, master, b"wa-cli/lock"))}


def lock_unwrap(password, meta):
    try:
        return AESGCM(_kek(password, b64d(meta["salt"]))).decrypt(b64d(meta["nonce"]), b64d(meta["wk"]), b"wa-cli/lock")
    except (InvalidTag, ValueError, KeyError):
        raise ValueError("password salah")


def seal_backup(password, data):
    salt, nonce = os.urandom(16), os.urandom(12)
    key = Scrypt(salt=salt, length=32, n=2 ** 15, r=8, p=1).derive(password.encode("utf-8"))
    return b"WACLIBK1" + salt + nonce + AESGCM(key).encrypt(nonce, data, b"WACLIBK1")


def open_backup(password, blob):
    if blob[:8] != b"WACLIBK1" or len(blob) < 52:
        raise ValueError("bukan file backup wa-cli")
    key = Scrypt(salt=blob[8:24], length=32, n=2 ** 15, r=8, p=1).derive(password.encode("utf-8"))
    try:
        return AESGCM(key).decrypt(blob[24:36], blob[36:], b"WACLIBK1")
    except InvalidTag:
        raise ValueError("password salah / file rusak")
