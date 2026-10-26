#!/usr/bin/env bash
# 更新到 main 的指定提交；省略 SHA 时手动部署 main 最新提交。
set -Eeuo pipefail
[[ "$EUID" -eq 0 ]] || { echo '请使用 sudo bash update.sh [提交SHA]' >&2; exit 1; }
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$PROJECT_DIR/scripts/remote_deploy.sh" "$PROJECT_DIR" "${1:-}"
