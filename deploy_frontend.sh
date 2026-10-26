#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/front"
npm ci
npm run build
echo 'Publish front/dist to your static host; configure SPA fallback and /api + /admin + /static routing.'
