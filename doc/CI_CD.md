# CI/CD 与服务器部署

## 流程

每次 push 和 PR 都执行后端单元测试、迁移一致性检查、前端构建、部署脚本测试和 Nginx 路由检查。CI 使用 Node 22，满足全部锁定依赖的运行环境要求。

只有 main 的 push 且所有检查通过，才通过 SSH 执行服务器构建：

1. 获取 main 最新提交，确认仍是本轮通过 CI 的 SHA；过期任务直接跳过。
2. 获取服务器部署锁，拒绝覆盖未提交代码和仍由 Git 跟踪的旧数据库。
3. 暂停 Gunicorn，切换到该 SHA。
4. 安装锁定依赖、构建前端、检查数据库结构、备份 SQLite、执行迁移、收集 R2 静态资源。
5. 先发布资源文件，启动 Gunicorn 并通过 Unix socket 检查 API，再替换前端 index.html、重载 Nginx。

部署任务串行执行，不取消正在进行的部署。过程不运行 Net 上传，失败不会自动回滚数据库或强行恢复到不确定的状态；迁移后恢复旧版必须同时恢复备份和匹配的代码。

## GitHub 配置

在仓库 Settings → Secrets and variables → Actions 配置以下 Secrets，也可以放在 production 环境中：

| Secret | 内容 |
| --- | --- |
| DEPLOY_HOST | SSH 主机名或 IP，不是 1Panel 网页端口地址 |
| DEPLOY_USER | 部署用 SSH 用户；若不是 root，需要配置能够非交互执行部署脚本的 sudo 权限 |
| DEPLOY_SSH_KEY | 专用部署 SSH 私钥，保留完整多行格式；服务器配置对应公钥 |
| DEPLOY_KNOWN_HOSTS | 预先核对指纹的 SSH 主机公钥记录；非 22 端口使用 `[host]:port` 格式 |

可选 Variables：

| Variable | 默认值 |
| --- | --- |
| DEPLOY_PORT | 22 |
| DEPLOY_PATH | /opt/xmmcg |

服务器须能读取 origin 仓库，并已经配置 Python 虚拟环境、Node、Nginx、Gunicorn、SQLite 以及 R2 凭证。应用凭证留在服务器配置文件中，不通过 workflow 传输。SSH 严格校验主机公钥，不自动信任扫描结果。

自定义 DEPLOY_PATH 时使用无空格的绝对路径，并同步维护实际 Gunicorn WorkingDirectory/ExecStart。默认路径与当前生产服务器一致。

## 两个部署入口

### 从零部署：deploy.sh

适用于新 Debian/Ubuntu 服务器。保留宿主机 Nginx + Gunicorn + SQLite 架构；1Panel 可以管理和查看服务器，不要求用面板的 OpenResty 或容器运行应用。

```sh
sudo bash deploy.sh
```

脚本安装基础工具、克隆 main、创建 `/opt/xmmcg/venv`，首次生成带随机 SECRET_KEY 的 `.env` 后停止，等待填写 R2 和域名等真实配置。填好配置后重新执行即可继续。

默认使用 python3，要求 Python 3.12+；可通过 `sudo env XMMCG_PYTHON_BIN=/path/to/python3.13 bash deploy.sh` 指定。首次安装会检查 Node 版本；已有 Node 22.12+ 时复用，否则首次安装流程会安装 Node 22。

只在配置不存在时安装 Nginx/Gunicorn 模板。已有 Certbot HTTPS 配置和服务参数保持不变。首次站点上线仍需完成 DNS 和 HTTPS 配置，例如 `sudo certbot --nginx -d xmmcg.majdata.net`。

### 增量更新：update.sh

现有安装日常使用此入口，或由 workflow 调用相同的 remote_deploy.sh → build.sh 流程：

```sh
cd /opt/xmmcg
sudo bash update.sh <通过检查的完整提交SHA>
# 手动部署 main 最新版本时可以省略 SHA。
```

不会升级系统、重复安装 1Panel、覆盖 .env、覆盖 Nginx 的 TLS 配置或替换 SQLite。迁移前备份位于 `/var/back/xmmcg/before_deploy_时间_SHA.sqlite3`；原每日备份脚本与保留策略继续存在。

`deploy_frontend.sh` 仅构建和发布当前检出版本的前端，不修改数据库或 Gunicorn。`scripts/build.sh` 是两条路径共用的服务器构建实现，不自行拉取 Git。

## 首次切换状态（2026-10-26 发布前复核）

服务器仍运行旧版应用，main 为 `80da1ac`。Node 已准备为 22.23.4，npm 为 10.9.9；Gunicorn 与 Nginx 均为 active，HTTPS 管理后台返回 200。项目、venv、前端和服务 socket 沿用已有目录，Gunicorn 的 RuntimeDirectory drop-in 已就绪。

旧服务器代码差异已保存在本地备份分支，生产数据库已解除 Git 跟踪，受跟踪文件工作区干净。原始数据库、媒体和配置备份位于 `/var/back/xmmcg/pre-refactor-20261026T072228Z`。生产 SQLite 完整性检查通过，仍有 54 个用户、59 张谱面、83 首歌曲、261 条评分，尚未执行新版迁移；发布时 `build.sh` 会再次备份当时的数据库。不要用演练副本覆盖生产数据。

此前已在服务器独立副本上完成迁移、历史媒体导入和 R2 静态资源验证。Nginx 候选配置 `/etc/nginx/sites-available/xmmcg.refactor-ready` 已准备，保留 Certbot 的证书、TLS include 和 HTTP 跳转，尚未启用。**首次合并后的自动部署不会替换 Nginx 配置，CI 成功后还需要完成路由切换。**

首次发布顺序：

1. 确认 PR 最终提交全部检查通过，在安排好的发布窗口合并至 main；main 检查通过后由 SSH 部署任务执行代码切换、备份、迁移及构建。
2. 部署成功后，在服务器执行 `sudo bash /opt/xmmcg-preparation/activate-nginx.sh`。已准备的脚本会核对新版比赛表和 Nginx 模板摘要，备份原配置，执行 `nginx -t` 后重载，并验证 HTTPS API 与 R2 静态资源。如果模板摘要变化，应重新核对候选配置，不跳过检查。
3. 验证登录、历史比赛成绩导出和谱面下载；移除仍配置的旧阶段更新定时任务。按 [比赛管理与换届](COMPETITIONS.md) 新建并配置比赛，确认窗口后启用。历史数据迁入归档比赛，不会自动开放新一届。

生产进程的 `ENABLE_CHART_FORWARD_TO_MAJDATA` 当前为 False。正式恢复 Net 转发前需单独确认配置；升级和联调不通过重试历史谱面验证转发。

首次切换不要执行服务器中旧版本的 `update.sh`，它仍使用没有新版保护的 git pull 流程。CI 从已通过检查的提交发送新 `remote_deploy.sh`；增量部署不会丢弃服务器差异或将生产数据库替换为空库。迁移后回滚必须同时恢复数据库备份与匹配的旧代码。
