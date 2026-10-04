#!/usr/bin/env bash
# Buat kode undangan: bash invite.sh | bash invite.sh -n 5 -t 72 | bash invite.sh --help
cd "$(dirname "$0")" || exit 1
exec python server/admin.py invite "$@"
