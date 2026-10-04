#!/usr/bin/env bash
# Tampilkan URL tunnel terbaru
cd "$(dirname "$0")" || exit 1
grep -ao 'https://[a-z0-9-]*\.trycloudflare\.com' logs/tunnel.log 2>/dev/null | grep -v '^https://api\.' | tail -1 \
  || echo "Belum ada URL. Jalankan: bash start-all.sh"
