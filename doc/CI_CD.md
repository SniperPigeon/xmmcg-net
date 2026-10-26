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

## 当前服务器首次切换到重构版前

通过 1Panel 只读核对的环境为 Debian 13、Python 3.13.5、Node 20.20.2、Nginx 1.26.3。Node 20 实测可以构建当前产物，但部分依赖声明要求 Node 22；首次切换前请将主机构建环境准备为 Node 22.12+，增量流程会在停服前检查，并且不会擅自升级系统运行时。项目、venv、前端和服务 socket 均沿用已有目录。没有在这次检查中执行部署、重启服务或上传谱面。

现有仓库存在未提交的数据库、前端依赖和旧阶段脚本改动，且旧版把 db.sqlite3 纳入了 Git。**不能直接强制 checkout/reset**：新版已停止跟踪数据库，直接切换可能删除旧路径。首次切换前应停止写入，使用 SQLite 在线备份，保留服务器代码差异，按 MIGRATION.md 完成迁移准备并人工整理这些差异。新自动部署入口遇到该状态会提前退出。

当前 Nginx 的 HTTPS 段落由 Certbot 管理，仍使用旧 `/static/` 和 `/media/` 本地 alias。首次切换时把 backend/nginx.conf 的路由和缓存规则合并进现有 443 server 块，保留证书、TLS include 和 80→443 跳转；通过 `nginx -t` 后重载。后续自动更新不会覆写该文件。

现有 Gunicorn unit 未声明 RuntimeDirectory，检查时 `/run/gunicorn` 不存在。新版构建会安装只包含 RuntimeDirectory 的 systemd drop-in，并 daemon-reload，保留原有 4 workers、2 threads、120 秒超时及日志位置；socket 目录随服务启动自动创建。

首次切换不要直接运行服务器里旧版本的 update.sh；旧脚本仍然是 git pull 流程，没有新版的数据库保护。CI 会从已通过检查的提交发送新的 remote_deploy.sh，因此会提前识别并拒绝这种状态。

这些首次切换准备需要在启用生产自动部署前完成。增量脚本不会静默丢弃服务器改动，也不会把当前生产数据库替换为空库。
