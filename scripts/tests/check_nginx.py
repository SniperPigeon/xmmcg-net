"""在随机本地端口验证 Nginx 模板；配置和资源均放在临时目录。"""

import http.client
from http.server import BaseHTTPRequestHandler
import json
from pathlib import Path
import shutil
import socket
from socketserver import UnixStreamServer
import subprocess
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[2]


class Backend(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps(
            {"path": self.path, "scheme": self.headers.get("X-Forwarded-Proto")}
        ).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def main():
    nginx = shutil.which("nginx")
    if not nginx:
        raise SystemExit("需要 nginx；在 CI 或隔离 Linux 容器中执行此检查")
    with tempfile.TemporaryDirectory(prefix="xmmcg-nginx-") as folder:
        base = Path(folder)
        base.chmod(0o755)
        frontend = base / "frontend"
        (frontend / "assets").mkdir(parents=True)
        (frontend / "res").mkdir()
        (frontend / "index.html").write_text("<h1>小妹妹唱歌net</h1>")
        (frontend / "assets/app-hash.js").write_text('console.log("test")')
        backend = UnixStreamServer(str(base / "backend.sock"), Backend)
        (base / "backend.sock").chmod(0o777)
        threading.Thread(target=backend.serve_forever, daemon=True).start()
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        config = (ROOT / "backend/nginx.conf").read_text()
        config = config.replace("listen 80;", f"listen 127.0.0.1:{port};")
        config = config.replace("/var/www/xmmcg/frontend", str(frontend))
        config = config.replace("/run/gunicorn/xmmcg.sock", str(base / "backend.sock"))
        config = config.replace(
            "/var/log/nginx/xmmcg_access.log", str(base / "access.log")
        )
        config = config.replace(
            "/var/log/nginx/xmmcg_error.log", str(base / "error.log")
        )
        full = base / "nginx.conf"
        full.write_text(
            f"pid {base}/nginx.pid;\nerror_log {base}/startup.log;\nevents {{}}\nhttp {{\n{config}\n}}\n"
        )
        args = [nginx, "-p", str(base), "-c", str(full)]
        subprocess.run(args + ["-t"], check=True)
        process = subprocess.Popen(args + ["-g", "daemon off;"])
        try:

            def get(path, headers=None):
                client = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                client.request(
                    "GET",
                    path,
                    headers={"Host": "xmmcg.majdata.net", **(headers or {})},
                )
                response = client.getresponse()
                result = response.status, dict(response.getheaders()), response.read()
                client.close()
                return result

            for attempt in range(50):
                try:
                    get("/index.html")
                    break
                except OSError:
                    time.sleep(0.1)
            status, headers, body = get("/charts")
            assert status == 200 and "小妹妹唱歌net" in body.decode()
            assert "no-cache" in headers.get("Cache-Control", "")
            assert headers.get("X-Content-Type-Options") == "nosniff"
            for endpoint in ("admin", "api", "static"):
                status, headers, _ = get("/" + endpoint + "?test=1")
                assert status == 308 and headers["Location"].endswith(
                    "/" + endpoint + "/?test=1"
                )
            assert get("/assets/missing.js")[0] == 404
            assert get("/res/missing.png")[0] == 404
            assert "immutable" in get("/assets/app-hash.js")[1]["Cache-Control"]
            for path in (
                "/api/contest/status/",
                "/admin/login/",
                "/static/admin/css/base.css",
            ):
                status, _, body = get(path, {"X-Forwarded-Proto": "https"})
                assert status == 200 and json.loads(body) == {
                    "path": path,
                    "scheme": "http",
                }
            print("Nginx 配置、后端路由、SPA 回退和缓存检查通过")
        finally:
            process.terminate()
            process.wait(timeout=5)
            backend.shutdown()
            backend.server_close()


if __name__ == "__main__":
    main()
