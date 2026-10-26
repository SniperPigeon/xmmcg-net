# 前端

Node.js 22.12+，Vue 3 + Vite + Element Plus。

```sh
npm ci
npm run dev
npm run build
npm run format:check
```

开发时 `/api/` 代理到 `127.0.0.1:8000`。生产默认同源 API，可用 `VITE_API_BASE_URL` 修改构建地址。不要在 `VITE_*` 变量中放入 R2 或 Net 凭证。

投稿、选歌、评分分别调用独立 API；页面权限由后端返回的 capabilities 决定，身份使用实际 Session 检查。资源 URL 由后端返回，前端不拼接本地 `/media/` 路径。
