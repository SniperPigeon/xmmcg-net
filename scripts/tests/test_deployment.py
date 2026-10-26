"""使用临时 Git 仓库验证部署边界，不连接生产服务器。"""

import importlib.util
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class RemoteDeployTests(unittest.TestCase):
    def setUp(self):
        if not shutil.which("git") or not shutil.which("flock"):
            self.skipTest("需要 git 与 flock（CI/Linux 容器中执行）")
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.base = Path(self.folder.name)
        self.origin = self.base / "origin.git"
        self.repo = self.base / "server"
        self.run_cmd("git", "init", "--bare", str(self.origin))
        self.run_cmd("git", "init", "-b", "main", str(self.repo))
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Deployment Test")
        self.git("remote", "add", "origin", str(self.origin))
        (self.repo / "scripts").mkdir()
        (self.repo / "scripts/build.sh").write_text(
            '#!/bin/bash\nset -eu\nprintf "%s" "$1" > "$TEST_RESULT"\n'
        )
        self.git("add", ".")
        self.git("commit", "-m", "initial")
        self.git("push", "origin", "main")
        self.sha = self.git("rev-parse", "HEAD").stdout.strip()
        self.result = self.base / "built-sha"
        self.events = self.base / "events"
        commands = self.base / "bin"
        commands.mkdir()
        systemctl = commands / "systemctl"
        systemctl.write_text('#!/bin/bash\nprintf "%s\\n" "$*" >> "$TEST_EVENTS"\n')
        systemctl.chmod(0o755)
        for name in ("node", "npm", "curl", "nginx"):
            executable = commands / name
            executable.write_text(
                '#!/bin/bash\n[[ "${FAIL_NODE:-}" != 1 ]]\n'
                if name == "node"
                else "#!/bin/bash\nexit 0\n"
            )
            executable.chmod(0o755)
        (self.repo / "venv/bin").mkdir(parents=True)
        executable = self.repo / "venv/bin/python"
        executable.write_text("#!/bin/bash\nexit 0\n")
        executable.chmod(0o755)
        self.env = {
            **os.environ,
            "PATH": str(commands) + os.pathsep + os.environ["PATH"],
            "TEST_RESULT": str(self.result),
            "TEST_EVENTS": str(self.events),
        }

    def run_cmd(self, *args, **kwargs):
        return subprocess.run(
            args, check=True, capture_output=True, text=True, **kwargs
        )

    def git(self, *args):
        return self.run_cmd("git", "-C", str(self.repo), *args)

    def deploy(self, sha):
        return subprocess.run(
            ["bash", str(ROOT / "scripts/remote_deploy.sh"), str(self.repo), sha],
            env=self.env,
            text=True,
            capture_output=True,
            timeout=20,
        )

    def test_deploys_exact_tested_commit(self):
        result = self.deploy(self.sha)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.result.read_text(), self.sha)
        self.assertEqual(self.events.read_text().strip(), "stop gunicorn")

    def test_stale_workflow_does_not_stop_or_deploy_server(self):
        (self.repo / "new.txt").write_text("new")
        self.git("add", ".")
        self.git("commit", "-m", "new main")
        self.git("push", "origin", "main")
        result = self.deploy(self.sha)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("跳过过期部署", result.stdout)
        self.assertFalse(self.result.exists())
        self.assertFalse(self.events.exists())

    def test_dirty_server_checkout_is_preserved(self):
        file = self.repo / "scripts/build.sh"
        file.write_text(file.read_text() + "# server customization\n")
        result = self.deploy(self.sha)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("server customization", file.read_text())
        self.assertFalse(self.events.exists())

    def test_unsupported_runtime_does_not_stop_server(self):
        self.env["FAIL_NODE"] = "1"
        result = self.deploy(self.sha)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.events.exists())
        self.assertFalse(self.result.exists())

    def test_invalid_revision_never_executes_shell_input(self):
        result = self.deploy("main; touch injected")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.repo / "injected").exists())
        self.assertFalse(self.events.exists())

    def test_legacy_tracked_database_is_never_removed_by_checkout(self):
        database = self.repo / "backend/xmmcg/db.sqlite3"
        database.parent.mkdir(parents=True)
        with sqlite3.connect(database) as db:
            db.execute("create table records(value text)")
        self.git("add", ".")
        self.git("commit", "-m", "legacy database")
        self.git("push", "origin", "main")
        sha = self.git("rev-parse", "HEAD").stdout.strip()
        with sqlite3.connect(database) as db:
            db.execute("insert into records values ('生产数据')")
        before = database.read_bytes()
        result = self.deploy(sha)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(database.read_bytes(), before)
        self.assertFalse(self.events.exists())


class BackupTests(unittest.TestCase):
    def test_backup_contains_committed_wal_rows_without_modifying_source(self):
        spec = importlib.util.spec_from_file_location(
            "backup_database", ROOT / "scripts/backup_database.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.sqlite3"
            with sqlite3.connect(source) as db:
                db.execute("pragma journal_mode=wal")
                db.execute("create table records (value text)")
                db.execute("insert into records values ('中文保留')")
                db.commit()
                target = module.backup_sqlite(
                    source, Path(folder) / "backups", "a" * 40
                )
                with sqlite3.connect(target) as backup:
                    self.assertEqual(
                        backup.execute("select value from records").fetchone()[0],
                        "中文保留",
                    )
                self.assertEqual(
                    db.execute("select count(*) from records").fetchone()[0], 1
                )
                self.assertEqual(target.stat().st_mode & 0o777, 0o600)


@unittest.skipUnless(os.geteuid() == 0, "仅在隔离容器/CI 的 root 测试环境运行")
class BuildTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.base = Path(self.folder.name)
        self.repo = self.base / "project"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        for key, value in [
            ("user.name", "Test"),
            ("user.email", "test@example.invalid"),
        ]:
            subprocess.run(
                ["git", "-C", str(self.repo), "config", key, value], check=True
            )
        (self.repo / "tracked").write_text("test")
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(self.repo), "commit", "-qm", "initial"], check=True
        )
        self.frontend = self.base / "published"
        (self.frontend / "assets").mkdir(parents=True)
        (self.frontend / "index.html").write_text("OLD INDEX")
        (self.frontend / "assets/old.js").write_text("old")
        dist = self.repo / "front/dist"
        (dist / "assets").mkdir(parents=True)
        (dist / "index.html").write_text("NEW INDEX")
        (dist / "assets/new.js").write_text("new")
        backend = self.repo / "backend/xmmcg"
        backend.mkdir(parents=True)
        self.database = backend / "db.sqlite3"
        self.database.write_text("test data only")
        (self.repo / ".env").write_text("TEST_ONLY=True")
        (self.repo / "venv/bin").mkdir(parents=True)
        commands = self.base / "bin"
        commands.mkdir()
        self.events = self.base / "events"
        self.env = {
            **os.environ,
            "PATH": str(commands) + os.pathsep + os.environ["PATH"],
            "XMMCG_PROJECT_DIR": str(self.repo),
            "XMMCG_FRONTEND_DIR": str(self.frontend),
            "XMMCG_BACKUP_DIR": str(self.base / "backups"),
            "TEST_DATABASE": str(self.database),
            "TEST_EVENTS": str(self.events),
        }

        def command(path, source):
            path.write_text("#!/bin/bash\nset -eu\n" + source)
            path.chmod(0o755)

        command(commands / "node", "exit 0\n")
        command(
            commands / "curl",
            'echo curl >> "$TEST_EVENTS"\n[[ "${FAIL_HEALTH:-}" != 1 ]]\n',
        )
        command(commands / "nginx", 'echo nginx >> "$TEST_EVENTS"\n')
        command(
            commands / "npm",
            'echo "npm $*" >> "$TEST_EVENTS"\n[[ "${FAIL_NPM:-}" != 1 ]]\n',
        )
        command(commands / "systemctl", 'echo "systemctl $*" >> "$TEST_EVENTS"\n')
        command(
            commands / "install",
            """
for arg in "$@"; do
  if [[ "$arg" = /etc/systemd/* ]]; then exit 0; fi
done
exec /usr/bin/install "$@"
""",
        )
        command(
            self.repo / "venv/bin/python",
            """
echo "python $*" >> "$TEST_EVENTS"
if [[ "$1" = -c && "$2" = *settings.DATABASES* ]]; then echo "$TEST_DATABASE"; fi
if [[ "$1" = manage.py && "$2" = migrate && "${FAIL_MIGRATE:-}" = 1 ]]; then exit 1; fi
""",
        )

    def run_build(self, **env):
        return subprocess.run(
            ["bash", str(ROOT / "scripts/build.sh")],
            env={**self.env, **env},
            capture_output=True,
            text=True,
            timeout=20,
        )

    def test_failed_frontend_build_does_not_publish(self):
        result = self.run_build(FAIL_NPM="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.frontend / "index.html").read_text(), "OLD INDEX")
        self.assertNotIn("systemctl restart", self.events.read_text())
        self.assertNotIn("manage.py migrate", self.events.read_text())

    def test_failed_migration_keeps_old_frontend_and_does_not_restart(self):
        result = self.run_build(FAIL_MIGRATE="1")
        self.assertNotEqual(result.returncode, 0)
        events = self.events.read_text()
        self.assertLess(
            events.index("scripts/backup_database.py"),
            events.index("manage.py migrate"),
        )
        self.assertNotIn("systemctl restart", events)
        self.assertEqual((self.frontend / "index.html").read_text(), "OLD INDEX")

    def test_failed_health_check_keeps_previous_entrypoint(self):
        result = self.run_build(FAIL_HEALTH="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.frontend / "index.html").read_text(), "OLD INDEX")

    def test_publish_keeps_old_hashed_assets(self):
        result = self.run_build()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.frontend / "index.html").read_text(), "NEW INDEX")
        self.assertTrue((self.frontend / "assets/old.js").exists())
        self.assertTrue((self.frontend / "assets/new.js").exists())
        self.assertIn("systemctl restart gunicorn", self.events.read_text())
