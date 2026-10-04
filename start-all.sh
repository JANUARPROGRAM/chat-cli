#!/usr/bin/env bash
# Jalankan server + Cloudflare Tunnel di tmux (auto-restart), lalu tampilkan URL publik.
cd "$(dirname "$0")" || exit 1
PORT="${WA_PORT:-8080}"
for c in tmux python cloudflared; do
  command -v "$c" >/dev/null 2>&1 || { echo "Belum ada '$c'. Jalankan: pkg install $c"; exit 1; }
done
mkdir -p data logs
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock
tmux kill-session -t wacli 2>/dev/null
: > logs/server.log
: > logs/tunnel.log
tmux new-session -d -s wacli -n server \
  "while true; do python server/server.py 2>&1 | tee -a logs/server.log; echo '[server berhenti - restart 3 detik]'; sleep 3; done"
tmux new-window -t wacli -n tunnel \
  "while true; do cloudflared tunnel --no-autoupdate --url http://127.0.0.1:$PORT 2>&1 | tee -a logs/tunnel.log; echo '[tunnel berhenti - restart 5 detik]'; sleep 5; done"
echo "Menunggu URL tunnel (maks 60 detik)..."
URL=""
for _ in $(seq 1 60); do
  URL=$(grep -ao 'https://[a-z0-9-]*\.trycloudflare\.com' logs/tunnel.log | grep -v '^https://api\.' | tail -1)
  [ -n "$URL" ] && break
  sleep 1
done
sleep 1
if [ -z "$URL" ]; then
  echo "URL belum muncul. Cek log: tmux attach -t wacli  (pindah jendela: Ctrl+B lalu N)"
  exit 1
fi
echo "$URL" > data/tunnel_url.txt
echo
echo "✓ Server & tunnel berjalan (tmux sesi 'wacli', restart otomatis kalau mati)"
echo "  URL publik : $URL"
KODE=$(grep -a "KODE UNDANGAN" logs/server.log | head -1)
[ -n "$KODE" ] && echo "  $KODE"
echo
echo "  Kode undangan baru : bash invite.sh"
echo "  URL terbaru        : bash url.sh   (URL berubah kalau tunnel restart)"
echo "  Lihat log          : tmux attach -t wacli   (keluar: Ctrl+B lalu D)"
echo "  Hentikan           : bash stop-all.sh"
echo "  Client             : bash start-client.sh -s $URL"
