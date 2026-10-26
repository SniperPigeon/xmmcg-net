#!/usr/bin/env bash
# 由 CI 通过 SSH 的标准输入执行：只部署通过检查且仍为 main 最新的提交。
set -Eeuo pipefail

PROJECT_DIR="${1:-/opt/xmmcg}"
EXPECTED_SHA="${2:-}"
[[ "$PROJECT_DIR" = /* && "$PROJECT_DIR" != / ]] || { echo '部署目录必须为绝对路径' >&2; exit 1; }
[[ -z "$EXPECTED_SHA" || "$EXPECTED_SHA" =~ ^[0-9a-f]{40}$ ]] || { echo '提交 SHA 格式错误' >&2; exit 1; }
cd "$PROJECT_DIR"
PROJECT_DIR="$(pwd -P)"
git_cmd() { git -c safe.directory="$PROJECT_DIR" "$@"; }
[[ "$(git_cmd rev-parse --show-toplevel)" = "$PROJECT_DIR" ]] || { echo '部署目录不是仓库根目录' >&2; exit 1; }
exec 9>"$(git_cmd rev-parse --git-path xmmcg-deploy.lock)"
flock -n 9 || { echo '另一次部署正在执行' >&2; exit 1; }
# 旧版曾把数据库提交到 Git；切到新版会删除该路径，必须先人工备份并迁出跟踪。
if git_cmd ls-files --error-unmatch backend/xmmcg/db.sqlite3 >/dev/null 2>&1; then
    echo '旧版数据库仍由 Git 跟踪。请先按部署文档备份并整理，脚本不会覆盖或删除生产数据库。' >&2
    exit 1
fi
[[ -z "$(git_cmd status --porcelain --untracked-files=no)" ]] || { echo '仓库有未提交修改，停止部署以保留现场' >&2; exit 1; }
git_cmd fetch --no-tags origin main
LATEST_SHA="$(git_cmd rev-parse FETCH_HEAD)"
if [[ -n "$EXPECTED_SHA" && "$EXPECTED_SHA" != "$LATEST_SHA" ]]; then
    echo '跳过过期部署：main 已有更新提交，等待对应 CI 通过。'
    exit 0
fi
EXPECTED_SHA="${EXPECTED_SHA:-$LATEST_SHA}"
# 运行环境不满足时在停服前退出，不在增量更新中更换系统运行时。
node -e 'const [major, minor] = process.versions.node.split(".").map(Number); if (major < 22 || (major === 22 && minor < 12)) { console.error("需要 Node.js 22.12+，请先准备服务器构建环境"); process.exit(1) }'
"$PROJECT_DIR/venv/bin/python" -c 'import sys; assert sys.version_info >= (3, 12), "需要 Python 3.12+"'
for tool in npm rsync curl nginx; do command -v "$tool" >/dev/null; done
nginx -t
# 保留原目录部署方式；切换代码前暂停请求，避免新旧代码混用。
trap 'echo "部署失败；请检查日志和迁移前备份，Gunicorn 不会自动恢复到未知状态。" >&2' ERR
systemctl stop gunicorn
git_cmd checkout --detach "$EXPECTED_SHA"
export XMMCG_PROJECT_DIR="$PROJECT_DIR" XMMCG_DEPLOY_LOCKED=1
exec bash "$PROJECT_DIR/scripts/build.sh" "$EXPECTED_SHA"
