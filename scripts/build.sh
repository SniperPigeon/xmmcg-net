#!/usr/bin/env bash
# 构建服务器当前检出的版本。CI 先由 remote_deploy.sh 固定到已测试的 SHA。
set -Eeuo pipefail
[[ "$EUID" -eq 0 ]] || { echo '请使用 sudo 运行服务器构建脚本' >&2; exit 1; }
PROJECT_DIR="${XMMCG_PROJECT_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)}"
FRONTEND_DIR="${XMMCG_FRONTEND_DIR:-/var/www/xmmcg/frontend}"
BACKUP_DIR="${XMMCG_BACKUP_DIR:-/var/back/xmmcg}"
PYTHON="$PROJECT_DIR/venv/bin/python"
FRONTEND_ONLY=false
if [[ "${1:-}" = --frontend-only ]]; then FRONTEND_ONLY=true; shift; fi
EXPECTED_SHA="${1:-}"
cd "$PROJECT_DIR"
git_cmd() { git -c safe.directory="$PROJECT_DIR" "$@"; }
if [[ "${XMMCG_DEPLOY_LOCKED:-}" != 1 ]]; then
    exec 9>"$(git_cmd rev-parse --git-path xmmcg-deploy.lock)"
    flock -n 9 || { echo '另一次部署正在执行' >&2; exit 1; }
fi
REVISION="$(git_cmd rev-parse HEAD)"
[[ -z "$EXPECTED_SHA" || "$REVISION" = "$EXPECTED_SHA" ]] || { echo '服务器提交与 CI 验证的提交不一致' >&2; exit 1; }
[[ "$FRONTEND_DIR" = /* && "$FRONTEND_DIR" != / ]] || { echo '前端目录必须为绝对路径' >&2; exit 1; }
command -v node >/dev/null
node -e 'const [major, minor] = process.versions.node.split(".").map(Number); if (major < 22 || (major === 22 && minor < 12)) { console.error("需要 Node.js 22.12+"); process.exit(1) }'
nginx -t
if ! "$FRONTEND_ONLY"; then
    [[ -x "$PYTHON" ]] || { echo '请先运行 deploy.sh 创建生产虚拟环境' >&2; exit 1; }
    "$PYTHON" -c 'import sys; assert sys.version_info >= (3, 12), "需要 Python 3.12+"'
    [[ -f "$PROJECT_DIR/.env" || -f "$PROJECT_DIR/login_credentials.env" ]] || { echo '缺少服务器配置文件' >&2; exit 1; }
fi
trap 'echo "服务器构建失败，未自动回滚数据库；请检查日志及 $BACKUP_DIR 中的备份。" >&2' ERR

cd "$PROJECT_DIR/front"
echo '安装锁定的前端依赖并构建...'
npm ci
npm run build
[[ -s dist/index.html ]] || { echo '构建未生成 index.html' >&2; exit 1; }

if ! "$FRONTEND_ONLY"; then
    systemctl stop gunicorn
    cd "$PROJECT_DIR/backend/xmmcg"
    # 构建、迁移和收集静态文件期间，绝不向 Net 上传谱面。
    export ENABLE_CHART_FORWARD_TO_MAJDATA=False
    "$PYTHON" -m pip install -r requirements.lock
    "$PYTHON" manage.py check
    "$PYTHON" manage.py preflight_upgrade
    "$PYTHON" "$PROJECT_DIR/scripts/backup_database.py" "$BACKUP_DIR" "$REVISION"
    "$PYTHON" manage.py migrate --noinput
    "$PYTHON" manage.py collectstatic --noinput
    # SQLite 文件及父目录需要应用用户可写；路径以 Django 配置为准。
    DATABASE_PATH="$("$PYTHON" -c 'import os; os.environ.setdefault("DJANGO_SETTINGS_MODULE", "xmmcg.settings"); from django.conf import settings; from pathlib import Path; print(Path(settings.DATABASES["default"]["NAME"]).resolve())')"
    chown www-data:www-data "$DATABASE_PATH" "$(dirname -- "$DATABASE_PATH")"
    chmod 660 "$DATABASE_PATH"
    chmod g+w "$(dirname -- "$DATABASE_PATH")"
fi

# 先发布资源，最后替换入口。旧哈希资源继续保留，兼容已打开的页面。
install -d -o www-data -g www-data "$FRONTEND_DIR"
rsync -a --exclude=index.html "$PROJECT_DIR/front/dist/" "$FRONTEND_DIR/"
install -m 644 "$PROJECT_DIR/front/dist/index.html" "$FRONTEND_DIR/.index.html.new"
chown -R www-data:www-data "$FRONTEND_DIR"
if ! "$FRONTEND_ONLY"; then
    install -d /etc/systemd/system/gunicorn.service.d
    install -m 644 "$PROJECT_DIR/backend/gunicorn-runtime.conf" /etc/systemd/system/gunicorn.service.d/xmmcg-runtime.conf
    systemctl daemon-reload
    systemctl restart gunicorn
    systemctl is-active --quiet gunicorn
    HEALTH_HOST="$("$PYTHON" -c 'import os; os.environ.setdefault("DJANGO_SETTINGS_MODULE", "xmmcg.settings"); from django.conf import settings; print(settings.PRODUCTION_DOMAIN)')"
    curl --fail --silent --show-error --retry 5 --retry-connrefused --retry-delay 1 \
        --unix-socket /run/gunicorn/xmmcg.sock \
        -H "Host: $HEALTH_HOST" -H 'X-Forwarded-Proto: https' \
        http://localhost/api/contest/status/ -o /dev/null
fi
mv -f "$FRONTEND_DIR/.index.html.new" "$FRONTEND_DIR/index.html"
# 不覆盖服务器上的 Nginx 文件，避免清掉 Certbot 管理的 HTTPS 配置。
nginx -t
systemctl reload nginx
echo "构建发布完成：$REVISION"
