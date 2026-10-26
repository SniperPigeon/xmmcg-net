"""用独立 SQLite 文件验证多连接写入，避免依赖不生效的行锁。"""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
from django.test import SimpleTestCase

from django.test import TransactionTestCase
from django.core.files.storage import default_storage
from unittest.mock import patch
from rest_framework.test import APIClient
from django.db import connection
from .test_peer_review_allocation import make_user, make_competition
from .test_contest import upload_files, phase


class SQLiteConcurrencyTests(SimpleTestCase):
    def test_simultaneous_favorites_respect_person_limit(self):
        script = r"""
import django
django.setup()
from django.core.management import call_command
call_command('migrate', verbosity=0)
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.db import connection, connections
from rest_framework.exceptions import ValidationError
from songs.models import Competition, PeerReview
from songs.reviews import submit_reviews
from songs.tests.test_peer_review_allocation import make_user, make_chart
assert connection.settings_dict['ENGINE'] == 'django.db.backends.sqlite3'
assert connection.settings_dict['OPTIONS']['transaction_mode'] == 'IMMEDIATE'
user = make_user('reviewer')
make_chart(user)
author = make_user('author')
charts = [make_chart(author), make_chart(author)]
config = Competition.current()
config.max_favorites = 1
config.save()
barrier = Barrier(2)
def submit(chart):
    barrier.wait(timeout=5)
    try:
        submit_reviews(user, [{'chart_id': chart.pk, 'score': 30, 'favorite': True}])
        return 'saved'
    except ValidationError:
        return 'limited'
    finally:
        connections.close_all()
with ThreadPoolExecutor(max_workers=2) as pool:
    results = list(pool.map(submit, charts))
assert sorted(results) == ['limited', 'saved'], results
assert PeerReview.objects.count() == 1
print('SQLite concurrency verified')
"""
        with tempfile.TemporaryDirectory(prefix="xmmcg-sqlite-test-") as folder:
            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=Path(__file__).resolve().parents[2],
                env={
                    **os.environ,
                    "DJANGO_SETTINGS_MODULE": "xmmcg.settings",
                    "SQLITE_PATH": str(Path(folder) / "test.sqlite3"),
                    "ENABLE_CHART_FORWARD_TO_MAJDATA": "False",
                },
                capture_output=True,
                text=True,
                timeout=60,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("SQLite concurrency verified", result.stdout)

    def test_concurrent_activation_keeps_one_current_competition(self):
        script = r"""
import django
django.setup()
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.core.management import call_command
from django.db import connections
from rest_framework.exceptions import ValidationError
from songs.competitions import activate_competition
from songs.models import Competition
call_command('migrate', verbosity=0)
ids = [Competition.objects.create(name=f'比赛{i}').pk for i in range(2)]
barrier = Barrier(2)
def activate(pk):
    barrier.wait(timeout=5)
    try:
        activate_competition(pk)
        return 'activated'
    except ValidationError:
        return 'rejected'
    finally:
        connections.close_all()
with ThreadPoolExecutor(max_workers=2) as pool:
    results = list(pool.map(activate, ids))
assert sorted(results) == ['activated', 'rejected'], results
assert Competition.objects.filter(status='active').count() == 1
assert Competition.objects.filter(status='draft').count() == 1
print('concurrent activation verified')
"""
        with tempfile.TemporaryDirectory(prefix="xmmcg-activation-test-") as folder:
            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=Path(__file__).resolve().parents[2],
                env={
                    **os.environ,
                    "DJANGO_SETTINGS_MODULE": "xmmcg.settings",
                    "SQLITE_PATH": str(Path(folder) / "test.sqlite3"),
                    "ENABLE_CHART_FORWARD_TO_MAJDATA": "False",
                },
                capture_output=True,
                text=True,
                timeout=60,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("concurrent activation verified", result.stdout)


class UploadTransactionTests(TransactionTestCase):
    def test_asset_writes_do_not_hold_sqlite_transaction(self):
        make_competition()
        user = make_user("upload-lock-test")
        client = APIClient()
        client.force_authenticate(user)
        original_save = default_storage._save

        def save_without_transaction(name, content):
            self.assertFalse(
                connection.in_atomic_block, "R2 上传不应占用 SQLite 写事务"
            )
            return original_save(name, content)

        with patch.object(
            default_storage, "_save", side_effect=save_without_transaction
        ):
            response = client.post("/api/charts/", upload_files(), format="multipart")
            self.assertEqual(response.status_code, 201)
            phase()
            files = upload_files()
            response = client.post(
                "/api/songs/",
                {"title": "歌曲", "audio_file": files["audio_file"]},
                format="multipart",
            )
            self.assertEqual(response.status_code, 201)
