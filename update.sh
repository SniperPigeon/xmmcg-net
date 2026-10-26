#!/bin/bash
# XMMCG 代码更新脚本
# 用于更新已部署的应用
# 使用方法: sudo bash update.sh

set -e

echo "=========================================="
echo "  XMMCG 代码更新脚本"
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

echo "📥 步骤 1/6: 拉取最新代码..."
cd $PROJECT_DIR
git config --global --add safe.directory $PROJECT_DIR
git pull

echo "🐍 步骤 2/6: 更新后端依赖..."
source $VENV_DIR/bin/activate
pip install -r $BACKEND_DIR/requirements.lock

echo "🗄️ 步骤 3/6: 应用数据库迁移..."
cd $BACKEND_DIR
python manage.py preflight_upgrade
python manage.py migrate

echo "📦 步骤 4/6: 收集静态文件..."
python manage.py collectstatic --noinput

echo "🔨 步骤 5/6: 重新构建前端..."
cd $FRONTEND_DIR
npm install
npm run build
cp -r $FRONTEND_DIR/dist/* $FRONTEND_DIST_DIR/

echo "🔄 步骤 6/6: 重启服务..."
chown -R www-data:www-data $PROJECT_DIR
chown -R www-data:www-data /var/www/xmmcg
systemctl restart gunicorn
systemctl reload nginx

echo ""
echo "=========================================="
echo "✅ 更新完成！"
echo "=========================================="
echo ""
echo "🔍 服务状态："
systemctl status gunicorn --no-pager | head -5
systemctl status nginx --no-pager | head -5
echo ""
echo "📝 查看日志: sudo journalctl -u gunicorn -f"
echo ""
