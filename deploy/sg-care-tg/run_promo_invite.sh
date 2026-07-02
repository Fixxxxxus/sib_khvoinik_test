#!/usr/bin/env bash
set -euo pipefail
if [ -f /etc/environment ]; then
    set -a
    . /etc/environment
    set +a
fi
cd /app
python /app/promo_invite.py
