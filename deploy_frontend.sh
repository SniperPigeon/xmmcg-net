#!/bin/bash
# 前端构建和部署脚本
# 在服务器上运行: sudo bash deploy_frontend.sh

set -e

echo "=========================================="
echo "  XMMCG 前端部署脚本"
echo "=========================================="

# 检查是否为 root 用户
if [ "$EUID" -ne 0 ]; then
    echo "❌ 请使用 sudo 运行此脚本"
    exit 1
fi

echo "📦 步骤 1/5: 安装 Node.js..."
if command -v node &> /dev/null; then
    echo "Node.js 已安装: $(node --version)"
else
    echo "安装 Node.js 22.x..."
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
    apt-get install -y nodejs
fi

echo "📥 步骤 2/5: 安装前端依赖..."
cd /opt/xmmcg/front
npm install

echo "🔨 步骤 3/5: 构建前端..."
npm run build

echo "📁 步骤 4/5: 部署前端文件..."
mkdir -p /var/www/xmmcg/frontend
cp -r /opt/xmmcg/front/dist/* /var/www/xmmcg/frontend/
chown -R www-data:www-data /var/www/xmmcg/frontend/

echo "🌐 步骤 5/5: 更新 Nginx 配置..."
cp /opt/xmmcg/backend/nginx.conf /etc/nginx/sites-available/xmmcg
nginx -t
systemctl reload nginx

echo ""
echo "=========================================="
echo "✅ 前端部署完成！"
echo "=========================================="
echo ""
echo "🌐 访问地址:"
echo "  - 网站: http://$(curl -s ifconfig.me)"
echo "  - 管理后台: http://$(curl -s ifconfig.me)/admin/"
echo ""
