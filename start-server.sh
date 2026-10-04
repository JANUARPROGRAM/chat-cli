#!/usr/bin/env bash
cd "$(dirname "$0")" || exit 1
mkdir -p data
command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock
exec python server/server.py
