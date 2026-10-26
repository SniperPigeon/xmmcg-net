from io import BytesIO
from pathlib import PurePosixPath
from unittest.mock import patch
from uuid import UUID
from zipfile import ZipFile

from django.core.exceptions import SuspiciousFileOperation
from django.core.files.storage import default_storage
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from songs.models import Chart
from songs.uploads import store_new_assets
from xmmcg.storage import R2Storage
from .test_contest import upload_files
from .test_peer_review_allocation import make_competition, make_user


class OriginalNameTests(SimpleTestCase):
    def test_r2_preserves_valid_original_names_and_rejects_traversal(self):
        storage = R2Storage(
            access_key="test",
            secret_key="test",
            bucket_name="test",
            endpoint_url="https://example.r2.cloudflarestorage.com",
        )
        name = "charts/example/中文 曲名 [最终版] + #1.mp3"
        self.assertEqual(storage.generate_filename(name), name)
        with self.assertRaises(SuspiciousFileOperation):
            storage.generate_filename("charts/example/../outside.txt")


class GuidAssetsTests(TestCase):
    def setUp(self):
        make_competition()
        self.user = make_user("guid-author")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_one_guid_folder_preserves_original_names_and_batch_zip(self):
        data = upload_files()
        originals = {
            "chart_file": "完整谱面" * 28 + " [终稿].txt",
            "audio_file": "原曲 [demo] + #1.mp3",
            "cover_image": "封面 图像.png",
        }
        contents = {}
        for field, name in originals.items():
            data[field].name = name
            contents[name] = data[field].read()
            data[field].seek(0)
        response = self.client.post("/api/charts/", data, format="multipart")
        self.assertEqual(response.status_code, 201, response.data)
        chart = Chart.objects.get()
        self.assertEqual(UUID(response.data["chart"]["guid"]), chart.guid)
        self.assertNotEqual(chart.guid, chart.submission_key)
        for field, name in originals.items():
            asset = getattr(chart, field)
            self.assertEqual(asset.name, f"charts/{chart.guid}/{name}")
            with asset.open("rb") as stream:
                self.assertEqual(stream.read(), contents[name])
        self.user.is_staff = self.user.is_superuser = True
        self.user.save()
        self.client.force_login(self.user)
        batch = self.client.post(
            "/admin/songs/chart/",
            {"action": "download_charts", "_selected_action": [chart.pk]},
        )
        self.assertEqual(batch.status_code, 200)
        with ZipFile(BytesIO(b"".join(batch.streaming_content))) as archive:
            self.assertEqual(
                set(archive.namelist()),
                {"谱面列表.txt"}
                | {f"{chart.guid}/{name}" for name in originals.values()},
            )
            for name, content in contents.items():
                self.assertEqual(archive.read(f"{chart.guid}/{name}"), content)
        batch.close()

    def test_interleaved_duplicate_request_never_overwrites_or_deletes_winner(self):
        before = set(default_storage.objects)
        first_data = upload_files()
        second_data = upload_files(submission_key=first_data["submission_key"])
        nested = []
        entered = False

        def interleaved_store(chart):
            nonlocal entered
            store_new_assets(chart)
            if not entered:
                entered = True
                nested.append(
                    self.client.post("/api/charts/", second_data, format="multipart")
                )

        with patch("songs.chart_views.store_new_assets", side_effect=interleaved_store):
            first = self.client.post("/api/charts/", first_data, format="multipart")
        self.assertEqual(first.status_code, 400)
        self.assertEqual(nested[0].status_code, 201)
        chart = Chart.objects.get()
        saved = {
            getattr(chart, name).name
            for name in ("chart_file", "audio_file", "cover_image")
        }
        self.assertEqual(set(default_storage.objects) - before, saved)
        self.assertEqual(
            {str(PurePosixPath(name).parent) for name in saved},
            {f"charts/{chart.guid}"},
        )
        for name in saved:
            self.assertTrue(default_storage.exists(name))
        with chart.audio_file.open("rb") as audio:
            self.assertEqual(audio.read(), b"audio")
