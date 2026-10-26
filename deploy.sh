#!/usr/bin/env bash
# Prepare this checkout for deployment. Service/hostname management belongs to the host.
set -euo pipefail
cd "$(dirname "$0")"
: "${PYTHON:=python3.13}"
if [[ ! -f .env && -z "${R2_BUCKET_NAME:-}" ]]; then
  echo 'Configure .env (see .env.example) or environment variables before deployment.' >&2
  exit 1
fi
"$PYTHON" -m venv .venv
.venv/bin/python -m pip install -r backend/xmmcg/requirements.lock
.venv/bin/python backend/xmmcg/manage.py check --deploy
# Migration is deliberately explicit: back up the database and media first.
echo 'Next: follow doc/DEPLOYMENT.md for migration, R2 CORS, collectstatic, and service startup.'
