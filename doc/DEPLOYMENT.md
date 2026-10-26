# 部署与 R2 配置

## 配置来源

优先使用进程环境变量。项目根 `.env` 可用于本地或单机部署。保留原有文件选择顺序：存在 `login_credentials.env` 时读取它，否则读取 `.env`。两份文件不自动合并，进程环境变量始终优先。示例见根目录 `.env.example`，不要将真实凭证提交到 Git。

后端 Python 3.12+，建议使用 3.13；前端构建支持 Node.js 22.12+。通过 `requirements.lock` 与 `package-lock.json` 固定已验证版本。

## R2

1. 创建专用于网站资源的桶，为后端生成仅访问该桶的 S3 凭证。
2. 填写 `R2_ACCOUNT_ID`、`R2_ACCESS_KEY_ID`、`R2_SECRET_ACCESS_KEY`、`R2_BUCKET_NAME`。区域为 `auto`；特殊区域可配置完整 `R2_ENDPOINT_URL`。
3. 默认使用私有桶和 `R2_URL_EXPIRY` 秒有效的读取地址（默认 3600 秒）。资源页面重新加载会获得新地址，签名到期后需刷新页面。
4. 若填写 `R2_PUBLIC_DOMAIN=assets.example.com`，需要在 Cloudflare 将该域名绑定到桶并启用公开访问。该模式的资源可公开读取，不再使用签名链接。
5. `collectstatic --noinput` 将 Django Admin 静态文件上传到 `static/`；业务素材写入 `media/`。无需 Nginx `/media` 或本地 `MEDIA_ROOT`。私有桶模式下，管理后台静态文件经 `/static/` 从 R2 读取并返回，确保 CSS 相对资源和 JavaScript 模块可以正常加载；该接口固定使用 `static/` 前缀，不能读取业务素材。

实际链路：浏览器 → 登录及 CSRF 验证后的 Django 投稿 API → R2 → Django 读取存储流 → Net。

Net 登录/上传地址、账号和哈希密码通过 `MAJDATA_*` 配置。投稿保留独立同步状态：失败可以重试；超时或无法确认响应会标记为 `unknown`，避免盲目重复上传。成功后的远端 URL 和响应被保存。`unknown` 或进程中断遗留的 `syncing` 状态由管理员先到 Net 核对，再运行 `resolve_net_sync` 标记已完成或允许重试。没有自动清除远端作品的操作。

## 两套 CORS

**网站 API**：`FRONTEND_ORIGINS` 填前端源，包含协议和端口；`CSRF_TRUSTED_ORIGINS` 配置允许提交表单的前端源。Session Cookie 登录开启 `credentials`，不允许通配源。生产 HTTPS 设置 `SESSION_COOKIE_SECURE=True` 和 `CSRF_COOKIE_SECURE=True`。前端与 API 不同站点时，两个 `*_SAMESITE` 均配置为 `None`，仍需 HTTPS 和浏览器允许第三方 Cookie；推荐同源代理。

**R2 桶**：`R2_CORS_ORIGINS` 填允许读取素材的网站源。当前浏览器只需要 GET/HEAD；文件经后端上传，无需开放浏览器 PUT/DELETE。

```sh
.venv/bin/python backend/xmmcg/manage.py configure_r2_cors
.venv/bin/python backend/xmmcg/manage.py configure_r2_cors --apply
```

第一条只输出 S3 格式 JSON；第二条读取并保留桶上原有 CORS 规则，再补充当前网站的读取规则；重复执行不会添加相同规则。若 S3 凭证不允许管理桶 CORS，可在 Cloudflare 控制台手动填写相同规则。浏览器可读响应头包含 ETag、Content-Length、Content-Range、Accept-Ranges。

自定义域名已有缓存时，修改 CORS 后需要刷新旧缓存；用 `Origin` 请求头验证。预签名链接仍然需要桶 CORS。参考 [Cloudflare CORS 文档](https://developers.cloudflare.com/r2/buckets/cors/) 与 [R2 boto3 接入](https://developers.cloudflare.com/r2/examples/aws/boto3/)。

## 部署顺序

1. 备份数据库和旧媒体；按 `MIGRATION.md` 演练一次迁移。
2. 安装锁定依赖，填写环境变量。生产设置 `DEBUG=False`、具体的 `ALLOWED_HOSTS` 和随机 `SECRET_KEY`。
3. 执行 `preflight_upgrade`、`migrate`。新安装不导入仓库旧 SQLite 文件。
4. 导入旧媒体（如有），配置桶 CORS，执行 `collectstatic --noinput`。
5. 保留原部署路径 `/opt/xmmcg`、生产虚拟环境 `venv/` 和 `backend/gunicorn.service`：4 个 worker、每个 2 个线程、120 秒超时、原有 socket 与日志目录。不要为本次重构替换数据库或 Web 托管架构。
6. 在 `front/` 中 `npm ci && npm run build`，将 `dist/` 按原部署方式放到 `/var/www/xmmcg/frontend/`，由 Nginx 提供 SPA 回退。默认同源 `/api/`、`/admin/`、`/static/` 转发至后端；或使用 `VITE_API_BASE_URL`。
7. 在后台配置比赛阶段、公告、比赛配置。歌曲阶段为可选；没有投稿/评分时间阶段时，使用比赛配置中的开放开关。

反向代理请求体上限必须覆盖音频、封面和视频总大小（保留原有 Nginx 50 MB 上限）；托管平台如有限制，应同步降低 `MAX_*_SIZE_MB`。数据库为元数据和 Session 的唯一状态来源，生产继续使用 SQLite，R2 保存上传资源。默认数据库为后端目录下的 `db.sqlite3`，可以通过 `SQLITE_PATH` 指定。保留 `scripts/backup_sqlite.sh` 以及原有 systemd 备份服务和定时器。SQLite 写事务使用 IMMEDIATE 模式与 30 秒锁等待；R2 文件上传在数据库写事务之外进行，避免网络请求占用写锁。

管理员入口：
- 比赛阶段：选择歌曲阶段执行一次抽选；抽选后该阶段不再接收歌曲或报名。
- 比赛配置：设置每谱评分数/满分/真爱票上限；保存后通过“预览 / 分配评分任务”补齐任务。
- 谱面：查看同步状态、重试明确失败的同步、导出选中谱面的评分。
- 公告/Banner：发布首页内容。

## 联调约束

联调必须在数据库副本上进行，并设置 `ENABLE_CHART_FORWARD_TO_MAJDATA=False`。R2 测试对象使用独立随机前缀，验证后清理；不要通过重试历史谱面验证 Net。本次联调还在代码层拦截了 Net 上传函数及所有非 R2 网络地址。

默认上传限制保留原值：音频 10 MB、封面 2 MB、视频 20 MB、谱面文本 1 MB，每位用户最多上传 3 首歌曲。环境变量可以覆盖这些值；谱面本身不再受指定歌曲或分阶段创作限制。

从零部署与增量更新分别使用 `deploy.sh`、`update.sh`；main push 通过检查后的 SSH 自动部署、服务器原有配置的处理方式详见 [CI/CD 文档](CI_CD.md)。
