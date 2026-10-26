# XMMCG Net

一个以完整谱面投稿为核心的比赛网站。Vue 3 + Element Plus 前端，Django REST API + Django Admin 后台；所有上传资源及 Django 管理后台静态文件存储于 Cloudflare R2。

## 比赛流程

- **谱面投稿**：登录后直接提交 `maidata.txt`、音频、封面及可选视频；自由选曲，没有竞标资格或分阶段创作要求。文件内容按原样保存并发送到 Net。
- **歌曲抽选（可选）**：创建并启用 `song_selection` 类型的比赛阶段。上传歌曲自动报名，也可直接报名。管理员执行一次抽选，每个实际用户分配一首歌；歌曲不足时均衡复用。结果不限制谱面选曲。没有启用该阶段时，入口与 API 同时关闭。
- **评分**：每谱目标评分数、满分及真爱票上限可在后台配置。均衡分配任务并排除本人及绑定账号参与创作的作品；同一实际用户对同一谱面只能评分一次。支持小数、评语、额外评分和 Excel 导出。
- **注册**：可选择已有大号，验证大号密码后创建绑定小号。小号使用大号联系方式，但独立登录、署名，不继承管理员权限。
- **首页**：保留 Banner、Markdown 公告、比赛时间轴和投稿统计。

## 开发

需要 Python 3.12+（建议 3.13）和 Node.js 22.12+。

```sh
python3.13 -m venv .venv
.venv/bin/python -m pip install -r backend/xmmcg/requirements.lock
cp .env.example .env
# 编辑 .env，填写 Django、数据库、R2 及 Net 配置。
.venv/bin/python backend/xmmcg/manage.py preflight_upgrade
.venv/bin/python backend/xmmcg/manage.py migrate
.venv/bin/python backend/xmmcg/manage.py createsuperuser
.venv/bin/python backend/xmmcg/manage.py configure_r2_cors       # 预览
.venv/bin/python backend/xmmcg/manage.py configure_r2_cors --apply
.venv/bin/python backend/xmmcg/manage.py collectstatic --noinput
.venv/bin/python backend/xmmcg/manage.py runserver
```

前端在 `front/` 中执行 `npm ci`、`npm run dev`。开发服务器将 `/api` 代理到 `127.0.0.1:8000`。生产默认同源；跨域部署可设置构建变量 `VITE_API_BASE_URL=https://api.example.com/api`。

## 云存储

配置 `R2_ACCOUNT_ID`（或 `R2_ENDPOINT_URL`）、`R2_ACCESS_KEY_ID`、`R2_SECRET_ACCESS_KEY`、`R2_BUCKET_NAME` 即可。凭证只存在后端环境中。

默认私有桶，API 返回临时签名读取地址；可通过 `R2_PUBLIC_DOMAIN` 使用公开自定义域名。上传由认证后端转存 R2，浏览器不持有写凭证。资源位于桶内 `media/`，Django 静态文件位于 `static/`；前端构建产物部署到静态站点托管服务。

R2 CORS 和 API CORS 分别配置，详见 [部署与 R2 配置](doc/DEPLOYMENT.md)。生产可以通过 `DATABASE_URL` 使用托管 PostgreSQL，使 API 实例不依赖持久本地磁盘；SQLite 仅作为开发选项。HTTP 上传缓冲可能使用临时空间，不存放持久资产。

## 验证

```sh
.venv/bin/python backend/xmmcg/manage.py test songs.tests --settings=xmmcg.test_settings
.venv/bin/python backend/xmmcg/manage.py makemigrations --check --dry-run --settings=xmmcg.test_settings
ruff check backend/xmmcg
cd front
npm run build
npm run format:check
```

测试使用独立内存数据库及没有本地路径的对象存储替身，Net 请求被模拟，不会向真实 Net 或 R2 上传文件。

## 结构与迁移

- `users/`：登录、注册及大小号身份。
- `songs/models.py`：谱面、阶段、歌曲抽选、评分及只读旧数据归档。
- `songs/chart_views.py`、`song_views.py`、`review_views.py`：各业务接口。
- `songs/phases.py`、`draws.py`、`reviews.py`：阶段权限和业务服务。
- `songs/majdata_service.py`：读取 R2 文件流并同步 Net。
- `xmmcg/storage.py`：R2 与桶 CORS 配置。

当前主线没有竞价、代币、两阶段创作或旧 API 兼容层。旧实现保存在 [`legacy`](https://github.com/SniperPigeon/xmmcg-net/tree/legacy) 分支。升级使用一次性数据迁移，参阅 [迁移说明](doc/MIGRATION.md)；不能直接使用历史仓库附带的开发数据库替代生产备份。
