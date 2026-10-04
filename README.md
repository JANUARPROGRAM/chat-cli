## Daftar isi
1. [Apa itu wa-cli?](#id-what) · 2. [Fitur](#id-features) · 3. [Cara kerja](#id-how) · 4. [Kebutuhan](#id-req) · 5. [Mulai cepat](#id-quick)
6. [Instalasi lengkap](#id-install) · 7. [Menjalankan server](#id-server) · 8. [Memakai client](#id-client) · 9. [Daftar command](#id-cmds)
10. [Struktur project](#id-layout) · 11. [Konfigurasi](#id-config) · 12. [Keamanan secara mendalam](#id-security) · 13. [Referensi API](#id-api)
14. [Batas & masa simpan](#id-limits) · 15. [Cloudflare Tunnel](#id-tunnel) · 16. [Update & reset](#id-update) · 17. [Pemecahan masalah](#id-trouble)
18. [FAQ](#id-faq) · 19. [Belum ada](#id-todo) · 20. [Riwayat versi](#id-changelog) · 21. [Penafian](#id-disclaimer)

<a id="id-what"></a>
## 1. Apa itu wa-cli?

**wa-cli** adalah aplikasi chat berbasis terminal yang dihosting sendiri dan cara kerjanya mirip messenger (kontak, chat 1:1, grup, kirim file, centang dibaca, pesan hilang otomatis) dengan **enkripsi end-to-end**.

- **Server** hanyalah server HTTP Python + SQLite. Ia berjalan di HP Android lewat **Termux** dan dibuka ke internet dengan **Cloudflare Tunnel** gratis. Tanpa API berbayar, tanpa laptop, tanpa VPS.
- **Client** adalah aplikasi CLI Python yang bisa jalan di Android (Termux), Linux, macOS, atau Windows. Semua proses enkripsi dan dekripsi terjadi **di perangkat kamu**; server hanya menyimpan data acak (ciphertext).
- Ini **bukan** WhatsApp dan tidak memakai API resmi WhatsApp. Ini messenger buatan sendiri yang konsepnya mirip.

<a id="id-features"></a>
## 2. Fitur

| Bidang | Yang kamu dapat |
|---|---|
| Chat | Chat 1:1, pesan masuk langsung lewat long polling, nomor pesan, balas (`/reply`), hapus untuk semua orang (`/del`), ringkasan belum dibaca, notifikasi Android per chat |
| Grup | Sampai 20 anggota, dibuat dengan satu command, dikirim lewat sesi terenkripsi tiap anggota |
| File | Kirim file terenkripsi sampai 1,5 MB (`/file`, `/get`) |
| Centang | ✓ terkirim · ✓✓ sampai · ✓✓ dibaca · ✗ gagal |
| Kehadiran | `status` menampilkan online / terakhir dilihat |
| Alat privasi | Verifikasi safety number, peringatan kunci berubah, blokir, pesan hilang otomatis (`/exp`) |
| Enkripsi | Kunci identitas X25519, kesepakatan kunci ala X3DH, **Double Ratchet**, **AES-256-GCM**, padding pesan |
| Perlindungan lokal | **Kunci aplikasi**: mengenkripsi pesan, kontak, sesi, token, dan kunci privat di HP dengan password |
| Cadangan | Backup / restore terenkripsi password |
| Kontrol akses | **Kode undangan**: tidak ada yang bisa daftar tanpa kode dari kamu |
| Operasional | `start-all.sh` menjalankan server + tunnel di tmux dengan restart otomatis dan menampilkan URL publik |
| Dependensi | Server: hanya Python standard library. Client: Python + `cryptography` |

<a id="id-how"></a>
## 3. Cara kerja

```
 HP A (client)                             HP B (client)
 ┌─────────────────┐                       ┌─────────────────┐
 │ enkripsi/dekripsi│                      │ enkripsi/dekripsi│
 │ terjadi DI SINI │                       │ terjadi DI SINI │
 └────────┬────────┘                       └────────┬────────┘
          │  HTTPS: hanya ciphertext "e2:..."       │
          ▼                                         ▼
 ┌──────────────────────────────────────────────────────────┐
 │  Cloudflare Tunnel   https://xxxx.trycloudflare.com      │
 └─────────────────────────────┬────────────────────────────┘
                               ▼
              ┌──────────────────────────────────┐
              │ HP server (Termux)               │
              │ server.py  127.0.0.1:8080        │
              │ SQLite: user, kunci publik,      │
              │ ciphertext, undangan             │
              └──────────────────────────────────┘
```

1. Tiap akun punya **ID** (10 digit acak) dan **pasangan kunci** yang dibuat di perangkat. Hanya kunci *publik* yang dikirim ke server.
2. Saat kamu menulis ke seseorang, client menyepakati rahasia bersama dengan kunci publiknya, lalu menjalankan **Double Ratchet**: setiap pesan memakai kunci AES-256-GCM baru dan kunci lama dihapus.
3. Client mengirim ciphertext ke server. Server memeriksa bentuknya (`e2:...`), menyimpannya, dan membangunkan permintaan long-poll milik penerima.
4. Client penerima mengambilnya, mendekripsinya secara lokal, lalu menyimpannya di database lokalnya sendiri.
5. Server menghapus pesan yang sudah terkirim setelah 1 jam. Riwayat chat hanya ada di perangkat kalian.
6. Grup bukan fitur server: pesan grup dikirim terpisah ke tiap anggota lewat sesi 1:1 yang sudah ada. Server bahkan tidak tahu grup itu ada.

<a id="id-req"></a>
## 4. Kebutuhan

- **HP server:** Android + [Termux](https://f-droid.org/packages/com.termux/) (versi F-Droid atau GitHub), kira-kira 100 MB ruang kosong, internet.
- **Paket Termux:** `python`, `python-cryptography`, `cloudflared`, `tmux`, `unzip` (opsional untuk notifikasi: `termux-api` + aplikasi **Termux:API**).
- **Client:** perangkat apa pun dengan Python 3 (dites di 3.12; Termux saat ini membawa 3.12–3.14) dan paket `cryptography`.
- Quick tunnel Cloudflare gratis (tanpa akun). Tidak ada jaminan uptime dan URL berubah tiap tunnel di-restart.

<a id="id-quick"></a>
## 5. Mulai cepat (5 menit)

@@INSTALL@@

Jalankan server dan tunnel (satu perintah):

```bash
bash start-all.sh
```

Ia menampilkan URL publik dan **kode undangan pertama**. Lalu di sesi Termux baru (geser dari tepi kiri layar → *New session*):

```bash
cd ~/wa-cli
bash start-client.sh -s https://URL-KAMU.trycloudflare.com -i XXXX-XXXX
```

Pilih nickname, boleh pasang password kunci aplikasi, lalu ketik `help`. Buat kode undangan lain dengan `bash invite.sh`.

<a id="id-install"></a>
## 6. Instalasi lengkap (Termux)

1. **Pasang Termux** dari F-Droid atau GitHub (versi Play Store sudah usang). Kalau mau notifikasi, pasang **Termux:API** dari *sumber yang sama*; beda sumber akan gagal karena tanda tangan aplikasinya berbeda.
2. **Update dan pasang paket:**
   ```bash
   pkg update -y && pkg upgrade -y
   pkg install -y python python-cryptography cloudflared tmux unzip
   ```
   Kalau muncul pertanyaan soal file konfigurasi saat upgrade, tekan Enter saja.
3. **Izinkan akses penyimpanan** (untuk membaca zip dari Download dan mengirim file dari HP):
   ```bash
   termux-setup-storage
   ```
   Tutup lalu buka lagi Termux kalau folder `~/storage` belum muncul.
4. **Ekstrak project** lalu cek:
   ```bash
   cd ~
   unzip ~/storage/downloads/wa-cli-v2.1.zip
   cd wa-cli
   python -m py_compile server/*.py cli/*.py && echo SEMUA OK
   ```
5. **Pilih `pkg install python-cryptography`**, bukan `pip install cryptography`. Lewat pip kadang harus compile Rust dan gagal di beberapa perangkat (di sebagian perangkat berhasil, tapi paket `pkg` yang paling aman).
6. `sqlite3` sudah **bawaan Python**. Jangan jalankan `pip install sqlite3` (gagal dan tidak perlu). Jangan juga `pip install api`: `api` adalah file lokal `server/api.py`.
7. **Baterai:** Pengaturan Android → Aplikasi → Termux → Baterai → *Tanpa batasan*. `start-all.sh` juga mengambil wake lock lewat `termux-wake-lock`.

<a id="id-server"></a>
## 7. Menjalankan server

### 7.1 Satu perintah: `start-all.sh` (disarankan)

```bash
bash start-all.sh
```

- Membuat sesi tmux bernama `wacli` dengan dua jendela: **server** dan **tunnel**.
- Keduanya restart otomatis kalau crash (server setelah 3 detik, tunnel setelah 5 detik).
- Menunggu URL tunnel sampai 60 detik, menampilkannya, menyimpannya ke `data/tunnel_url.txt`, dan menampilkan kode undangan pertama.
- Log ada di `logs/server.log` dan `logs/tunnel.log` (direset tiap start).

| Keperluan | Perintah |
|---|---|
| Lihat URL tunnel terbaru | `bash url.sh` |
| Buat kode undangan | `bash invite.sh` |
| Lihat log | `tmux attach -t wacli` (ganti jendela: `Ctrl+B` lalu `N`; keluar: `Ctrl+B` lalu `D`) |
| Hentikan semuanya | `bash stop-all.sh` |

> URL tunnel **berubah setiap tunnel di-restart**. Setelah restart jalankan `bash url.sh` dan kasih URL baru ke teman (mereka bisa pakai command `server <url>` di dalam client).

### 7.2 Mode manual (tiga sesi Termux)

@@MANUAL@@

Cek server: `curl http://127.0.0.1:8080/health` harus menampilkan `{"status": "ok", ...}`. Tunnel menampilkan kotak berisi `https://....trycloudflare.com`; itu URL publik kamu. Peringatan `ping_group_range permission denied` tidak berbahaya.

### 7.3 Kode undangan (kontrol pendaftaran)

Secara default server **hanya menerima pendaftar dengan undangan**. Tidak ada yang bisa membuat akun tanpa kode yang valid.

- Saat server pertama kali menyala (belum ada user dan belum ada undangan valid) ia menampilkan `*** KODE UNDANGAN PERTAMA: XXXX-XXXX ***` (berlaku 24 jam, sekali pakai).
- Bentuk kode seperti `K7F2-9QXM`. Di server hanya tersimpan **hash**-nya; kode asli ditampilkan sekali saat dibuat.
- Perintah admin (jalankan di HP server):

@@ADMIN@@

- `mode open` membuat siapa pun bisa daftar tanpa kode. Pakai sebentar saja kalau memang perlu.
- Perlindungan brute force: 10 percobaan daftar per jam per IP, dan kalau terlihat 50 kode salah dalam satu jam, pendaftaran dikunci sementara.

<a id="id-client"></a>
## 8. Memakai client

### 8.1 Pertama kali

```bash
bash start-client.sh -s https://URL-KAMU.trycloudflare.com -i XXXX-XXXX
```

Kamu akan ditanya: URL server (kalau tidak pakai `-s`), kode undangan (kalau tidak pakai `-i`), nickname (2–20 karakter), dan apakah mau mengaktifkan **kunci aplikasi**. Lalu kamu mendapat **ID** 10 digit acak. Ketik `me` untuk melihatnya. Login tersimpan sebagai profil `default`.

Berikutnya cukup `bash start-client.sh`.

### 8.2 Tambah kontak dan verifikasi

```
add 1234567890 Budi         tambah kontak dengan ID dan nama
verify Budi                 cocokkan safety number (lihat di bawah)
contacts                    daftar kontak (✓ = terverifikasi)
```

**Verifikasi itu penting.** `verify` menampilkan safety number 30 digit. Bandingkan dengan layar temanmu lewat *jalur lain* (telepon, ketemu langsung). Kalau angkanya sama, tidak ada pihak yang menyusup di tengah (termasuk server). Jawab `y` untuk menandai kontak sebagai terverifikasi.

### 8.3 Ngobrol

```
chat Budi
```

Kamu melihat 20 pesan terakhir dan header (`🔒 terverifikasi` atau `🔓 belum diverifikasi`). Tinggal ketik untuk mengirim. Pesan diberi nomor seperti `#12`; nomornya lokal di perangkatmu. Pesan masuk dari chat lain muncul sebagai `📩 Nama: cuplikan`.

Di dalam chat:

| Ketikan | Efek |
|---|---|
| `teks` | kirim pesan |
| `/reply 12 teks` | balas pesan #12 (tampil dengan `↩`) |
| `/del 12` | hapus pesan **kamu** #12 untuk semua orang (semampunya) |
| `/file ~/storage/downloads/foto.jpg keterangan` | kirim file, maks 1,5 MB, path tanpa spasi |
| `/get 15` | unduh file di pesan #15 ke `~/wa-downloads/` |
| `/exp 1h` | pesan yang kamu kirim hilang 1 jam setelah dikirim (`off`, `30s`, `5m`, `1h`, `1d`, maks `30d`) |
| `/info` | info lawan chat / grup dan status verifikasi |
| `/back` | keluar dari chat (`/q` dan `/exit` juga bisa) |
| `/help` | bantuan di dalam chat |

> Hati-hati: mengetik `exit` biasa di dalam chat akan **mengirim kata "exit"**. Pakai `/back` dulu.

Centang: `✓` diterima server · `✓✓` sampai ke client penerima · `✓✓ dibaca` penerima membuka/melihatnya · `✗ gagal` tidak bisa terkirim. Pesan grup hanya menampilkan `✓`.

### 8.4 Grup

```
group new tim Budi Cici         buat grup "tim" dengan dua anggota
chat #tim                       buka chat grup
group list                      daftar grup dan anggotanya
group leave tim                 keluar (yang lain diberi tahu)
```

Anggota ditambahkan dengan ID atau nama kontak (1–19 orang lain). Semua anggota menerima undangan terenkripsi secara otomatis. Mengirim ke grup berarti mengirim satu salinan terenkripsi per anggota, jadi satu pesan grup dihitung N−1 pesan untuk batas laju. Belum ada peran admin; siapa pun yang tahu ID kamu bisa memasukkan kamu ke grup, jadi pakai `group leave` atau `block` untuk melawan spam.

### 8.5 File

```
chat Budi
/file ~/storage/downloads/foto.jpg ini ya
```

File dienkripsi dengan kunci acak 256-bit *sebelum* diunggah; kuncinya dikirim di dalam pesan terenkripsi end-to-end. Server hanya melihat blob acak selama 3 hari. Penerima mengetik `/get <nomor>` (atau `get <nomor>` di luar chat), lalu membukanya dengan `termux-open ~/wa-downloads/foto.jpg`. Kecilkan foto dulu kalau lebih dari 1,5 MB:

```bash
pkg install imagemagick
magick foto.jpg -resize 1280x1280 -quality 80 kecil.jpg
```

### 8.6 Status, blokir, pesan hilang otomatis

- `status Budi` → `🟢 online` atau `terakhir dilihat 5 menit lalu`.
- `block Budi` / `unblock Budi` → server diam-diam membuang pesan dari orang yang diblokir (mereka tidak diberi tahu), dan client kamu juga mengabaikannya.
- `/exp 1h` di dalam chat → pesan baru kamu hilang dari kedua perangkat setelah waktu itu (dihitung sejak dikirim bagi kamu, sejak diterima bagi penerima). Sifatnya kooperatif: penerima masih bisa screenshot atau memakai client yang dimodifikasi.

### 8.7 Notifikasi (Android)

1. Pasang aplikasi **Termux:API** (sumber sama dengan Termux) lalu jalankan `pkg install termux-api`.
2. Pengaturan Android → Aplikasi → Termux:API → Izin → izinkan *Notifikasi*.
3. Tes: `termux-notification --title tes --content halo`.
4. Di client: `notif on` (default), `notif hide` (hanya tampil "Pesan baru", isi disembunyikan dari layar kunci), `notif off`.

Notifikasi hanya muncul selama client berjalan dan hanya untuk chat yang sedang tidak dibuka. Tiap chat punya notifikasinya sendiri, ditambah getar singkat kalau `termux-vibrate` tersedia. Supaya tetap hidup di background pakai `tmux`, `termux-wake-lock`, dan set baterai Termux ke *Tanpa batasan*.

### 8.8 Kunci aplikasi (enkripsi data lokal dengan password)

```
lock on         aktifkan (minta password baru, min 8 karakter)
lock passwd     ganti password
lock off        matikan
lock            lihat status
```

Saat kunci aktif, pesan, nama kontak, nama grup, sesi enkripsi, token login, dan kunci privat disimpan terenkripsi (AES-256-GCM). Password diubah jadi kunci dengan scrypt; kunci data yang sebenarnya acak dan dibungkus oleh kunci itu. Client meminta password tiap dibuka (3 kali percobaan). **Password yang lupa tidak bisa dipulihkan.** ID, waktu, status pesan, dan chat mana yang memiliki pesan tetap terbaca di file lokal, karena database membutuhkannya untuk query.

### 8.9 Backup dan restore

```
backup ~/cadangan.wabk     dienkripsi dengan password pilihanmu (min 8 karakter)
restore ~/cadangan.wabk    menimpa profil saat ini, lalu jalankan ulang client
```

Jangan pernah memakai akun yang sama di dua perangkat lewat restore: sesi enkripsi akan bentrok dan pesan berhenti bisa didekripsi.

### 8.10 Beberapa akun di satu HP (untuk tes)

Kamu tidak bisa chat dengan diri sendiri, tapi bisa menjalankan dua akun dengan profil:

@@MULTI@@

Tiap profil punya file sendiri: `~/.wa-cli2/<profil>.json` dan `.db`.

### 8.11 Teman di perangkat lain (bahkan beda negara)

Siapa pun yang bisa menjangkau URL tunnel kamu bisa chat dengan kamu, di mana pun mereka berada. Mereka hanya butuh **tiga file client** di folder yang sama (`client.py`, `secure.py`, `store.py`), Python, dan `cryptography`:

@@FRIEND@@

Berikan URL **dan** kode undangan lewat jalur yang aman.

<a id="id-cmds"></a>
## 9. Daftar command

### Client (prompt utama `wa>`)

| Command | Fungsi |
|---|---|
| `help` | daftar command |
| `me` | ID, nickname, server, profil, status kunci aplikasi |
| `add [id] [nama]` | tambah kontak (ditanya kalau argumen kurang) |
| `contacts` | daftar kontak (✓ terverifikasi, `[diblokir]`) |
| `chat <id\|nama\|#grup>` | buka chat |
| `send <id\|nama\|#grup> <teks>` | kirim tanpa membuka chat |
| `status <id\|nama>` | online / terakhir dilihat |
| `verify <id\|nama>` | tampilkan dan konfirmasi safety number |
| `trust <id\|nama>` | terima kunci yang berubah, atau reset sesi enkripsi yang rusak |
| `block` / `unblock <id\|nama>` | blokir / buka blokir |
| `group new <nama> <anggota…>` | buat grup |
| `group list` / `group leave <nama>` | daftar / keluar |
| `get <no>` | unduh file di pesan #no |
| `clear <id\|nama\|#grup>` | hapus riwayat lokal sebuah chat |
| `notif on\|hide\|off` | notifikasi Android |
| `lock on\|off\|passwd` | kunci aplikasi |
| `backup [file]` / `restore <file>` | backup / restore terenkripsi |
| `server [url]` | lihat / ganti URL server |
| `exit` (`quit`, `q`, Ctrl+D) | keluar |

### Opsi saat menjalankan client

| Opsi | Arti |
|---|---|
| `-s`, `--server URL` | URL server (disimpan untuk berikutnya) |
| `-p`, `--profile NAMA` | profil akun (default `default`) |
| `-i`, `--invite KODE` | kode undangan untuk pendaftaran |

### Admin server (`python server/admin.py …`)

`invite [-n PAKAI] [-t JAM]` · `invites` · `revoke ID` · `users` · `mode [open|invite]`

<a id="id-layout"></a>
## 10. Struktur project

```
wa-cli/
├── server/
│   ├── server.py      server HTTP (127.0.0.1:8080), parsing request, pembersihan latar belakang
│   ├── api.py         routing, validasi, autentikasi, batas laju, long polling
│   ├── database.py    SQLite: user, blokir, pesan, blob, undangan, pengaturan
│   └── admin.py       alat admin kode undangan dan user
├── cli/
│   ├── client.py      aplikasi chat
│   ├── secure.py      X25519, kesepakatan ala X3DH, Double Ratchet, AES-GCM, kripto kunci aplikasi
│   └── store.py       penyimpanan lokal SQLite (bisa terenkripsi)
├── data/              database server (wa2.db) dan blob file terenkripsi (dibuat saat jalan)
├── logs/              server.log dan tunnel.log dari start-all.sh
├── start-all.sh       server + tunnel di tmux dengan restart otomatis
├── stop-all.sh        hentikan keduanya
├── url.sh             tampilkan URL tunnel terbaru
├── invite.sh          buat kode undangan
├── start-server.sh    server saja
├── start-tunnel.sh    tunnel saja
├── start-client.sh    peluncur client
├── requirements.txt   cryptography
└── README.md
```

<a id="id-config"></a>
## 11. Konfigurasi

### Variabel lingkungan

| Variabel | Dipakai oleh | Default | Arti |
|---|---|---|---|
| `WA_HOST` | server | `127.0.0.1` | alamat bind (biarkan lokal; tunnel terhubung ke sini) |
| `WA_PORT` | server, script | `8080` | port |
| `WA_DB` | server | `data/wa2.db` | lokasi database (blob masuk ke folder `blobs/` di sebelahnya) |
| `WA_SERVER` | client | – | URL server default |
| `WA_INVITE` | client | – | kode undangan untuk pendaftaran |
| `WA_WAIT` | client | `25` | lama long-poll dalam detik (0–25) |

### File

| Lokasi | Isi |
|---|---|
| `~/.wa-cli2/<profil>.json` | pengaturan non-rahasia: server, ID, nickname, kunci publik, ID pesan terakhir (chmod 600) |
| `~/.wa-cli2/<profil>.db` | kontak, sesi, grup, riwayat, **dan token + kunci privatmu** (terenkripsi kalau kunci aplikasi aktif) |
| `~/wa-downloads/` | file yang diunduh dengan `/get` |
| `data/wa2.db`, `data/blobs/` | database server dan blob file terenkripsi |

<a id="id-security"></a>
## 12. Keamanan secara mendalam

### 12.1 Desain kriptografi

| Bagian | Pilihan |
|---|---|
| Identitas | Pasangan kunci X25519 per akun, dibuat di perangkat; hanya kunci publik yang diunggah |
| Awal sesi | Ala X3DH: `HKDF(DH(IK_A, IK_B) ‖ DH(EK_A, IK_B))` dengan kunci ephemeral baru untuk tiap sesi |
| Pesan | **Double Ratchet**: KDF akar HKDF-SHA256, KDF rantai HMAC-SHA256, langkah DH ratchet baru tiap arah berganti |
| Cipher | **AES-256-GCM**; kunci dan nonce diturunkan per pesan (nonce tidak pernah dipakai ulang); header dan `pengirim>penerima` ikut diautentikasi |
| Padding | plaintext dipadatkan ke kelipatan 128 byte untuk menyamarkan panjang pesan |
| Tidak berurutan | sampai 100 kunci pesan terlewat disimpan; pesan ulang (replay) ditolak |
| State | state ratchet disimpan **sebelum** mengirim, jadi kunci pesan tidak pernah dipakai dua kali; enkripsi/dekripsi diserialkan antar thread |
| File | kunci acak 256-bit + nonce acak per file; kunci dikirim di dalam pesan terenkripsi |
| Backup | scrypt (N=2¹⁵) + AES-256-GCM |
| Kunci aplikasi | scrypt (N=2¹⁶) membungkus kunci utama acak 256-bit; kolom dienkripsi AES-256-GCM |
| Token | acak 256-bit; server hanya menyimpan hash SHA-256 |

### 12.2 Kepercayaan dan verifikasi

- Saat kontak pertama kali, kunci publik teman **dipin**. Kalau server nanti memberi kunci berbeda, client menolak ngobrol dan menampilkan **KUNCI BERUBAH**. Pakai `verify`, lalu `trust` hanya kalau kamu yakin.
- `verify` membandingkan safety number yang diturunkan dari kedua kunci publik. Inilah yang menggagalkan server jahat.
- Pengirim tak dikenal tampil sebagai `~Nickname`; nickname itu dipilih mereka sendiri dan tidak terverifikasi.

### 12.3 Yang bisa dan tidak bisa dilihat server

| Server TIDAK bisa melihat | Server BISA melihat |
|---|---|
| isi pesan, isi file, nama file | siapa ngobrol dengan siapa, dan kapan |
| nama grup dan keanggotaannya | ukuran pesan (kira-kira, sudah dipadatkan), ukuran file |
| kunci privatmu | ID, nickname terdaftar, kunci publik |
| nama kontakmu, password kunci aplikasi | kapan terakhir online, daftar blokirmu |
| | IP kamu (lewat header Cloudflare) |

Cloudflare mengakhiri TLS untuk tunnel, jadi ia bisa melihat metadata yang sama plus ciphertext, tidak pernah plaintext.

### 12.4 Pengerasan server

Hanya bind ke `127.0.0.1` · validasi input dan batas ukuran ketat · pesan plaintext ditolak (hanya ciphertext `e2:…`) · batas laju · token di-hash · file database `chmod 600` · tanpa secret yang di-hardcode · timeout request · `Cache-Control: no-store`, `X-Content-Type-Options: nosniff` · karakter escape terminal dibuang dari teks yang ditampilkan.

### 12.5 Keterbatasan (apa adanya)

- **Belum diaudit pihak independen.** Ini proyek hobi di atas primitif yang sudah dikenal; jangan andalkan untuk hal yang menyangkut nyawa atau uang besar.
- **Tanpa pre-key:** pesan sebelum balasan pertama dilindungi oleh kunci identitas jangka panjang penerima. Setelah balasan pertama, ratchet memberi forward secrecy dan pemulihan.
- **Metadata terlihat** oleh pemilik server dan Cloudflare (lihat 12.3).
- **Riwayat lokal berupa plaintext** kecuali kunci aplikasi aktif, dan itu pun ID/waktu/status tetap terbaca. Siapa pun yang memegang HP kamu yang terbuka bisa membaca layar dan notifikasimu (pakai `notif hide`).
- **Satu perangkat per akun.** Restore backup ke perangkat kedua yang dipakai bersamaan akan merusak sesi.
- **Pesan hilang dan hapus-untuk-semua sifatnya semampunya**: bergantung pada client lawan bicara.
- **Grup tanpa admin**; siapa pun bisa memasukkan kamu ke grup.
- Password kunci aplikasi yang lemah bisa ditebak secara offline kalau file HP kamu dicuri.
- Quick tunnel tidak punya jaminan uptime.

<a id="id-api"></a>
## 13. Referensi API

Semua body berupa JSON kecuali disebutkan lain. Panggilan terautentikasi butuh `Authorization: Bearer <token>`.

| Method & path | Auth | Fungsi |
|---|---|---|
| `GET /` | tidak | `{name, version, status, registration}` (`registration` bernilai `invite` atau `open`) |
| `GET /health` | tidak | cek hidup |
| `POST /register` | tidak | `{nickname, ik, invite?}` → `201 {id, nickname, token}` |
| `GET /users/<id>` | ya | `{id, nickname, ik, last_seen, online}` |
| `POST /messages/send` | ya | `{to, text}`, `text` wajib ciphertext `e2:…` (≤ 4096 karakter) → `201 {id, status, created_at}` |
| `GET /messages/<idku>?after=N&limit=1-100&wait=0-25&track=1,2,3` | ya | long-poll: `{messages:[{id,from,to,text,created_at}], last_id, status:{id:"sent"\|"delivered"}}` |
| `POST /block`, `POST /unblock` | ya | `{id}` |
| `POST /blobs` | ya | byte mentah (`application/octet-stream`, ≤ 2 MiB) → `{id, size}` |
| `GET /blobs/<id>` | ya | byte terenkripsi mentah |

Kode status: `400` input salah · `401` token salah · `403` kode undangan salah / bukan milikmu · `404` tidak ditemukan · `405` method salah · `408` timeout baca · `413` body terlalu besar · `414` URL terlalu panjang · `429` kena batas laju · `500` error server.

Tes cepat:

```bash
curl http://127.0.0.1:8080/
curl http://127.0.0.1:8080/health
```

<a id="id-limits"></a>
## 14. Batas & masa simpan

| Hal | Nilai |
|---|---|
| Teks pesan (client) | 1000 karakter |
| Payload terenkripsi / pesan di jaringan | 2800 byte / 4096 karakter |
| Body request JSON | 8 KB |
| File | 1,5 MB (client) · 2 MiB (batas keras server) |
| Nickname / nama grup / nama kontak | 2–20 / 2–20 / maks 30 karakter |
| Ukuran grup | 20 anggota termasuk kamu |
| Pesan | 120 per menit per user |
| Cek user | 60 per menit per user |
| Pendaftaran | 10 per jam per IP; 50 kode undangan salah per jam → dikunci sementara |
| Unggah / unduh file | 20 / 60 per jam per user |
| Long-poll bersamaan | 3 per user |
| Jendela "online" | 45 detik |
| Pesan terkirim disimpan di server | 1 jam |
| Pesan belum terkirim disimpan | 14 hari |
| File disimpan | 3 hari |
| Pesan hilang otomatis | sampai 30 hari |
| Toleransi tidak berurutan | 100 pesan per rantai |

<a id="id-tunnel"></a>
## 15. Catatan Cloudflare Tunnel

- *Quick tunnel* gratis tidak butuh akun: `cloudflared tunnel --url http://127.0.0.1:8080`. `start-all.sh` melakukannya untukmu.
- URL (`https://kata-acak.trycloudflare.com`) **berubah tiap restart**; tidak ada jaminan uptime.
- Kalau QUIC diblokir jaringanmu: `bash start-tunnel.sh --protocol http2`.
- Pakai `cloudflared` dari `pkg`, bukan binary Linux dari GitHub (masalah DNS di Android).
- Untuk URL permanen kamu butuh akun Cloudflare gratis dan sebuah domain: `cloudflared tunnel login`, `cloudflared tunnel create wa`, `cloudflared tunnel route dns wa chat.domainmu.com`, lalu jalankan tunnel dengan file konfigurasi. Belum diotomatisasi di project ini.

<a id="id-update"></a>
## 16. Update & reset

- **Update:** ekstrak versi baru di samping yang lama, salin folder `data/` (database server), dan biarkan `~/.wa-cli2/` (data client) apa adanya. Dari v2.0, client memindahkan rahasianya ke database lokal secara otomatis.
- **Reset profil client:** `rm ~/.wa-cli2/<profil>.*` (kamu akan daftar lagi dan dapat ID baru).
- **Reset server:** hentikan, lalu `rm -rf data/wa2.db* data/blobs`. Semua akun hilang dan setiap client harus mereset profilnya.
- **Hapus total:** `rm -rf ~/wa-cli ~/.wa-cli2 ~/wa-downloads`.

<a id="id-trouble"></a>
## 17. Pemecahan masalah

| Gejala | Penyebab dan solusi |
|---|---|
| `ModuleNotFoundError: No module named 'api'` | `server/api.py` tidak ada. Jalankan `ls server`. Ekstrak ulang. **Jangan** `pip install api`. |
| `pip install sqlite3` gagal | Normal. `sqlite3` sudah bawaan Python. |
| `Butuh paket 'cryptography'` | `pkg install python-cryptography` |
| `start-tunnel.sh: command not found` | Jalankan `bash start-tunnel.sh` (atau `chmod +x` lalu `./start-tunnel.sh`). |
| Tunnel "nyangkut" setelah menampilkan log | Normal; ia berjalan di depan layar. URL ada di dalam kotak. Jangan tekan Ctrl+C. |
| `ping_group_range … permission denied` | Peringatan cloudflared yang tidak berbahaya. |
| `Gagal listen … Address already in use` | Server lain masih jalan: `bash stop-all.sh` atau `pkill -f server.py`. |
| Client: `Connection refused` | Server belum jalan, URL salah, atau port salah. |
| `HTTP 530 / 1033 / 502`, "bukan dari wa-cli server" | Tunnel mati atau URL berubah. `bash url.sh`, lalu `server <url-baru>` di client. |
| Error DNS / `[::1]:53` di cloudflared | Pakai cloudflared dari `pkg`; coba `--protocol http2`. |
| `Kode undangan salah atau kedaluwarsa` (403) | Kode salah, sudah dipakai, kedaluwarsa, atau dicabut. Buat baru dengan `bash invite.sh`. |
| `429` saat daftar | Terlalu banyak percobaan. Tunggu sejam atau minta admin. |
| `Token ditolak` / "akun tidak dikenal" | Database server direset. `rm ~/.wa-cli2/<profil>.*` lalu daftar lagi. |
| Peringatan **KUNCI BERUBAH** | Server memberi kunci berbeda untuk ID itu. Jalankan `verify`; pakai `trust` hanya kalau yakin. |
| `Pesan dari X tidak bisa dibuka` | Sesi enkripsi tidak sinkron (misal backup di-restore di dua perangkat). Jalankan `trust <kontak>` dan jawab `y` pada pertanyaan *reset sesi*; pesan baru memulai sesi segar. |
| `Terlalu banyak koneksi polling` | Ada lebih dari 3 client login dengan akun yang sama. |
| File ditolak | Lebih dari 1,5 MB, atau path mengandung spasi (ganti nama file). |
| `~/storage` tidak ada | Jalankan `termux-setup-storage`, lalu restart Termux. |
| Tidak ada notifikasi | Pastikan `termux-notification --title t --content c` jalan; Termux:API harus dari sumber yang sama dengan Termux; izin sudah diberikan; `notif on`; client sedang berjalan. |
| Semua mati saat layar padam | Baterai Termux = Tanpa batasan, `termux-wake-lock`, jalankan lewat `start-all.sh` (tmux). |
| Prompt password menampilkan "Can not control echo" | Client tidak terhubung ke terminal sungguhan; tidak berbahaya. |
| Membuka kunci butuh sekitar satu detik | scrypt memang sengaja lambat (menyulitkan brute force). |
| `tmux: command not found` | `pkg install tmux` |
| Pesan grup tidak masuk | Kamu harus sudah menerima undangan grup, dan pengirim harus anggota. Kalau sudah keluar, kamu tidak lagi di grup. |
| Nickname ditolak | 2–20 karakter: huruf, angka, spasi, `.`, `-`, `_`. |
| Error Python aneh di versi Python baru | Laporkan traceback lengkapnya; kode hanya memakai API yang stabil. |

<a id="id-faq"></a>
## 18. FAQ

**Ini WhatsApp?** Bukan. Ini messenger mandiri dengan ide yang mirip; tidak ada API resmi yang dipakai.

**Pemilik server bisa baca pesanku?** Tidak, hanya ciphertext. Pemilik bisa melihat metadata (siapa, kapan, ukuran).

**Bisa chat dengan diri sendiri?** Server menolaknya. Pakai dua profil (bagian 8.10).

**HP server harus tetap nyala?** Ya. Pesan menunggu sampai 14 hari untuk penerima yang offline.

**Multi-perangkat?** Tidak, satu perangkat per akun.

**Ukuran grup?** Sampai 20 anggota.

**Bisa ganti nickname atau hapus akun?** Belum: daftar akun baru dan reset profil lama.

**Server bisa di PC atau VPS?** Bisa, mesin apa pun dengan Python 3; hanya script bantu yang mengasumsikan Termux.

**Jalan di iPhone?** Client jalan di mana pun Python jalan; Termux sendiri hanya untuk Android.

**Bagaimana tahu temanku benar-benar temanku?** Lakukan `verify` dan cocokkan safety number lewat telepon atau ketemu langsung.

<a id="id-todo"></a>
## 19. Belum ada (ide)

Indikator mengetik (butuh UI layar penuh), bot AI (butuh API online), pre-key, admin grup dan pengelolaan anggota, edit pesan, reaksi, pesan suara, kirim lokasi, mute/pin, antarmuka curses, named tunnel otomatis, dukungan multi-perangkat.

<a id="id-changelog"></a>
## 20. Riwayat versi

- **v2.1**: pendaftaran hanya dengan undangan, `admin.py`, `start-all.sh` / `stop-all.sh` / `url.sh` / `invite.sh`, **kunci aplikasi**, notifikasi per chat, opsi reset sesi di `trust`, pemilihan sesi aktif terbaru, dan perbaikan balapan antara kirim dan terima yang bisa merusak state ratchet.
- **v2.0**: enkripsi end-to-end (X25519 + Double Ratchet + AES-256-GCM), grup, file, long polling, centang, pesan hilang otomatis, blokir, status, backup.
- **v1.x**: prototipe pertama tanpa enkripsi dengan API HTTP dan SQLite, lalu kunci AES per kontak opsional.

<a id="id-disclaimer"></a>
## 21. Penafian

Disediakan "apa adanya", tanpa jaminan apa pun. Pakai dengan risiko sendiri dan patuhi hukum serta aturan platform yang berlaku bagimu. wa-cli tidak berafiliasi dengan WhatsApp, Meta, Cloudflare, atau Termux.

[⬆ kembali ke atas](#top)