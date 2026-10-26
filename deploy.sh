#!/bin/bash
# XMMCG 完整部署脚本 - Google Compute Engine (Ubuntu/Debian)
# 支持后端 + 前端一键部署
# 使用方法: sudo bash deploy.sh

set -e  # 遇到错误立即退出

echo "=========================================="
echo "  XMMCG 完整部署脚本 (后端 + 前端)"
echo "=========================================="

# 检查是否为 root 用户
if [ "$EUID" -ne 0 ]; then
    echo "❌ 请使用 sudo 运行此脚本"
    exit 1
fi

# 配置变量
PROJECT_DIR="/opt/xmmcg"
VENV_DIR="$PROJECT_DIR/venv"
BACKEND_DIR="$PROJECT_DIR/backend/xmmcg"
FRONTEND_DIR="$PROJECT_DIR/front"
FRONTEND_DIST_DIR="/var/www/xmmcg/frontend"
LOG_DIR="/var/log/gunicorn"
SOCKET_DIR="/var/run/gunicorn"


echo "📦 步骤 1/10: 更新系统包..."
apt-get update
apt-get upgrade -y

echo "📦 步骤 2/10: 安装依赖..."
# 检测是否为 Debian 并安装相应包
if [ -f /etc/debian_version ]; then
    DEBIAN_VERSION=$(cat /etc/debian_version | cut -d. -f1)
    echo "检测到 Debian $DEBIAN_VERSION"
fi

apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    nginx \
    git \
    sqlite3 \
    curl

# Certbot 在 Debian 上的安装
if command -v certbot &> /dev/null; then
    echo "Certbot 已安装"
else
    echo "安装 Certbot..."
    apt-get install -y certbot python3-certbot-nginx || {
        echo "通过 snap 安装 Certbot..."
        apt-get install -y snapd
        snap install core
        snap refresh core
        snap install --classic certbot
        ln -sf /snap/bin/certbot /usr/bin/certbot
    }
fi

echo "📁 步骤 3/10: 创建项目目录..."
mkdir -p $PROJECT_DIR
mkdir -p $FRONTEND_DIST_DIR
mkdir -p $LOG_DIR
mkdir -p $SOCKET_DIR

echo "📥 步骤 4/10: 克隆代码仓库..."
if [ -d "$PROJECT_DIR/.git" ]; then
    echo "代码已存在，执行 git pull..."
    cd $PROJECT_DIR
    git config --global --add safe.directory $PROJECT_DIR
    git pull
else
    git clone https://github.com/SniperPigeon/xmmcg-net.git $PROJECT_DIR
    cd $PROJECT_DIR
    git config --global --add safe.directory $PROJECT_DIR
fi

echo "🐍 步骤 5/10: 配置 Python 虚拟环境并安装依赖..."
if [ ! -d "$VENV_DIR" ]; then
    echo "创建新的虚拟环境..."
    python3 -m venv $VENV_DIR
fi
source $VENV_DIR/bin/activate
pip install --upgrade pip
pip install -r $BACKEND_DIR/requirements.lock

echo "⚙️ 步骤 6/10: 配置环境变量..."
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "创建 .env 文件..."
    cat > $PROJECT_DIR/.env << EOF
# Django Settings
SECRET_KEY=$($VENV_DIR/bin/python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')
DEBUG=False
ALLOWED_HOSTS=*

# Production Domain (修改为你的域名)
PRODUCTION_DOMAIN=your-domain.com

# Majdata.net Settings
ENABLE_CHART_FORWARD_TO_MAJDATA=True
MAJDATA_USERNAME=xmmcg5
MAJDATA_PASSWD_HASHED=your-password-hash

# R2 对象存储（凭证只放后端）
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET_NAME=
R2_CORS_ORIGINS=https://your-domain.com

EOF
    echo "⚠️ 请编辑 $PROJECT_DIR/.env，填好 R2 等配置后重新运行。"
    exit 1
fi

echo "🗄️ 步骤 7/10: 初始化数据库..."
cd $BACKEND_DIR
$VENV_DIR/bin/python manage.py preflight_upgrade
$VENV_DIR/bin/python manage.py migrate

echo "🔧 修复数据库权限 (SQLite 需要目录和文件写权限)..."
chown www-data:www-data db.sqlite3
chmod 664 db.sqlite3
chown www-data:www-data .
chmod 775 .
echo "✅ 数据库权限已修复"

$VENV_DIR/bin/python manage.py collectstatic --noinput

echo "📦 步骤 8/10: 安装 Node.js 和构建前端..."
if command -v node &> /dev/null; then
    echo "Node.js 已安装: $(node --version)"
else
    echo "安装 Node.js 22.x..."
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
    apt-get install -y nodejs
fi

echo "🔨 构建前端应用..."
cd $FRONTEND_DIR
npm install
npm run build

echo "📁 部署前端文件..."
cp -r $FRONTEND_DIR/dist/* $FRONTEND_DIST_DIR/

echo "👤 步骤 9/10: 设置权限..."
chown -R www-data:www-data $PROJECT_DIR
chown -R www-data:www-data $FRONTEND_DIST_DIR
chown -R www-data:www-data $LOG_DIR
chown -R www-data:www-data $SOCKET_DIR

echo "🔧 步骤 10/10: 配置服务..."
cp $PROJECT_DIR/backend/gunicorn.service /etc/systemd/system/gunicorn.service
systemctl daemon-reload
systemctl enable gunicorn
systemctl start gunicorn

cp $PROJECT_DIR/backend/nginx.conf /etc/nginx/sites-available/xmmcg
ln -sf /etc/nginx/sites-available/xmmcg /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx

echo ""
echo "=========================================="
echo "✅ 部署完成！"
echo "=========================================="
echo ""
echo "📋 下一步操作："
echo "1. 编辑环境变量: nano /opt/xmmcg/.env"
echo "2. 设置域名: 修改 PRODUCTION_DOMAIN 和 ALLOWED_HOSTS"
echo "3. 配置 SSL: sudo certbot --nginx -d your-domain.com"
echo "4. 创建管理员: cd /opt/xmmcg/backend/xmmcg && source /opt/xmmcg/venv/bin/activate && python manage.py createsuperuser"
echo "5. 配置状态监控和备份服务，请参考 scripts 文件夹"
echo ""
echo "🔍 服务状态检查："
echo "  - Gunicorn: sudo systemctl status gunicorn"
echo "  - Nginx: sudo systemctl status nginx"
echo "  - 日志: sudo journalctl -u gunicorn -f"
echo ""
echo "🌐 访问地址："
SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || echo "your-server-ip")
echo "  - 网站首页: http://$SERVER_IP"
echo "  - 管理后台: http://$SERVER_IP/admin/"
echo "  - API 文档: http://$SERVER_IP/api/"
echo ""
echo "可选：下载1Panel，以获得更好的监视"
echo '请按 1Panel 官方安装说明操作。'
echo "📝 更新代码请运行: sudo bash /opt/xmmcg/update.sh"
echo ""
