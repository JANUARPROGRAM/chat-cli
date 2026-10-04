#!/usr/bin/env bash
if tmux kill-session -t wacli 2>/dev/null; then echo "✓ Server & tunnel dihentikan."; else echo "Tidak ada sesi 'wacli' yang berjalan."; fi
command -v termux-wake-unlock >/dev/null 2>&1 && termux-wake-unlock
