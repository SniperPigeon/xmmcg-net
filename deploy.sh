#!/usr/bin/env bash
# 首次安装/初始化；日常更新由 update.sh 或 CI 触发，不重复修改系统配置。
set -Eeuo pipefail
[[ "$EUID" -eq 0 ]] || { echo '请使用 sudo bash deploy.sh' >&2; exit 1; }
PROJECT_DIR="/opt/xmmcg"
PYTHON_BIN="${XMMCG_PYTHON_BIN:-python3}"
[[ "$PROJECT_DIR" = /* && "$PROJECT_DIR" != / ]] || { echo '部署目录必须为绝对路径' >&2; exit 1; }

echo '安装部署依赖...'
apt-get update
apt-get install -y python3 python3-pip python3-venv python3-dev build-essential nginx git sqlite3 curl rsync util-linux certbot python3-certbot-nginx
"$PYTHON_BIN" -c 'import sys; assert sys.version_info >= (3, 12), "需要 Python 3.12+；可通过 XMMCG_PYTHON_BIN 指定已安装的解释器"'
if ! command -v node >/dev/null || ! node -e 'const [a,b]=process.versions.node.split(".").map(Number); process.exit(a>22 || (a===22 && b>=12) ? 0 : 1)'; then
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
    apt-get install -y nodejs
fi
node -e 'const [major, minor] = process.versions.node.split(".").map(Number); if (major < 22 || (major === 22 && minor < 12)) { console.error("需要 Node.js 22.12+"); process.exit(1) }'

if [[ ! -d "$PROJECT_DIR/.git" ]]; then
    git clone --branch main https://github.com/SniperPigeon/xmmcg-net.git "$PROJECT_DIR"
fi
cd "$PROJECT_DIR"
if [[ ! -x venv/bin/python ]]; then "$PYTHON_BIN" -m venv venv; fi
if [[ ! -f .env && ! -f login_credentials.env ]]; then
    install -m 600 .env.example .env
    "$PYTHON_BIN" -c 'from pathlib import Path; import secrets; p=Path(".env"); p.write_text(p.read_text().replace("replace-with-a-long-random-secret", secrets.token_urlsafe(50)))'
    echo '已创建 .env，请填写真实配置（SECRET_KEY 已随机生成，请配置 R2 和域名）后重新运行。'
    exit 1
fi

install -d -o www-data -g www-data /var/www/xmmcg/frontend /var/log/gunicorn /run/gunicorn
# 保留已有配置，尤其是 Certbot 写入的 HTTPS 段落。
if [[ ! -e /etc/nginx/sites-available/xmmcg ]]; then
    install -m 644 backend/nginx.conf /etc/nginx/sites-available/xmmcg
else
    echo '保留已有 Nginx 配置；如需更新，请对照 backend/nginx.conf 合并修改。'
fi
if [[ ! -e /etc/nginx/sites-enabled/xmmcg ]]; then
    ln -s /etc/nginx/sites-available/xmmcg /etc/nginx/sites-enabled/xmmcg
fi
if [[ ! -e /etc/systemd/system/gunicorn.service ]]; then
    install -m 644 backend/gunicorn.service /etc/systemd/system/gunicorn.service
else
    echo '保留已有 Gunicorn 服务配置，请确认 socket 目录在重启后可用。'
fi
nginx -t
systemctl daemon-reload
systemctl enable nginx gunicorn
# 继续使用原有应用用户；配置文件不授予其他用户读取权限。
chown -R www-data:www-data "$PROJECT_DIR"
for file in .env login_credentials.env; do
    if [[ -f "$file" ]]; then chmod 640 "$file"; fi
done
export XMMCG_PROJECT_DIR="$PROJECT_DIR"
bash scripts/build.sh
echo '部署完成。域名 HTTPS 继续通过原有 Certbot/Nginx 配置管理。'
