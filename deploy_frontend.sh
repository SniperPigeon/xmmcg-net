#!/usr/bin/env bash
# 仅重建和发布当前版本的前端，不修改数据库或服务器 Nginx 配置。
set -Eeuo pipefail
PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$PROJECT_DIR/scripts/build.sh" --frontend-only
