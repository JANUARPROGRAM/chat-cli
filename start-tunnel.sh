#!/usr/bin/env bash
exec cloudflared tunnel --url http://127.0.0.1:${WA_PORT:-8080} "$@"
