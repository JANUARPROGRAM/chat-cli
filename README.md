<a id="top"></a>
# chat-cli v2.1

> End-to-end encrypted chat for your terminal. Self-hosted on Android (Termux), free Cloudflare Tunnel, no paid API.
> Chat terminal terenkripsi end-to-end. Jalan di HP Android (Termux), tunnel Cloudflare gratis, tanpa API berbayar.

**Language / Bahasa:** [🇬🇧 English](#en) · [🇮🇩 Bahasa Indonesia](#id) · [😎 Bahasa Gaul](#gaul)

`X25519` · `Double Ratchet` · `AES-256-GCM` · `Python + SQLite` · `Termux` · `Cloudflare Tunnel`

---

<a id="en"></a>
# 🇬🇧 English

## Table of contents
1. [What is chat-cli?](#en-what) · 2. [Features](#en-features) · 3. [How it works](#en-how) · 4. [Requirements](#en-req) · 5. [Quick start](#en-quick)
6. [Full installation](#en-install) · 7. [Running the server](#en-server) · 8. [Using the client](#en-client) · 9. [Command reference](#en-cmds)
10. [Project layout](#en-layout) · 11. [Configuration](#en-config) · 12. [Security in depth](#en-security) · 13. [API reference](#en-api)
14. [Limits & retention](#en-limits) · 15. [Cloudflare Tunnel](#en-tunnel) · 16. [Updating & resetting](#en-update) · 17. [Troubleshooting](#en-trouble)
18. [FAQ](#en-faq) · 19. [Not included](#en-todo) · 20. [Changelog](#en-changelog) · 21. [Disclaimer](#en-disclaimer)

<a id="en-what"></a>
## 1. What is chat-cli?

**chat-cli** is a small, self-hosted, terminal-based chat app that works like a messenger (contacts, 1:1 chats, groups, file sharing, read receipts, disappearing messages) with **end-to-end encryption**.

- The **server** is a plain Python HTTP server + SQLite. It runs on an Android phone inside **Termux** and is exposed to the internet with a free **Cloudflare Tunnel**. No paid API, no laptop, no cloud VM.
- The **client** is a Python CLI that runs on Android (Termux), Linux, macOS or Windows. All encryption and decryption happen **on your device**; the server only stores ciphertext.
- It is **not** WhatsApp and does not use any official WhatsApp API. It is its own messenger that merely has a similar concept.

<a id="en-features"></a>
## 2. Features

| Area | What you get |
|---|---|
| Chat | 1:1 chats, live delivery via long polling, message numbers, replies (`/reply`), delete for everyone (`/del`), unread summary, per-chat Android notifications |
| Groups | Up to 20 members, created with one command, delivered through each member's own encrypted session |
| Files | Encrypted file transfer up to 1.5 MB (`/file`, `/get`) |
| Receipts | ✓ sent · ✓✓ delivered · ✓✓ read · ✗ failed |
| Presence | `status` shows online / last seen |
| Privacy tools | Safety-number verification, key-change alerts, block/unblock, disappearing messages (`/exp`) |
| Encryption | X25519 identity keys, X3DH-style key agreement, **Double Ratchet**, **AES-256-GCM**, message padding |
| Local protection | **App lock**: password-encrypts your local messages, contacts, sessions, token and private key |
| Backup | Password-encrypted backup / restore |
| Access control | **Invite codes**: nobody can register without a code from you |
| Operations | `start-all.sh` runs server + tunnel in tmux with auto-restart and prints the public URL |
| Dependencies | Server: Python standard library only. Client: Python + `cryptography` |

<a id="en-how"></a>
## 3. How it works

```
 Phone A (client)                          Phone B (client)
 ┌─────────────────┐                       ┌─────────────────┐
 │ encrypt/decrypt │                       │ encrypt/decrypt │
 │ happens HERE    │                       │ happens HERE    │
 └────────┬────────┘                       └────────┬────────┘
          │  HTTPS: ciphertext "e2:..." only        │
          ▼                                         ▼
 ┌──────────────────────────────────────────────────────────┐
 │  Cloudflare Tunnel   https://xxxx.trycloudflare.com      │
 └─────────────────────────────┬────────────────────────────┘
                               ▼
              ┌──────────────────────────────────┐
              │ Server phone (Termux)            │
              │ server.py  127.0.0.1:8080        │
              │ SQLite: users, public keys,      │
              │ ciphertext, invites              │
              └──────────────────────────────────┘
```

1. Each account has an **ID** (10 random digits) and a **key pair** generated on the device. Only the *public* key is sent to the server.
2. When you write to someone, your client agrees on a secret with their public key, then runs a **Double Ratchet**: every message uses a fresh AES-256-GCM key, and old keys are deleted.
3. The client sends the ciphertext to the server. The server checks that it looks like ciphertext (`e2:...`), stores it, and wakes up the recipient's long-poll request.
4. The recipient's client fetches it, decrypts it locally and saves it in its own local database.
5. The server deletes delivered messages after 1 hour. Your history lives only on your devices.
6. Groups are not a server feature: a group message is sent separately to each member over the existing 1:1 sessions. The server does not even know groups exist.

<a id="en-req"></a>
## 4. Requirements

- **Server phone:** Android + [Termux](https://f-droid.org/packages/com.termux/) (F-Droid or GitHub build), roughly 100 MB free storage, internet.
- **Termux packages:** `python`, `python-cryptography`, `cloudflared`, `tmux`, `unzip` (and `termux-api` + the **Termux:API** app for notifications, optional).
- **Clients:** any device with Python 3 (tested on 3.12; Termux currently ships 3.12–3.14) and the `cryptography` package.
- Free Cloudflare quick tunnel (no account needed). It has no uptime guarantee and the URL changes whenever the tunnel restarts.

<a id="en-quick"></a>
## 5. Quick start (5 minutes)

```bash
pkg update -y && pkg upgrade -y
pkg install -y python python-cryptography cloudflared tmux unzip
termux-setup-storage
cd ~
unzip ~/storage/downloads/chat-cli-v2.1.zip
cd chat-cli
python -m py_compile server/*.py cli/*.py && echo ALL OK
```

Start the server and the tunnel (one command):

```bash
bash start-all.sh
```

It prints your public URL and a **first invite code**. Then, in a new Termux session (swipe from the left edge → *New session*):

```bash
cd ~/chat-cli
bash start-client.sh -s https://YOUR-URL.trycloudflare.com -i XXXX-XXXX
```

Pick a nickname, optionally set an app-lock password, and type `help`. Create more invite codes with `bash invite.sh`.

<a id="en-install"></a>
## 6. Full installation (Termux)

1. **Install Termux** from F-Droid or GitHub (the Play Store build is outdated). If you want notifications, install **Termux:API** from the *same source*; mixing sources fails because the signing keys differ.
2. **Update and install packages:**
   ```bash
   pkg update -y && pkg upgrade -y
   pkg install -y python python-cryptography cloudflared tmux unzip
   ```
   If a config-file question appears during the upgrade, just press Enter.
3. **Allow storage access** (needed to read the zip from Downloads and to send files from your phone):
   ```bash
   termux-setup-storage
   ```
   Close and reopen Termux if `~/storage` does not appear.
4. **Unzip the project** and verify it:
   ```bash
   cd ~
   unzip ~/storage/downloads/chat-cli-v2.1.zip
   cd chat-cli
   python -m py_compile server/*.py cli/*.py && echo ALL OK
   ```
5. **Prefer `pkg install python-cryptography`** over `pip install cryptography`. The pip route may try to compile Rust and fail on some devices (it works on some, but the `pkg` build is the safe choice).
6. `sqlite3` is **built into Python**. Never run `pip install sqlite3` (it fails and is not needed). Also never `pip install api`: `api` is a local file, `server/api.py`.
7. **Battery:** Android Settings → Apps → Termux → Battery → *Unrestricted*. `start-all.sh` also takes a wake lock via `termux-wake-lock`.

<a id="en-server"></a>
## 7. Running the server

### 7.1 One command: `start-all.sh` (recommended)

```bash
bash start-all.sh
```

- Creates a tmux session called `wacli` with two windows: **server** and **tunnel**.
- Each one restarts automatically if it crashes (server after 3 s, tunnel after 5 s).
- Waits up to 60 s for the tunnel URL, prints it, saves it to `data/tunnel_url.txt`, and shows the first-run invite code.
- Logs go to `logs/server.log` and `logs/tunnel.log` (reset on every start).

| Task | Command |
|---|---|
| Show the latest tunnel URL | `bash url.sh` |
| Create an invite code | `bash invite.sh` |
| Watch logs | `tmux attach -t wacli` (switch window: `Ctrl+B` then `N`; detach: `Ctrl+B` then `D`) |
| Stop everything | `bash stop-all.sh` |

> The tunnel URL **changes every time the tunnel restarts**. After a restart run `bash url.sh` and give friends the new URL (they can use the `server <url>` command inside the client).

### 7.2 Manual mode (three Termux sessions)

```bash
# session 1
bash start-server.sh
# session 2
bash start-tunnel.sh
# session 3
bash start-client.sh -s https://YOUR-URL.trycloudflare.com -i XXXX-XXXX
```

Verify the server: `curl http://127.0.0.1:8080/health` should print `{"status": "ok", ...}`. The tunnel prints a box containing `https://....trycloudflare.com`; that is your public URL. The warning about `ping_group_range permission denied` is harmless.

### 7.3 Invite codes (registration control)

By default the server is **invite-only**. Nobody can create an account without a valid code.

- On the very first start (no users, no valid invite) the server prints `*** FIRST INVITE CODE: XXXX-XXXX ***` (valid 24 h, single use).
- Codes look like `K7F2-9QXM`. Only a **hash** is stored on the server; the code is shown once, at creation.
- Admin commands (run on the server phone):

```bash
bash invite.sh                        # 1 code, single use, 24 h
bash invite.sh -n 5 -t 72             # 5 uses, 72 h
python server/admin.py invites
python server/admin.py revoke 7483c1cb
python server/admin.py users
python server/admin.py mode open      # or: mode invite
```

- `mode open` lets anyone register without a code. Use it only briefly, if at all.
- Brute-force protection: 10 registration attempts per hour per IP, and when 50 wrong codes are seen in an hour the registration endpoint is locked temporarily.

<a id="en-client"></a>
## 8. Using the client

### 8.1 First run

```bash
bash start-client.sh -s https://YOUR-URL.trycloudflare.com -i XXXX-XXXX
```

You will be asked for: the server URL (if you did not pass `-s`), an invite code (if you did not pass `-i`), a nickname (2–20 characters), and whether to enable **app lock**. You then get a random 10-digit **ID**. Type `me` to see it. Your login is saved as profile `default`.

Next time just run `bash start-client.sh`.

### 8.2 Add contacts and verify them

```
add 1234567890 Budi         add a contact by ID and give it a name
verify Budi                 compare the safety number (see below)
contacts                    list contacts (✓ = verified)
```

**Verify matters.** `verify` shows a 30-digit safety number. Compare it with your friend's screen over a *different channel* (phone call, in person). If the numbers match, nobody (including the server) is sitting in the middle. Answer `y` to mark the contact as verified.

### 8.3 Chatting

```
chat Budi
```

You see the last 20 messages and a header (`🔒 verified` or `🔓 not verified`). Just type to send. Messages get numbers like `#12`; the numbers are local to your device. Incoming messages from other chats show up as `📩 Name: preview`.

Inside a chat:

| Input | Effect |
|---|---|
| `text` | send a message |
| `/reply 12 text` | reply to message #12 (shown with `↩`) |
| `/del 12` | delete **your** message #12 for everyone (best effort) |
| `/file ~/storage/downloads/pic.jpg caption` | send a file, max 1.5 MB, no spaces in the path |
| `/get 15` | download the file in message #15 to `~/wa-downloads/` |
| `/exp 1h` | your messages disappear 1 hour after sending (`off`, `30s`, `5m`, `1h`, `1d`, max `30d`) |
| `/info` | peer / group info and verification state |
| `/back` | leave the chat (`/q` and `/exit` also work) |
| `/help` | show chat help |

> Careful: typing plain `exit` inside a chat **sends the word "exit"**. Use `/back` first.

Ticks: `✓` accepted by the server · `✓✓` delivered to the recipient's client · `✓✓ read` the recipient opened or saw it · `✗ failed` could not be sent. Group messages only show `✓`.

### 8.4 Groups

```
group new team Budi Cici        create group "team" with two members
chat #team                      open the group chat
group list                      list groups and members
group leave team                leave (others are notified)
```

Members are added by ID or contact name (1–19 other people). Everybody receives an encrypted invitation automatically. Sending to a group sends one encrypted copy per member, so a group message counts as N−1 messages against the rate limit. There is no admin role yet; anyone who knows your ID can add you to a group, so use `group leave` or `block` against spam.

### 8.5 Files

```
chat Budi
/file ~/storage/downloads/photo.jpg here you go
```

The file is encrypted with a random 256-bit key *before* upload; the key travels inside the end-to-end encrypted message. The server only sees an opaque blob for 3 days. The receiver types `/get <number>` (or `get <number>` outside the chat), then opens it with `termux-open ~/wa-downloads/photo.jpg`. Resize photos first if they exceed 1.5 MB:

```bash
pkg install imagemagick
magick photo.jpg -resize 1280x1280 -quality 80 small.jpg
```

### 8.6 Status, blocking, disappearing messages

- `status Budi` → `🟢 online` or `last seen 5 minutes ago`.
- `block Budi` / `unblock Budi` → the server silently drops messages from a blocked person (they are not told), and your client ignores them too.
- `/exp 1h` inside a chat → your new messages disappear from both devices after the time (counted from sending for you, from receipt for the recipient). It is cooperative: a recipient can still screenshot or run a modified client.

### 8.7 Notifications (Android)

1. Install the **Termux:API** app (same source as Termux) and run `pkg install termux-api`.
2. Android Settings → Apps → Termux:API → Permissions → allow *Notifications*.
3. Test: `termux-notification --title test --content hello`.
4. In the client: `notif on` (default), `notif hide` (shows only "New message", hiding the content on your lock screen), `notif off`.

Notifications appear only while the client is running and only for chats that are not currently open. Each chat gets its own notification, with a short vibration if `termux-vibrate` is available. To keep it alive in the background use `tmux`, `termux-wake-lock` and set Termux battery to *Unrestricted*.

### 8.8 App lock (password-encrypt your local data)

```
lock on         enable (asks for a new password, min 8 chars)
lock passwd     change the password
lock off        disable
lock            show status
```

With the lock on, your messages, contact names, group names, encryption sessions, login token and private key are stored encrypted (AES-256-GCM). The password is turned into a key with scrypt; the real data key is random and wrapped by it. The client asks for the password on every start (3 tries). **A forgotten password cannot be recovered.** IDs, timestamps, message status and which chat a message belongs to remain readable in the local file, because the database needs them for queries.

### 8.9 Backup and restore

```
backup ~/my-backup.wabk     encrypted with a password you choose (min 8 chars)
restore ~/my-backup.wabk    overwrites the current profile, then restart the client
```

Never run the same account on two devices through a restore: the encryption sessions would collide and messages stop decrypting.

### 8.10 Several accounts on one phone (testing)

You cannot message yourself, but you can run two accounts using profiles:

```bash
bash start-client.sh -p a -s http://127.0.0.1:8080 -i CODE1
bash start-client.sh -p b -s http://127.0.0.1:8080 -i CODE2
```

Each profile has its own files: `~/.chat-cli2/<profile>.json` and `.db`.

### 8.11 Friends on other devices (even other countries)

Anyone who can reach your tunnel URL can chat with you, wherever they are. They need only the **three client files** in the same folder (`client.py`, `secure.py`, `store.py`), Python and `cryptography`:

```bash
mkdir -p ~/chat-cli/cli && cd ~/chat-cli/cli      # put client.py secure.py store.py here
pkg install -y python python-cryptography     # on a PC: pip install cryptography
python client.py -s https://YOUR-URL.trycloudflare.com -i XXXX-XXXX
```

Give them the URL **and** an invite code through a secure channel.

<a id="en-cmds"></a>
## 9. Command reference

### Client (main prompt `wa>`)

| Command | Description |
|---|---|
| `help` | list commands |
| `me` | your ID, nickname, server, profile, app-lock state |
| `add [id] [name]` | add a contact (prompts if arguments are missing) |
| `contacts` | list contacts (✓ verified, `[blocked]`) |
| `chat <id\|name\|#group>` | open a chat |
| `send <id\|name\|#group> <text>` | send without opening the chat |
| `status <id\|name>` | online / last seen |
| `verify <id\|name>` | show and confirm the safety number |
| `trust <id\|name>` | accept a changed key, or reset a broken encryption session |
| `block` / `unblock <id\|name>` | block / unblock |
| `group new <name> <members…>` | create a group |
| `group list` / `group leave <name>` | list / leave |
| `get <no>` | download the file in message #no |
| `clear <id\|name\|#group>` | delete the local history of a chat |
| `notif on\|hide\|off` | Android notifications |
| `lock on\|off\|passwd` | app lock |
| `backup [file]` / `restore <file>` | encrypted backup / restore |
| `server [url]` | show / change the server URL |
| `exit` (`quit`, `q`, Ctrl+D) | quit |

### Client launch options

| Option | Meaning |
|---|---|
| `-s`, `--server URL` | server URL (saved for next time) |
| `-p`, `--profile NAME` | account profile (default `default`) |
| `-i`, `--invite CODE` | invite code for registration |

### Server admin (`python server/admin.py …`)

`invite [-n USES] [-t HOURS]` · `invites` · `revoke ID` · `users` · `mode [open|invite]`

<a id="en-layout"></a>
## 10. Project layout

```
chat-cli/
├── server/
│   ├── server.py      HTTP server (127.0.0.1:8080), request parsing, background cleanup
│   ├── api.py         routing, validation, authentication, rate limits, long polling
│   ├── database.py    SQLite: users, blocks, messages, blobs, invites, settings
│   ├── admin.py       invite codes and user admin tool
│   └── recover_users.py   re-register accounts from client profiles after a server DB loss
├── cli/
│   ├── client.py      the chat application
│   ├── secure.py      X25519, X3DH-style agreement, Double Ratchet, AES-GCM, app-lock crypto
│   └── store.py       local SQLite store (optionally encrypted)
├── data/              server database (wa2.db) and encrypted file blobs (created at runtime)
├── logs/              server.log and tunnel.log from start-all.sh
├── start-all.sh       server + tunnel in tmux with auto-restart
├── stop-all.sh        stop them
├── url.sh             print the latest tunnel URL
├── invite.sh          create an invite code
├── start-server.sh    server only
├── start-tunnel.sh    tunnel only
├── start-client.sh    client launcher
├── requirements.txt   cryptography
└── README.md
```

<a id="en-config"></a>
## 11. Configuration

### Environment variables

| Variable | Used by | Default | Meaning |
|---|---|---|---|
| `WA_HOST` | server | `127.0.0.1` | bind address (keep it local; the tunnel connects here) |
| `WA_PORT` | server, scripts | `8080` | listening port |
| `WA_DB` | server | `data/wa2.db` | database path (blobs go to a `blobs/` folder next to it) |
| `WA_SERVER` | client | – | default server URL |
| `WA_INVITE` | client | – | invite code for registration |
| `WA_WAIT` | client | `25` | long-poll wait in seconds (0–25) |

### Files

| Where | What |
|---|---|
| `~/.chat-cli2/<profile>.json` | non-secret settings: server, ID, nickname, public key, last message ID (chmod 600) |
| `~/.chat-cli2/<profile>.db` | contacts, sessions, groups, history, **and your token + private key** (encrypted if app lock is on) |
| `~/wa-downloads/` | files you downloaded with `/get` |
| `data/wa2.db`, `data/blobs/` | server database and encrypted file blobs |

<a id="en-security"></a>
## 12. Security in depth

### 12.1 Cryptographic design

| Piece | Choice |
|---|---|
| Identity | X25519 key pair per account, generated on the device; only the public key is uploaded |
| Session setup | X3DH-style: `HKDF(DH(IK_A, IK_B) ‖ DH(EK_A, IK_B))` with a fresh ephemeral key per new session |
| Messages | **Double Ratchet**: HKDF-SHA256 root KDF, HMAC-SHA256 chain KDF, new DH ratchet step on every change of direction |
| Cipher | **AES-256-GCM**; key and nonce are derived per message (no nonce reuse); the header and `sender>recipient` are authenticated |
| Padding | plaintext padded to multiples of 128 bytes to hide exact message length |
| Out-of-order | up to 100 skipped message keys are kept; replays are rejected |
| State | ratchet state is saved **before** sending, so a message key is never used twice; encrypt/decrypt are serialized between threads |
| Files | random 256-bit key + random nonce per file; key sent inside the encrypted message |
| Backup | scrypt (N=2¹⁵) + AES-256-GCM |
| App lock | scrypt (N=2¹⁶) wraps a random 256-bit master key; columns are encrypted with AES-256-GCM |
| Tokens | 256-bit random; the server stores only a SHA-256 hash |

### 12.2 Trust and verification

- On first contact a friend's public key is **pinned**. If the server later presents a different key, the client refuses to talk and shows **KEY CHANGED**. Use `verify`, then `trust` only if you are sure.
- `verify` compares a safety number derived from both public keys. This is what defeats a malicious server.
- Unknown senders are shown as `~Nickname`; that nickname is chosen by them and is not verified.

### 12.3 What the server can and cannot see

| The server CANNOT see | The server CAN see |
|---|---|
| message text, file contents, file names | who talks to whom, and when |
| group names and membership | message sizes (roughly, padded), file sizes |
| your private key | your ID, registered nickname, public key |
| your contacts' names, your app-lock password | when you were last online, your block list |
| | your IP (via Cloudflare headers) |

Cloudflare terminates TLS for the tunnel, so it can see the same metadata plus the ciphertext, never the plaintext.

### 12.4 Server hardening

Binds to `127.0.0.1` only · strict input validation and size limits · plaintext messages are rejected (only `e2:…` ciphertext accepted) · rate limits · tokens hashed · database file `chmod 600` · no hard-coded secrets · request timeouts · `Cache-Control: no-store`, `X-Content-Type-Options: nosniff` · terminal-escape characters stripped from displayed text.

### 12.5 Honest limitations

- **Not independently audited.** It is a hobby project built on well-known primitives; do not rely on it where lives or large sums depend on secrecy.
- **No pre-keys:** messages before the first reply are protected by the recipient's long-term identity key. After the first reply the ratchet gives forward secrecy and recovery.
- **Metadata is visible** to the server owner and Cloudflare (see 12.3).
- **Local history is plaintext** unless app lock is on, and even then IDs/timestamps/status stay readable. Anyone with your unlocked phone can read the screen and your notifications (use `notif hide`).
- **One device per account.** Restoring a backup onto a second device that is used at the same time breaks the sessions.
- **Disappearing and delete-for-everyone are best-effort**: they depend on the other client behaving.
- **Groups have no admins**; anyone can add you to a group.
- A weak app-lock password can be brute-forced offline if your phone's files are stolen.
- Quick tunnels have no uptime guarantee.

<a id="en-api"></a>
## 13. API reference

All bodies are JSON unless noted. Authenticated calls need `Authorization: Bearer <token>`.

| Method & path | Auth | Purpose |
|---|---|---|
| `GET /` | no | `{name, version, status, registration}` (`registration` is `invite` or `open`) |
| `GET /health` | no | liveness check |
| `POST /register` | no | `{nickname, ik, invite?}` → `201 {id, nickname, token}` |
| `GET /users/<id>` | yes | `{id, nickname, ik, last_seen, online}` |
| `POST /messages/send` | yes | `{to, text}` where `text` must be `e2:…` ciphertext (≤ 4096 chars) → `201 {id, status, created_at}` |
| `GET /messages/<myid>?after=N&limit=1-100&wait=0-25&track=1,2,3` | yes | long-poll: `{messages:[{id,from,to,text,created_at}], last_id, status:{id:"sent"\|"delivered"}}` |
| `POST /block`, `POST /unblock` | yes | `{id}` |
| `POST /blobs` | yes | raw bytes (`application/octet-stream`, ≤ 2 MiB) → `{id, size}` |
| `GET /blobs/<id>` | yes | raw encrypted bytes |

Status codes: `400` bad input · `401` bad token · `403` bad invite code / not your resource · `404` not found · `405` wrong method · `408` read timeout · `413` body too large · `414` URL too long · `429` rate limited · `500` server error.

Quick test:

```bash
curl http://127.0.0.1:8080/
curl http://127.0.0.1:8080/health
```

<a id="en-limits"></a>
## 14. Limits & retention

| Item | Value |
|---|---|
| Message text (client) | 1000 characters |
| Encrypted payload / wire message | 2800 bytes / 4096 characters |
| JSON request body | 8 KB |
| File | 1.5 MB (client) · 2 MiB (server hard limit) |
| Nickname / group name / contact name | 2–20 / 2–20 / up to 30 characters |
| Group size | 20 members including you |
| Messages | 120 per minute per user |
| User lookups | 60 per minute per user |
| Registrations | 10 per hour per IP; 50 wrong invite codes per hour → temporary lock |
| File uploads / downloads | 20 / 60 per hour per user |
| Concurrent long-polls | 3 per user |
| "Online" window | 45 seconds |
| Delivered messages kept on server | 1 hour |
| Undelivered messages kept | 14 days |
| Files kept | 3 days |
| Disappearing messages | up to 30 days |
| Out-of-order tolerance | 100 messages per chain |

<a id="en-tunnel"></a>
## 15. Cloudflare Tunnel notes

- The free *quick tunnel* needs no account: `cloudflared tunnel --url http://127.0.0.1:8080`. `start-all.sh` does this for you.
- The URL (`https://random-words.trycloudflare.com`) **changes on every restart**; there is no uptime guarantee.
- If QUIC is blocked on your network: `bash start-tunnel.sh --protocol http2`.
- Use the `pkg` build of `cloudflared`, not the GitHub Linux binary (DNS problems on Android).
- For a permanent URL you need a free Cloudflare account and a domain: `cloudflared tunnel login`, `cloudflared tunnel create wa`, `cloudflared tunnel route dns wa chat.yourdomain.com`, then run the tunnel with a config file. Not automated in this project.

<a id="en-update"></a>
## 16. Updating & resetting

- **Update:** unzip the new version next to the old one, copy `data/` (server database) over, keep `~/.chat-cli2/` (client data) as is. From v2.0, clients migrate their secrets into the local database automatically.
- **Reset a client profile:** `rm ~/.chat-cli2/<profile>.*` (you will register again and get a new ID).
- **Reset the server:** stop it, `rm -rf data/wa2.db* data/blobs`. All accounts disappear and every client must reset its profile.
- **Uninstall:** `rm -rf ~/chat-cli ~/.chat-cli2 ~/wa-downloads`.

<a id="en-trouble"></a>
## 17. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `ModuleNotFoundError: No module named 'api'` | `server/api.py` is missing. Run `ls server`. Re-unzip. **Do not** `pip install api`. |
| `pip install sqlite3` fails | Normal. `sqlite3` is built into Python. |
| `Butuh paket 'cryptography'` | `pkg install python-cryptography` |
| `start-tunnel.sh: command not found` | Run `bash start-tunnel.sh` (or `chmod +x` then `./start-tunnel.sh`). |
| Tunnel "hangs" after printing logs | Normal; it runs in the foreground. The URL is in the box. Do not press Ctrl+C. |
| `ping_group_range … permission denied` | Harmless warning from cloudflared. |
| `Gagal listen … Address already in use` | Another server is running: `bash stop-all.sh` or `pkill -f server.py`. |
| Client: `Connection refused` | Server not running, wrong URL, or wrong port. |
| `HTTP 530 / 1033 / 502`, "not from chat-cli server" | Tunnel is down or the URL changed. `bash url.sh`, then `server <new-url>` in the client. |
| cloudflared DNS / `[::1]:53` errors | Use the `pkg` cloudflared; try `--protocol http2`. |
| `Kode undangan salah atau kedaluwarsa` (403) | Wrong, used, expired or revoked code. Make a new one with `bash invite.sh`. |
| `429` on registration | Too many attempts. Wait an hour or ask the admin. |
| `Token ditolak` / "account unknown" | The server database was reset or replaced. If the client profile still exists on the same phone as the server: stop the server, run `python server/recover_users.py`, start the server again; your ID, history and encryption sessions keep working. Otherwise `rm ~/.chat-cli2/<profile>.*` and register again. |
| **KEY CHANGED** warning | The server returned a different key for that ID. Run `verify`; use `trust` only if you are sure. |
| `Pesan dari X tidak bisa dibuka` | Encryption sessions out of sync (e.g. a backup restored on two devices). Run `trust <contact>` and answer `y` to the *reset session* question; new messages start a fresh session. |
| `Terlalu banyak koneksi polling` | More than 3 clients are logged in with the same account. |
| File refused | Over 1.5 MB, or the path has spaces (rename the file). |
| `~/storage` missing | Run `termux-setup-storage`, then restart Termux. |
| No notifications | Check `termux-notification --title t --content c` works; Termux:API must come from the same source as Termux; permission granted; `notif on`; client running. |
| Everything dies when the screen is off | Termux battery = Unrestricted, `termux-wake-lock`, run via `start-all.sh` (tmux). |
| Password prompt shows "Can not control echo" | The client is not attached to a real terminal; harmless. |
| Unlock takes about a second | scrypt on purpose (it slows down brute force). |
| `tmux: command not found` | `pkg install tmux` |
| Group messages missing | You must have received the group invitation, and the sender must be a member. If you left, you are out. |
| Nickname rejected | 2–20 characters: letters, digits, space, `.`, `-`, `_`. |
| Odd Python errors on new Python versions | Report the exact traceback; the code uses only stable APIs. |

<a id="en-faq"></a>
## 18. FAQ

**Is this WhatsApp?** No. It is an independent messenger with a similar idea; no official API is used.

**Can the server owner read my messages?** No, only ciphertext. The owner can see metadata (who, when, sizes).

**Can I message myself?** The server refuses it. Use two profiles (section 8.10).

**Does the server phone need to stay on?** Yes. Messages wait up to 14 days for offline recipients.

**Multi-device?** No, one device per account.

**Group size?** Up to 20 members.

**Can I change my nickname or delete my account?** Not yet: register a new account and reset the old profile.

**Can I run the server on a PC or VPS?** Yes, any machine with Python 3; only the helper scripts assume Termux.

**Does it work on iPhone?** The client runs anywhere Python runs; Termux itself is Android-only.

**How do I know my friend is really my friend?** Do `verify` and compare the safety number over a call or in person.

<a id="en-todo"></a>
## 19. Not included (ideas)

Typing indicator (needs a full-screen UI), an AI bot (needs an online API), pre-keys, group admins and member management, message editing, reactions, voice messages, location sharing, mute/pin, a curses interface, automated named tunnels, multi-device support.

<a id="en-changelog"></a>
## 20. Changelog

- **v2.1**: invite-only registration, `admin.py`, `start-all.sh` / `stop-all.sh` / `url.sh` / `invite.sh`, **app lock**, per-chat notifications, session-reset option in `trust`, newest-active-session selection, fix for a race between sending and receiving that could corrupt a ratchet state.
- **v2.0**: end-to-end encryption (X25519 + Double Ratchet + AES-256-GCM), groups, files, long polling, receipts, disappearing messages, block, status, backup.
- **v1.x**: first plaintext prototype with HTTP API and SQLite, then optional per-contact AES keys.

<a id="en-disclaimer"></a>
## 21. Disclaimer

Provided "as is", without warranty of any kind. Use it at your own risk and follow the laws and platform rules that apply to you. chat-cli is not affiliated with WhatsApp, Meta, Cloudflare or Termux.

[⬆ back to the top](#top)


---

<a id="id"></a>
# 🇮🇩 Bahasa Indonesia

## Daftar isi
1. [Apa itu chat-cli?](#id-what) · 2. [Fitur](#id-features) · 3. [Cara kerja](#id-how) · 4. [Kebutuhan](#id-req) · 5. [Mulai cepat](#id-quick)
6. [Instalasi lengkap](#id-install) · 7. [Menjalankan server](#id-server) · 8. [Memakai client](#id-client) · 9. [Daftar command](#id-cmds)
10. [Struktur project](#id-layout) · 11. [Konfigurasi](#id-config) · 12. [Keamanan secara mendalam](#id-security) · 13. [Referensi API](#id-api)
14. [Batas & masa simpan](#id-limits) · 15. [Cloudflare Tunnel](#id-tunnel) · 16. [Update & reset](#id-update) · 17. [Pemecahan masalah](#id-trouble)
18. [FAQ](#id-faq) · 19. [Belum ada](#id-todo) · 20. [Riwayat versi](#id-changelog) · 21. [Penafian](#id-disclaimer)

<a id="id-what"></a>
## 1. Apa itu chat-cli?

**chat-cli** adalah aplikasi chat berbasis terminal yang dihosting sendiri dan cara kerjanya mirip messenger (kontak, chat 1:1, grup, kirim file, centang dibaca, pesan hilang otomatis) dengan **enkripsi end-to-end**.

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

```bash
pkg update -y && pkg upgrade -y
pkg install -y python python-cryptography cloudflared tmux unzip
termux-setup-storage
cd ~
unzip ~/storage/downloads/chat-cli-v2.1.zip
cd chat-cli
python -m py_compile server/*.py cli/*.py && echo ALL OK
```

Jalankan server dan tunnel (satu perintah):

```bash
bash start-all.sh
```

Ia menampilkan URL publik dan **kode undangan pertama**. Lalu di sesi Termux baru (geser dari tepi kiri layar → *New session*):

```bash
cd ~/chat-cli
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
   unzip ~/storage/downloads/chat-cli-v2.1.zip
   cd chat-cli
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

```bash
# session 1
bash start-server.sh
# session 2
bash start-tunnel.sh
# session 3
bash start-client.sh -s https://YOUR-URL.trycloudflare.com -i XXXX-XXXX
```

Cek server: `curl http://127.0.0.1:8080/health` harus menampilkan `{"status": "ok", ...}`. Tunnel menampilkan kotak berisi `https://....trycloudflare.com`; itu URL publik kamu. Peringatan `ping_group_range permission denied` tidak berbahaya.

### 7.3 Kode undangan (kontrol pendaftaran)

Secara default server **hanya menerima pendaftar dengan undangan**. Tidak ada yang bisa membuat akun tanpa kode yang valid.

- Saat server pertama kali menyala (belum ada user dan belum ada undangan valid) ia menampilkan `*** KODE UNDANGAN PERTAMA: XXXX-XXXX ***` (berlaku 24 jam, sekali pakai).
- Bentuk kode seperti `K7F2-9QXM`. Di server hanya tersimpan **hash**-nya; kode asli ditampilkan sekali saat dibuat.
- Perintah admin (jalankan di HP server):

```bash
bash invite.sh                        # 1 code, single use, 24 h
bash invite.sh -n 5 -t 72             # 5 uses, 72 h
python server/admin.py invites
python server/admin.py revoke 7483c1cb
python server/admin.py users
python server/admin.py mode open      # or: mode invite
```

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

```bash
bash start-client.sh -p a -s http://127.0.0.1:8080 -i CODE1
bash start-client.sh -p b -s http://127.0.0.1:8080 -i CODE2
```

Tiap profil punya file sendiri: `~/.chat-cli2/<profil>.json` dan `.db`.

### 8.11 Teman di perangkat lain (bahkan beda negara)

Siapa pun yang bisa menjangkau URL tunnel kamu bisa chat dengan kamu, di mana pun mereka berada. Mereka hanya butuh **tiga file client** di folder yang sama (`client.py`, `secure.py`, `store.py`), Python, dan `cryptography`:

```bash
mkdir -p ~/chat-cli/cli && cd ~/chat-cli/cli      # put client.py secure.py store.py here
pkg install -y python python-cryptography     # on a PC: pip install cryptography
python client.py -s https://YOUR-URL.trycloudflare.com -i XXXX-XXXX
```

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
chat-cli/
├── server/
│   ├── server.py      server HTTP (127.0.0.1:8080), parsing request, pembersihan latar belakang
│   ├── api.py         routing, validasi, autentikasi, batas laju, long polling
│   ├── database.py    SQLite: user, blokir, pesan, blob, undangan, pengaturan
│   ├── admin.py       alat admin kode undangan dan user
│   └── recover_users.py   daftarkan ulang akun dari profil client setelah database server hilang
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
| `~/.chat-cli2/<profil>.json` | pengaturan non-rahasia: server, ID, nickname, kunci publik, ID pesan terakhir (chmod 600) |
| `~/.chat-cli2/<profil>.db` | kontak, sesi, grup, riwayat, **dan token + kunci privatmu** (terenkripsi kalau kunci aplikasi aktif) |
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

- **Update:** ekstrak versi baru di samping yang lama, salin folder `data/` (database server), dan biarkan `~/.chat-cli2/` (data client) apa adanya. Dari v2.0, client memindahkan rahasianya ke database lokal secara otomatis.
- **Reset profil client:** `rm ~/.chat-cli2/<profil>.*` (kamu akan daftar lagi dan dapat ID baru).
- **Reset server:** hentikan, lalu `rm -rf data/wa2.db* data/blobs`. Semua akun hilang dan setiap client harus mereset profilnya.
- **Hapus total:** `rm -rf ~/chat-cli ~/.chat-cli2 ~/wa-downloads`.

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
| `HTTP 530 / 1033 / 502`, "bukan dari chat-cli server" | Tunnel mati atau URL berubah. `bash url.sh`, lalu `server <url-baru>` di client. |
| Error DNS / `[::1]:53` di cloudflared | Pakai cloudflared dari `pkg`; coba `--protocol http2`. |
| `Kode undangan salah atau kedaluwarsa` (403) | Kode salah, sudah dipakai, kedaluwarsa, atau dicabut. Buat baru dengan `bash invite.sh`. |
| `429` saat daftar | Terlalu banyak percobaan. Tunggu sejam atau minta admin. |
| `Token ditolak` / "akun tidak dikenal" | Database server direset atau tertukar. Kalau profil client masih ada di HP yang sama dengan server: hentikan server, jalankan `python server/recover_users.py`, nyalakan server lagi; ID, riwayat, dan sesi enkripsi tetap berlaku. Kalau tidak, `rm ~/.chat-cli2/<profil>.*` lalu daftar lagi. |
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

Disediakan "apa adanya", tanpa jaminan apa pun. Pakai dengan risiko sendiri dan patuhi hukum serta aturan platform yang berlaku bagimu. chat-cli tidak berafiliasi dengan WhatsApp, Meta, Cloudflare, atau Termux.

[⬆ kembali ke atas](#top)


---

<a id="gaul"></a>
# 😎 Bahasa Gaul (santuy mode)

## Daftar isi
1. [Ini apaan sih?](#gl-what) · 2. [Fitur-fiturnya](#gl-features) · 3. [Cara kerjanya](#gl-how) · 4. [Yang lu butuhin](#gl-req) · 5. [Gas cepet](#gl-quick)
6. [Install lengkap](#gl-install) · 7. [Nyalain server](#gl-server) · 8. [Pake client](#gl-client) · 9. [Daftar command](#gl-cmds)
10. [Isi folder](#gl-layout) · 11. [Setelan](#gl-config) · 12. [Soal keamanan (serius dikit)](#gl-security) · 13. [Referensi API](#gl-api)
14. [Batasan & masa simpan](#gl-limits) · 15. [Cloudflare Tunnel](#gl-tunnel) · 16. [Update & reset](#gl-update) · 17. [Kalo error](#gl-trouble)
18. [FAQ](#gl-faq) · 19. [Belum ada](#gl-todo) · 20. [Riwayat versi](#gl-changelog) · 21. [Disclaimer](#gl-disclaimer)

<a id="gl-what"></a>
## 1. Ini apaan sih?

**chat-cli** itu aplikasi chat lewat terminal yang lu host sendiri. Rasanya kayak messenger beneran (ada kontak, chat berdua, grup, kirim file, centang dibaca, pesan ngilang otomatis), tapi dilindungi **enkripsi end-to-end**.

- **Server**-nya cuma server HTTP Python + SQLite. Jalannya di HP Android lu lewat **Termux**, terus dibuka ke internet pake **Cloudflare Tunnel** gratisan. Nggak pake API bayaran, nggak butuh laptop, nggak butuh VPS. Hemat banget kwkw.
- **Client**-nya aplikasi CLI Python yang bisa jalan di Android (Termux), Linux, macOS, sampe Windows. Semua urusan enkripsi dan dekripsi kejadiannya **di HP lu sendiri**. Server cuma nyimpen teks acak-acakan (ciphertext) yang dia sendiri nggak ngerti.
- Ini **bukan** WhatsApp dan nggak pake API resmi WhatsApp ya. Ini messenger bikinan sendiri yang konsepnya mirip aja.

<a id="gl-features"></a>
## 2. Fitur-fiturnya

| Bagian | Dapet apa |
|---|---|
| Chat | Chat berdua, pesan masuk langsung (long polling), nomor pesan, balas (`/reply`), hapus buat semua orang (`/del`), ringkasan belum dibaca, notif Android per chat |
| Grup | Sampe 20 orang, bikinnya satu command doang, dikirim lewat sesi terenkripsi tiap anggota |
| File | Kirim file terenkripsi sampe 1,5 MB (`/file`, `/get`) |
| Centang | ✓ terkirim · ✓✓ nyampe · ✓✓ dibaca · ✗ gagal |
| Kehadiran | `status` ngasih tau online atau terakhir dilihat kapan |
| Alat privasi | Verifikasi safety number, alarm kalo kunci berubah, blokir, pesan ngilang otomatis (`/exp`) |
| Enkripsi | Kunci identitas X25519, kesepakatan kunci ala X3DH, **Double Ratchet**, **AES-256-GCM**, padding pesan |
| Proteksi lokal | **Kunci aplikasi**: pesan, kontak, sesi, token, sama kunci privat di HP lu dienkripsi pake password |
| Cadangan | Backup / restore yang dienkripsi password |
| Kontrol akses | **Kode undangan**: nggak ada yang bisa daftar kalo lu nggak ngasih kodenya |
| Operasional | `start-all.sh` nyalain server + tunnel di tmux, restart sendiri kalo mati, dan nampilin URL publik |
| Dependensi | Server: cuma Python standard library. Client: Python + `cryptography` |

<a id="gl-how"></a>
## 3. Cara kerjanya

```
 HP A (client)                             HP B (client)
 ┌─────────────────┐                       ┌─────────────────┐
 │ acak-acak & buka │                      │ acak-acak & buka │
 │ pesan di SINI   │                       │ pesan di SINI   │
 └────────┬────────┘                       └────────┬────────┘
          │  HTTPS: cuma ciphertext "e2:..."        │
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

1. Tiap akun punya **ID** (10 digit acak) dan **pasangan kunci** yang dibikin di HP lu. Yang dikirim ke server cuma kunci *publik*-nya.
2. Pas lu nulis ke seseorang, client lu sepakat soal rahasia bareng pake kunci publik dia, terus jalanin **Double Ratchet**: tiap pesan pake kunci AES-256-GCM baru, kunci lama langsung dibuang.
3. Client ngirim ciphertext ke server. Server ngecek bentuknya (`e2:...`), nyimpen, terus ngebangunin request long-poll punya penerima.
4. Client penerima ngambil, buka kuncinya di HP dia sendiri, terus nyimpen di database lokalnya.
5. Server ngapus pesan yang udah nyampe setelah 1 jam. Riwayat chat cuma ada di HP kalian berdua.
6. Grup bukan fitur server: pesan grup dikirim satu-satu ke tiap anggota lewat sesi berdua yang udah ada. Server bahkan nggak tau grup itu ada.

<a id="gl-req"></a>
## 4. Yang lu butuhin

- **HP server:** Android + [Termux](https://f-droid.org/packages/com.termux/) (dari F-Droid atau GitHub), ruang kosong sekitar 100 MB, internet.
- **Paket Termux:** `python`, `python-cryptography`, `cloudflared`, `tmux`, `unzip` (opsional buat notif: `termux-api` + aplikasi **Termux:API**).
- **Client:** perangkat apa aja yang ada Python 3 (dites di 3.12; Termux sekarang bawa 3.12–3.14) plus paket `cryptography`.
- Quick tunnel Cloudflare gratis (nggak perlu akun). Nggak ada jaminan uptime dan URL-nya ganti tiap tunnel di-restart.

<a id="gl-quick"></a>
## 5. Gas cepet (5 menit)

```bash
pkg update -y && pkg upgrade -y
pkg install -y python python-cryptography cloudflared tmux unzip
termux-setup-storage
cd ~
unzip ~/storage/downloads/chat-cli-v2.1.zip
cd chat-cli
python -m py_compile server/*.py cli/*.py && echo ALL OK
```

Nyalain server sama tunnel (satu perintah doang):

```bash
bash start-all.sh
```

Nanti muncul URL publik lu dan **kode undangan pertama**. Terus buka sesi Termux baru (geser dari pinggir kiri layar → *New session*):

```bash
cd ~/chat-cli
bash start-client.sh -s https://URL-LU.trycloudflare.com -i XXXX-XXXX
```

Pilih nickname, boleh pasang password kunci aplikasi, terus ketik `help`. Mau bikin kode undangan lagi? `bash invite.sh`.

<a id="gl-install"></a>
## 6. Install lengkap (Termux)

1. **Install Termux** dari F-Droid atau GitHub (yang Play Store udah jadul). Kalo mau notif, install **Termux:API** dari *sumber yang sama*; beda sumber bakal gagal soalnya tanda tangan aplikasinya beda.
2. **Update dan install paket:**
   ```bash
   pkg update -y && pkg upgrade -y
   pkg install -y python python-cryptography cloudflared tmux unzip
   ```
   Kalo pas upgrade ada pertanyaan soal file konfigurasi, pencet Enter aja.
3. **Kasih izin storage** (buat baca zip dari Download dan kirim file dari HP):
   ```bash
   termux-setup-storage
   ```
   Tutup terus buka lagi Termux kalo folder `~/storage` belum nongol.
4. **Ekstrak project** terus cek:
   ```bash
   cd ~
   unzip ~/storage/downloads/chat-cli-v2.1.zip
   cd chat-cli
   python -m py_compile server/*.py cli/*.py && echo SEMUA OK
   ```
5. **Mending `pkg install python-cryptography`**, jangan `pip install cryptography`. Lewat pip kadang harus compile Rust dan gagal di beberapa HP (di sebagian HP sih berhasil, tapi paket `pkg` yang paling aman).
6. `sqlite3` itu **udah bawaan Python**. Jangan `pip install sqlite3` (gagal dan emang nggak perlu). Jangan juga `pip install api`: `api` itu file lokal `server/api.py`, bukan paket pip.
7. **Baterai:** Pengaturan Android → Aplikasi → Termux → Baterai → *Tanpa batasan*. `start-all.sh` juga ngambil wake lock lewat `termux-wake-lock`.

<a id="gl-server"></a>
## 7. Nyalain server

### 7.1 Satu perintah: `start-all.sh` (paling gampang)

```bash
bash start-all.sh
```

- Bikin sesi tmux namanya `wacli` isi dua jendela: **server** dan **tunnel**.
- Dua-duanya restart sendiri kalo mati (server 3 detik, tunnel 5 detik).
- Nunggu URL tunnel sampe 60 detik, nampilin, nyimpen ke `data/tunnel_url.txt`, dan nampilin kode undangan pertama.
- Lognya di `logs/server.log` dan `logs/tunnel.log` (direset tiap start).

| Mau ngapain | Perintah |
|---|---|
| Liat URL tunnel terbaru | `bash url.sh` |
| Bikin kode undangan | `bash invite.sh` |
| Liat log | `tmux attach -t wacli` (pindah jendela: `Ctrl+B` terus `N`; keluar: `Ctrl+B` terus `D`) |
| Matiin semuanya | `bash stop-all.sh` |

> URL tunnel **ganti tiap tunnel restart**. Abis restart jalanin `bash url.sh` dan kasih URL baru ke temen lu (mereka tinggal ketik `server <url>` di dalam client).

### 7.2 Mode manual (tiga sesi Termux)

```bash
# session 1
bash start-server.sh
# session 2
bash start-tunnel.sh
# session 3
bash start-client.sh -s https://YOUR-URL.trycloudflare.com -i XXXX-XXXX
```

Cek servernya: `curl http://127.0.0.1:8080/health` harus keluar `{"status": "ok", ...}`. Tunnel nampilin kotak isi `https://....trycloudflare.com`; itu URL publik lu. Warning `ping_group_range permission denied` santai aja, nggak ngaruh.

### 7.3 Kode undangan (biar nggak sembarang orang masuk)

Dari sananya server **cuma nerima pendaftar yang punya kode undangan**. Nggak ada yang bisa bikin akun tanpa kode valid.

- Pas server pertama nyala (belum ada user dan belum ada undangan valid) dia nampilin `*** KODE UNDANGAN PERTAMA: XXXX-XXXX ***` (berlaku 24 jam, sekali pake).
- Bentuknya kayak `K7F2-9QXM`. Di server cuma disimpen **hash**-nya; kode aslinya cuma muncul sekali pas dibikin, jadi catet.
- Perintah admin (jalanin di HP server):

```bash
bash invite.sh                        # 1 code, single use, 24 h
bash invite.sh -n 5 -t 72             # 5 uses, 72 h
python server/admin.py invites
python server/admin.py revoke 7483c1cb
python server/admin.py users
python server/admin.py mode open      # or: mode invite
```

- `mode open` bikin siapa aja bisa daftar tanpa kode. Pake sebentar doang kalo emang perlu.
- Anti brute force: 10 percobaan daftar per jam per IP, dan kalo kebaca 50 kode salah dalam sejam, pendaftaran dikunci sementara.

<a id="gl-client"></a>
## 8. Pake client

### 8.1 Pertama kali

```bash
bash start-client.sh -s https://URL-LU.trycloudflare.com -i XXXX-XXXX
```

Lu bakal ditanya: URL server (kalo nggak pake `-s`), kode undangan (kalo nggak pake `-i`), nickname (2–20 karakter), dan mau pasang **kunci aplikasi** nggak. Abis itu lu dapet **ID** 10 digit acak. Ketik `me` buat liat. Login lu kesimpen sebagai profil `default`.

Besok-besok tinggal `bash start-client.sh`.

### 8.2 Tambah kontak dan verifikasi

```
add 1234567890 Budi         tambah kontak pake ID dan nama
verify Budi                 cocokin safety number (penjelasan di bawah)
contacts                    daftar kontak (✓ = udah diverifikasi)
```

**Verifikasi itu penting banget.** `verify` nampilin safety number 30 digit. Cocokin sama layar temen lu lewat *jalur lain* (telepon atau ketemu langsung). Kalo angkanya sama persis, berarti nggak ada yang nyelip di tengah (termasuk server). Jawab `y` buat nandain kontaknya terverifikasi.

### 8.3 Ngobrol

```
chat Budi
```

Lu bakal liat 20 pesan terakhir dan header (`🔒 terverifikasi` atau `🔓 belum diverifikasi`). Tinggal ketik buat kirim. Pesan dikasih nomor kayak `#12`; nomornya lokal di HP lu aja. Pesan masuk dari chat lain muncul sebagai `📩 Nama: cuplikan`.

Di dalem chat:

| Ketik | Hasilnya |
|---|---|
| `teks` | kirim pesan |
| `/reply 12 teks` | bales pesan #12 (tampil pake `↩`) |
| `/del 12` | hapus pesan **lu** #12 buat semua orang (semampunya) |
| `/file ~/storage/downloads/foto.jpg caption` | kirim file, maks 1,5 MB, path jangan ada spasi |
| `/get 15` | unduh file di pesan #15 ke `~/wa-downloads/` |
| `/exp 1h` | pesan yang lu kirim ngilang 1 jam abis dikirim (`off`, `30s`, `5m`, `1h`, `1d`, maks `30d`) |
| `/info` | info lawan chat / grup dan status verifikasi |
| `/back` | keluar dari chat (`/q` dan `/exit` juga bisa) |
| `/help` | bantuan di dalem chat |

> Awas: ngetik `exit` biasa di dalem chat itu bakal **ngirim kata "exit"** ke temen lu kwkw. Pake `/back` dulu.

Arti centang: `✓` udah diterima server · `✓✓` udah nyampe di client penerima · `✓✓ dibaca` penerima udah buka/liat · `✗ gagal` nggak bisa kekirim. Pesan grup cuma nampilin `✓`.

### 8.4 Grup

```
group new tim Budi Cici         bikin grup "tim" isi dua orang
chat #tim                       buka chat grup
group list                      daftar grup dan anggotanya
group leave tim                 keluar (yang lain dikasih tau)
```

Anggota ditambahin pake ID atau nama kontak (1–19 orang lain). Semua anggota otomatis dapet undangan terenkripsi. Ngirim ke grup artinya ngirim satu salinan terenkripsi per anggota, jadi satu pesan grup dihitung N−1 pesan buat batas laju. Belum ada admin grup; siapa aja yang tau ID lu bisa masukin lu ke grup, jadi lawan spam pake `group leave` atau `block`.

### 8.5 File

```
chat Budi
/file ~/storage/downloads/foto.jpg nih bro
```

File dienkripsi pake kunci acak 256-bit *sebelum* diunggah; kuncinya dikirim di dalem pesan yang terenkripsi end-to-end. Server cuma liat blob acak selama 3 hari. Penerima ketik `/get <nomor>` (atau `get <nomor>` di luar chat), terus buka pake `termux-open ~/wa-downloads/foto.jpg`. Kalo fotonya lebih dari 1,5 MB, kecilin dulu:

```bash
pkg install imagemagick
magick foto.jpg -resize 1280x1280 -quality 80 kecil.jpg
```

### 8.6 Status, blokir, pesan ngilang

- `status Budi` → `🟢 online` atau `terakhir dilihat 5 menit lalu`.
- `block Budi` / `unblock Budi` → server diem-diem ngebuang pesan dari orang yang diblokir (dia nggak dikasih tau), dan client lu juga cuekin dia.
- `/exp 1h` di dalem chat → pesan baru lu ngilang dari dua HP setelah waktunya (dihitung dari dikirim buat lu, dari diterima buat penerima). Sifatnya kooperatif: penerima masih bisa screenshot atau pake client modifan.

### 8.7 Notif (Android)

1. Install aplikasi **Termux:API** (sumber sama kayak Termux) terus `pkg install termux-api`.
2. Pengaturan Android → Aplikasi → Termux:API → Izin → izinin *Notifikasi*.
3. Tes: `termux-notification --title tes --content halo`.
4. Di client: `notif on` (default), `notif hide` (cuma muncul "Pesan baru", isinya disembunyiin dari layar kunci), `notif off`.

Notif cuma muncul selama client lagi jalan dan cuma buat chat yang lagi nggak lu buka. Tiap chat punya notifnya sendiri, plus getar sebentar kalo `termux-vibrate` ada. Biar tetep hidup di background pake `tmux`, `termux-wake-lock`, dan set baterai Termux ke *Tanpa batasan*.

### 8.8 Kunci aplikasi (enkripsi data lokal pake password)

```
lock on         aktifin (minta password baru, min 8 karakter)
lock passwd     ganti password
lock off        matiin
lock            liat status
```

Pas kunci nyala, pesan, nama kontak, nama grup, sesi enkripsi, token login, dan kunci privat lu disimpen terenkripsi (AES-256-GCM). Password diubah jadi kunci pake scrypt; kunci data yang asli itu acak dan dibungkus sama kunci tadi. Client minta password tiap dibuka (3 kali kesempatan). **Lupa password = data nggak bisa balik, beneran.** ID, waktu, status pesan, dan pesan itu masuk chat yang mana tetep kebaca di file lokal, soalnya database butuh itu buat query.

### 8.9 Backup dan restore

```
backup ~/cadangan.wabk     dienkripsi password pilihan lu (min 8 karakter)
restore ~/cadangan.wabk    nimpa profil sekarang, abis itu jalanin ulang client
```

Jangan pernah pake akun yang sama di dua HP lewat restore: sesi enkripsinya bakal tabrakan dan pesan berhenti bisa dibuka.

### 8.10 Banyak akun di satu HP (buat ngetes)

Lu nggak bisa chat sama diri sendiri, tapi bisa jalanin dua akun pake profil:

```bash
bash start-client.sh -p a -s http://127.0.0.1:8080 -i CODE1
bash start-client.sh -p b -s http://127.0.0.1:8080 -i CODE2
```

Tiap profil punya file sendiri: `~/.chat-cli2/<profil>.json` dan `.db`.

### 8.11 Temen di HP lain (bahkan beda negara)

Siapa aja yang bisa nyampe ke URL tunnel lu bisa chat sama lu, di mana pun dia berada. Dia cuma butuh **tiga file client** di satu folder (`client.py`, `secure.py`, `store.py`), Python, dan `cryptography`:

```bash
mkdir -p ~/chat-cli/cli && cd ~/chat-cli/cli      # put client.py secure.py store.py here
pkg install -y python python-cryptography     # on a PC: pip install cryptography
python client.py -s https://YOUR-URL.trycloudflare.com -i XXXX-XXXX
```

Kasih dia URL **dan** kode undangan lewat jalur yang aman.

<a id="gl-cmds"></a>
## 9. Daftar command

### Client (prompt utama `wa>`)

| Command | Fungsinya |
|---|---|
| `help` | daftar command |
| `me` | ID, nickname, server, profil, status kunci aplikasi |
| `add [id] [nama]` | tambah kontak (ditanyain kalo argumennya kurang) |
| `contacts` | daftar kontak (✓ terverifikasi, `[diblokir]`) |
| `chat <id\|nama\|#grup>` | buka chat |
| `send <id\|nama\|#grup> <teks>` | kirim tanpa buka chat |
| `status <id\|nama>` | online / terakhir dilihat |
| `verify <id\|nama>` | tampilin dan konfirmasi safety number |
| `trust <id\|nama>` | terima kunci yang berubah, atau reset sesi enkripsi yang rusak |
| `block` / `unblock <id\|nama>` | blokir / buka blokir |
| `group new <nama> <anggota…>` | bikin grup |
| `group list` / `group leave <nama>` | daftar / keluar |
| `get <no>` | unduh file di pesan #no |
| `clear <id\|nama\|#grup>` | hapus riwayat lokal sebuah chat |
| `notif on\|hide\|off` | notif Android |
| `lock on\|off\|passwd` | kunci aplikasi |
| `backup [file]` / `restore <file>` | backup / restore terenkripsi |
| `server [url]` | liat / ganti URL server |
| `exit` (`quit`, `q`, Ctrl+D) | keluar |

### Opsi pas nyalain client

| Opsi | Artinya |
|---|---|
| `-s`, `--server URL` | URL server (kesimpen buat next time) |
| `-p`, `--profile NAMA` | profil akun (default `default`) |
| `-i`, `--invite KODE` | kode undangan buat daftar |

### Admin server (`python server/admin.py …`)

`invite [-n PAKAI] [-t JAM]` · `invites` · `revoke ID` · `users` · `mode [open|invite]`

<a id="gl-layout"></a>
## 10. Isi folder

```
chat-cli/
├── server/
│   ├── server.py      server HTTP (127.0.0.1:8080), baca request, bersih-bersih di background
│   ├── api.py         routing, validasi, autentikasi, batas laju, long polling
│   ├── database.py    SQLite: user, blokir, pesan, blob, undangan, setelan
│   ├── admin.py       alat admin kode undangan dan user
│   └── recover_users.py   daftarkan ulang akun dari profil client setelah database server hilang
├── cli/
│   ├── client.py      aplikasi chat-nya
│   ├── secure.py      X25519, kesepakatan ala X3DH, Double Ratchet, AES-GCM, kripto kunci aplikasi
│   └── store.py       penyimpanan lokal SQLite (bisa terenkripsi)
├── data/              database server (wa2.db) dan blob file terenkripsi (dibikin pas jalan)
├── logs/              server.log dan tunnel.log dari start-all.sh
├── start-all.sh       server + tunnel di tmux, restart sendiri
├── stop-all.sh        matiin keduanya
├── url.sh             tampilin URL tunnel terbaru
├── invite.sh          bikin kode undangan
├── start-server.sh    server doang
├── start-tunnel.sh    tunnel doang
├── start-client.sh    peluncur client
├── requirements.txt   cryptography
└── README.md          ini nih
```

<a id="gl-config"></a>
## 11. Setelan

### Variabel lingkungan

| Variabel | Dipake oleh | Default | Artinya |
|---|---|---|---|
| `WA_HOST` | server | `127.0.0.1` | alamat bind (biarin lokal; tunnel nyambungnya ke sini) |
| `WA_PORT` | server, script | `8080` | port |
| `WA_DB` | server | `data/wa2.db` | lokasi database (blob masuk folder `blobs/` di sebelahnya) |
| `WA_SERVER` | client | – | URL server default |
| `WA_INVITE` | client | – | kode undangan buat daftar |
| `WA_WAIT` | client | `25` | lama long-poll dalam detik (0–25) |

### File

| Lokasi | Isinya |
|---|---|
| `~/.chat-cli2/<profil>.json` | setelan non-rahasia: server, ID, nickname, kunci publik, ID pesan terakhir (chmod 600) |
| `~/.chat-cli2/<profil>.db` | kontak, sesi, grup, riwayat, **plus token dan kunci privat lu** (terenkripsi kalo kunci aplikasi nyala) |
| `~/wa-downloads/` | file hasil `/get` |
| `data/wa2.db`, `data/blobs/` | database server dan blob file terenkripsi |

<a id="gl-security"></a>
## 12. Soal keamanan (serius dikit)

### 12.1 Desain kriptonya

| Bagian | Pilihan |
|---|---|
| Identitas | Pasangan kunci X25519 per akun, dibikin di HP; yang diunggah cuma kunci publik |
| Awal sesi | Ala X3DH: `HKDF(DH(IK_A, IK_B) ‖ DH(EK_A, IK_B))` pake kunci ephemeral baru tiap sesi |
| Pesan | **Double Ratchet**: KDF akar HKDF-SHA256, KDF rantai HMAC-SHA256, langkah DH ratchet baru tiap arah ganti |
| Cipher | **AES-256-GCM**; kunci dan nonce diturunin per pesan (nonce nggak pernah kepake dua kali); header dan `pengirim>penerima` ikut diautentikasi |
| Padding | plaintext dipadetin ke kelipatan 128 byte biar panjang pesan nggak ketebak |
| Nggak berurutan | sampe 100 kunci pesan yang kelewat disimpen; pesan ulang (replay) ditolak |
| State | state ratchet disimpen **sebelum** ngirim, jadi kunci pesan nggak pernah kepake dua kali; enkripsi/dekripsi dibikin gantian antar thread |
| File | kunci acak 256-bit + nonce acak per file; kuncinya dikirim di dalem pesan terenkripsi |
| Backup | scrypt (N=2¹⁵) + AES-256-GCM |
| Kunci aplikasi | scrypt (N=2¹⁶) ngebungkus kunci utama acak 256-bit; kolom dienkripsi AES-256-GCM |
| Token | acak 256-bit; server cuma nyimpen hash SHA-256-nya |

### 12.2 Percaya tapi verifikasi

- Pas kontak pertama, kunci publik temen lu **dikunci/dipin**. Kalo nanti server ngasih kunci beda, client nolak ngobrol dan nampilin **KUNCI BERUBAH**. Pake `verify`, terus `trust` cuma kalo lu yakin.
- `verify` ngebandingin safety number dari dua kunci publik. Ini yang bikin server jahat gagal total.
- Pengirim yang nggak dikenal tampil sebagai `~Nickname`; nickname itu dia sendiri yang milih dan belum terverifikasi.

### 12.3 Apa yang bisa dan nggak bisa diliat server

| Server NGGAK bisa liat | Server BISA liat |
|---|---|
| isi pesan, isi file, nama file | siapa ngobrol sama siapa, dan kapan |
| nama grup dan siapa aja anggotanya | ukuran pesan (kira-kira, udah dipadetin), ukuran file |
| kunci privat lu | ID, nickname terdaftar, kunci publik |
| nama kontak lu, password kunci aplikasi | kapan terakhir online, daftar blokir lu |
| | IP lu (lewat header Cloudflare) |

Cloudflare yang nutup TLS buat tunnel, jadi dia bisa liat metadata yang sama plus ciphertext, tapi nggak pernah plaintext.

### 12.4 Pengerasan server

Cuma bind ke `127.0.0.1` · validasi input dan batas ukuran ketat · pesan plaintext ditolak (cuma ciphertext `e2:…`) · batas laju · token di-hash · file database `chmod 600` · nggak ada secret yang di-hardcode · timeout request · `Cache-Control: no-store`, `X-Content-Type-Options: nosniff` · karakter escape terminal dibuang dari teks yang ditampilin.

### 12.5 Kekurangan (jujur aja)

- **Belum diaudit pihak independen.** Ini proyek hobi yang pake bahan-bahan kripto yang udah terkenal; jangan diandelin buat urusan nyawa atau duit gede.
- **Nggak ada pre-key:** pesan sebelum balasan pertama dilindungi kunci identitas jangka panjang penerima. Abis balasan pertama, ratchet ngasih forward secrecy dan pemulihan.
- **Metadata keliatan** sama pemilik server dan Cloudflare (liat 12.3).
- **Riwayat lokal itu plaintext** kecuali kunci aplikasi nyala, dan itu pun ID/waktu/status tetep kebaca. Siapa aja yang megang HP lu yang lagi kebuka bisa baca layar dan notif lu (pake `notif hide`).
- **Satu HP per akun.** Restore backup ke HP kedua yang dipake barengan bakal ngerusak sesi.
- **Pesan ngilang dan hapus-buat-semua itu semampunya**: tergantung client lawan ngobrol lu.
- **Grup nggak ada admin**; siapa aja bisa masukin lu ke grup.
- Password kunci aplikasi yang lemah bisa ditebak offline kalo file HP lu kecolongan.
- Quick tunnel nggak ada jaminan uptime.

<a id="gl-api"></a>
## 13. Referensi API

Semua body JSON kecuali disebut lain. Panggilan yang butuh login pake `Authorization: Bearer <token>`.

| Method & path | Auth | Buat apa |
|---|---|---|
| `GET /` | nggak | `{name, version, status, registration}` (`registration` isinya `invite` atau `open`) |
| `GET /health` | nggak | cek server hidup |
| `POST /register` | nggak | `{nickname, ik, invite?}` → `201 {id, nickname, token}` |
| `GET /users/<id>` | ya | `{id, nickname, ik, last_seen, online}` |
| `POST /messages/send` | ya | `{to, text}`, `text` wajib ciphertext `e2:…` (≤ 4096 karakter) → `201 {id, status, created_at}` |
| `GET /messages/<idgue>?after=N&limit=1-100&wait=0-25&track=1,2,3` | ya | long-poll: `{messages:[{id,from,to,text,created_at}], last_id, status:{id:"sent"\|"delivered"}}` |
| `POST /block`, `POST /unblock` | ya | `{id}` |
| `POST /blobs` | ya | byte mentah (`application/octet-stream`, ≤ 2 MiB) → `{id, size}` |
| `GET /blobs/<id>` | ya | byte terenkripsi mentah |

Kode status: `400` input salah · `401` token salah · `403` kode undangan salah / bukan punya lu · `404` nggak ketemu · `405` method salah · `408` timeout baca · `413` body kegedean · `414` URL kepanjangan · `429` kena batas laju · `500` server error.

Tes cepet:

```bash
curl http://127.0.0.1:8080/
curl http://127.0.0.1:8080/health
```

<a id="gl-limits"></a>
## 14. Batasan & masa simpan

| Hal | Nilai |
|---|---|
| Teks pesan (client) | 1000 karakter |
| Payload terenkripsi / pesan di jaringan | 2800 byte / 4096 karakter |
| Body request JSON | 8 KB |
| File | 1,5 MB (client) · 2 MiB (batas keras server) |
| Nickname / nama grup / nama kontak | 2–20 / 2–20 / maks 30 karakter |
| Ukuran grup | 20 orang termasuk lu |
| Pesan | 120 per menit per user |
| Cek user | 60 per menit per user |
| Daftar akun | 10 per jam per IP; 50 kode undangan salah per jam → dikunci sementara |
| Unggah / unduh file | 20 / 60 per jam per user |
| Long-poll barengan | 3 per user |
| Jendela "online" | 45 detik |
| Pesan yang udah nyampe disimpen di server | 1 jam |
| Pesan yang belum nyampe disimpen | 14 hari |
| File disimpen | 3 hari |
| Pesan ngilang otomatis | sampe 30 hari |
| Toleransi nggak berurutan | 100 pesan per rantai |

<a id="gl-tunnel"></a>
## 15. Catatan Cloudflare Tunnel

- *Quick tunnel* gratis nggak butuh akun: `cloudflared tunnel --url http://127.0.0.1:8080`. `start-all.sh` udah ngurusin ini buat lu.
- URL-nya (`https://kata-acak.trycloudflare.com`) **ganti tiap restart**; nggak ada jaminan uptime.
- Kalo QUIC diblokir jaringan lu: `bash start-tunnel.sh --protocol http2`.
- Pake `cloudflared` dari `pkg`, jangan binary Linux dari GitHub (suka bermasalah DNS di Android).
- Mau URL permanen? Lu butuh akun Cloudflare gratis dan sebuah domain: `cloudflared tunnel login`, `cloudflared tunnel create wa`, `cloudflared tunnel route dns wa chat.domainlu.com`, terus jalanin tunnel pake file konfigurasi. Belum diotomatisasi di project ini.

<a id="gl-update"></a>
## 16. Update & reset

- **Update:** ekstrak versi baru di sebelah yang lama, salin folder `data/` (database server), dan biarin `~/.chat-cli2/` (data client) apa adanya. Dari v2.0, client mindahin rahasianya ke database lokal otomatis.
- **Reset profil client:** `rm ~/.chat-cli2/<profil>.*` (lu daftar lagi dan dapet ID baru).
- **Reset server:** matiin dulu, terus `rm -rf data/wa2.db* data/blobs`. Semua akun ilang dan tiap client harus reset profilnya.
- **Hapus total:** `rm -rf ~/chat-cli ~/.chat-cli2 ~/wa-downloads`.

<a id="gl-trouble"></a>
## 17. Kalo error (jangan panik)

| Gejala | Penyebab dan solusi |
|---|---|
| `ModuleNotFoundError: No module named 'api'` | `server/api.py` nggak ada. Cek `ls server`. Ekstrak ulang. **Jangan** `pip install api`. |
| `pip install sqlite3` gagal | Wajar. `sqlite3` udah bawaan Python. |
| `Butuh paket 'cryptography'` | `pkg install python-cryptography` |
| `start-tunnel.sh: command not found` | Jalanin `bash start-tunnel.sh` (atau `chmod +x` terus `./start-tunnel.sh`). |
| Tunnel kayak "nyangkut" abis nampilin log | Normal; dia jalan di depan layar. URL ada di dalem kotak. Jangan pencet Ctrl+C. |
| `ping_group_range … permission denied` | Warning cloudflared yang nggak ngaruh. |
| `Gagal listen … Address already in use` | Server lain masih jalan: `bash stop-all.sh` atau `pkill -f server.py`. |
| Client: `Connection refused` | Server belum nyala, URL salah, atau port salah. |
| `HTTP 530 / 1033 / 502`, "bukan dari chat-cli server" | Tunnel mati atau URL ganti. `bash url.sh`, terus `server <url-baru>` di client. |
| Error DNS / `[::1]:53` di cloudflared | Pake cloudflared dari `pkg`; coba `--protocol http2`. |
| `Kode undangan salah atau kedaluwarsa` (403) | Kode salah, udah kepake, kedaluwarsa, atau dicabut. Bikin baru: `bash invite.sh`. |
| `429` pas daftar | Kebanyakan percobaan. Tunggu sejam atau minta admin. |
| `Token ditolak` / "akun tidak dikenal" | Database server direset atau ketuker. Kalo profil client masih ada di HP yang sama kayak server: matiin server, jalanin `python server/recover_users.py`, nyalain server lagi; ID, riwayat, dan sesi enkripsi lu tetep jalan. Kalo nggak, `rm ~/.chat-cli2/<profil>.*` terus daftar lagi. |
| Peringatan **KUNCI BERUBAH** | Server ngasih kunci beda buat ID itu. Jalanin `verify`; pake `trust` cuma kalo yakin. |
| `Pesan dari X tidak bisa dibuka` | Sesi enkripsi nggak sinkron (misal backup di-restore di dua HP). Jalanin `trust <kontak>` dan jawab `y` di pertanyaan *reset sesi*; pesan baru bakal mulai sesi segar. |
| `Terlalu banyak koneksi polling` | Ada lebih dari 3 client login pake akun yang sama. |
| File ditolak | Lebih dari 1,5 MB, atau path ada spasinya (ganti nama file). |
| `~/storage` nggak ada | Jalanin `termux-setup-storage`, terus restart Termux. |
| Notif nggak muncul | Pastiin `termux-notification --title t --content c` jalan; Termux:API harus dari sumber yang sama kayak Termux; izin udah dikasih; `notif on`; client lagi jalan. |
| Semuanya mati pas layar padam | Baterai Termux = Tanpa batasan, `termux-wake-lock`, jalanin lewat `start-all.sh` (tmux). |
| Prompt password muncul "Can not control echo" | Client nggak nempel ke terminal beneran; nggak bahaya. |
| Buka kunci agak lama (sekitar sedetik) | scrypt emang sengaja lambat (biar susah di-brute force). |
| `tmux: command not found` | `pkg install tmux` |
| Pesan grup nggak masuk | Lu harus udah nerima undangan grupnya, dan pengirimnya harus anggota. Kalo udah keluar, ya udah nggak di grup. |
| Nickname ditolak | 2–20 karakter: huruf, angka, spasi, `.`, `-`, `_`. |
| Error Python aneh di versi Python baru | Kirim traceback lengkapnya; kodenya cuma pake API yang stabil. |

<a id="gl-faq"></a>
## 18. FAQ

**Ini WhatsApp?** Bukan, bro. Ini messenger mandiri dengan ide mirip; nggak ada API resmi yang dipake.

**Pemilik server bisa baca chat gue?** Nggak, yang dia pegang cuma ciphertext. Dia cuma bisa liat metadata (siapa, kapan, ukuran).

**Bisa chat sama diri sendiri?** Server nolak. Pake dua profil (bagian 8.10).

**HP server harus nyala terus?** Iya. Pesan nunggu sampe 14 hari buat penerima yang lagi offline.

**Multi-HP?** Nggak bisa, satu HP per akun.

**Maksimal anggota grup?** 20 orang.

**Bisa ganti nickname atau hapus akun?** Belum: daftar akun baru terus reset profil yang lama.

**Server bisa di PC atau VPS?** Bisa, mesin apa aja yang ada Python 3; cuma script bantunya yang ngira lu pake Termux.

**Jalan di iPhone?** Client jalan di mana aja Python jalan; Termux-nya sendiri cuma buat Android.

**Gimana caranya yakin temen gue beneran temen gue?** `verify` terus cocokin safety number lewat telepon atau ketemu langsung.

<a id="gl-todo"></a>
## 19. Belum ada (ide)

Indikator "lagi ngetik" (butuh tampilan layar penuh), bot AI (butuh API online), pre-key, admin grup dan kelola anggota, edit pesan, reaksi emoji, pesan suara, kirim lokasi, mute/pin, tampilan curses, named tunnel otomatis, dukungan multi-HP.

<a id="gl-changelog"></a>
## 20. Riwayat versi

- **v2.1**: daftar akun cuma pake undangan, `admin.py`, `start-all.sh` / `stop-all.sh` / `url.sh` / `invite.sh`, **kunci aplikasi**, notif per chat, opsi reset sesi di `trust`, pilih sesi aktif yang paling baru, dan benerin bug balapan antara kirim dan terima yang bisa ngerusak state ratchet.
- **v2.0**: enkripsi end-to-end (X25519 + Double Ratchet + AES-256-GCM), grup, file, long polling, centang, pesan ngilang, blokir, status, backup.
- **v1.x**: prototipe pertama tanpa enkripsi pake API HTTP dan SQLite, terus kunci AES per kontak yang opsional.

<a id="gl-disclaimer"></a>
## 21. Disclaimer

Dikasih "apa adanya", tanpa garansi apa pun. Pake dengan risiko sendiri dan patuhin hukum serta aturan platform yang berlaku buat lu. chat-cli nggak ada hubungannya sama WhatsApp, Meta, Cloudflare, atau Termux.

[⬆ balik ke atas](#top)
