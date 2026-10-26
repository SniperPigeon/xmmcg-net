# 后端

Django 项目入口：`manage.py`。配置、部署、R2 和历史数据迁移参阅仓库根 [README](../../README.md) 及 [部署文档](../../doc/DEPLOYMENT.md)。

API 按 `/api/users/`、`/api/contest/`、`/api/charts/`、`/api/songs/`、`/api/reviews/` 划分。歌曲 API 仅在歌曲阶段启用；评分分配、导出仅管理员可调用。登录使用 Django Session + CSRF，没有竞标代币或 Bearer 登录令牌。
