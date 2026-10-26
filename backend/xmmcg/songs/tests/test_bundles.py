from io import BytesIO
from unittest.mock import patch
from zipfile import ZipFile

from django.contrib.auth.models import Permission
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image
from rest_framework.test import APIClient

from songs.competitions import archive_competition, activate_competition
from songs.models import Chart, Competition
from .test_contest import upload_files
from .test_peer_review_allocation import make_competition, make_user


class BundleTests(TestCase):
    def setUp(self):
        self.competition = make_competition()
        self.admin = make_user("download-admin")
        self.admin.is_staff = self.admin.is_superuser = True
        self.admin.save()
        self.api = APIClient()
        self.api.force_authenticate(self.admin)
        self.client.force_login(self.admin)
        patcher = patch(
            "songs.majdata_service.upload_chart",
            side_effect=AssertionError("测试不允许发送 Net"),
        )
        self.net_upload = patcher.start()
        self.addCleanup(patcher.stop)

    def upload(self, video=None):
        data = upload_files(title="相同标题/../中文")
        if video:
            data["background_video"] = SimpleUploadedFile(video, b"video-exact-bytes")
        expected = {}
        for name, filename in (
            ("chart_file", "maidata.txt"),
            ("audio_file", "track.mp3"),
            ("cover_image", "bg.png"),
            ("background_video", video),
        ):
            if name in data:
                expected[filename] = data[name].read()
                data[name].seek(0)
        response = self.api.post("/api/charts/", data, format="multipart")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["chart"]["net_sync_status"], "disabled")
        self.net_upload.assert_not_called()
        return Chart.objects.get(pk=response.data["chart"]["id"]), expected

    def download(self, chart_ids, client=None):
        return (client or self.client).post(
            "/admin/songs/chart/",
            {
                "action": "download_charts",
                "_selected_action": chart_ids,
            },
        )

    def test_batch_preserves_selected_archived_files_and_video_names(self):
        first, first_files = self.upload("pv.mp4")
        second, second_files = self.upload("bg.mp4")
        archive_competition(self.competition.pk)
        new = Competition.objects.create(name="新的比赛")
        activate_competition(new.pk)
        excluded, _ = self.upload()
        with patch.object(
            default_storage, "path", side_effect=AssertionError("不能依赖本地资产路径")
        ):
            response = self.download([first.pk, second.pk])
            self.assertEqual(response.status_code, 200)
            self.assertIn('filename="charts.zip"', response["Content-Disposition"])
            with ZipFile(BytesIO(b"".join(response.streaming_content))) as bundle:
                expected = {"谱面列表.txt"}
                for chart, files in ((first, first_files), (second, second_files)):
                    for filename, content in files.items():
                        original_name = {
                            "maidata.txt": "original.txt",
                            "track.mp3": "any.mp3",
                            "bg.png": "cover.png",
                        }.get(filename, filename)
                        name = f"{chart.guid}/{original_name}"
                        expected.add(name)
                        self.assertEqual(bundle.read(name), content)
                self.assertEqual(set(bundle.namelist()), expected)
                manifest = bundle.read("谱面列表.txt").decode("utf-8")
                self.assertIn(first.title, manifest)
                self.assertNotIn(f"{excluded.guid}：", manifest)
            response.close()
        self.net_upload.assert_not_called()
        first.refresh_from_db()
        self.assertEqual(first.net_sync_status, "disabled")

    def test_single_bundle_has_playable_root_layout_and_exact_bytes(self):
        chart, expected = self.upload("pv.mp4")
        response = self.api.get(f"/api/charts/{chart.pk}/bundle/")
        self.assertEqual(response.status_code, 200)
        with ZipFile(BytesIO(b"".join(response.streaming_content))) as bundle:
            self.assertEqual(set(bundle.namelist()), set(expected))
            for name, data in expected.items():
                self.assertEqual(bundle.read(name), data)
        response.close()
        self.net_upload.assert_not_called()

    def test_single_bundle_normalizes_player_names_but_batch_keeps_originals(self):
        cover = BytesIO()
        Image.new("RGB", (2, 2)).save(cover, format="JPEG")
        data = upload_files(
            cover_image=SimpleUploadedFile("封面.JPEG", cover.getvalue(), "image/jpeg"),
            background_video=SimpleUploadedFile("PV.MP4", b"video"),
        )
        data["chart_file"].name = "原稿.TXT"
        data["audio_file"].name = "原曲.MP3"
        expected = {}
        for field in ("chart_file", "audio_file", "cover_image", "background_video"):
            expected[data[field].name] = data[field].read()
            data[field].seek(0)
        response = self.api.post("/api/charts/", data, format="multipart")
        self.assertEqual(response.status_code, 201, response.data)
        chart = Chart.objects.get(pk=response.data["chart"]["id"])
        single = self.api.get(f"/api/charts/{chart.pk}/bundle/")
        with ZipFile(BytesIO(b"".join(single.streaming_content))) as bundle:
            names = {
                "原稿.TXT": "maidata.txt",
                "原曲.MP3": "track.mp3",
                "封面.JPEG": "bg.jpg",
                "PV.MP4": "pv.mp4",
            }
            self.assertEqual(set(bundle.namelist()), set(names.values()))
            for original, normalized in names.items():
                self.assertEqual(bundle.read(normalized), expected[original])
        single.close()
        batch = self.download([chart.pk])
        with ZipFile(BytesIO(b"".join(batch.streaming_content))) as bundle:
            self.assertEqual(
                set(bundle.namelist()),
                {"谱面列表.txt"} | {f"{chart.guid}/{name}" for name in expected},
            )
        batch.close()

    def test_webp_cover_uses_player_filename_without_reencoding(self):
        cover = BytesIO()
        Image.new("RGB", (2, 2)).save(cover, format="WEBP")
        data = upload_files(
            cover_image=SimpleUploadedFile("封面.webp", cover.getvalue(), "image/webp")
        )
        response = self.api.post("/api/charts/", data, format="multipart")
        self.assertEqual(response.status_code, 201, response.data)
        chart_id = response.data["chart"]["id"]
        response = self.api.get(f"/api/charts/{chart_id}/bundle/")
        with ZipFile(BytesIO(b"".join(response.streaming_content))) as bundle:
            self.assertEqual(bundle.read("bg.png"), cover.getvalue())
        response.close()

    def test_missing_resource_returns_error_instead_of_incomplete_zip(self):
        chart, _ = self.upload()
        original_open = default_storage._open

        def missing_audio(name, mode="rb"):
            if name == chart.audio_file.name:
                raise FileNotFoundError("missing test resource")
            return original_open(name, mode)

        with patch.object(default_storage, "_open", side_effect=missing_audio):
            single = self.api.get(f"/api/charts/{chart.pk}/bundle/")
            self.assertEqual(single.status_code, 503)
            self.assertIn(f"谱面 #{chart.pk} 的音频读取失败", str(single.data))
            batch = self.download([chart.pk])
            self.assertEqual(batch.status_code, 302)
            self.assertNotIn("Content-Disposition", batch)
            page = self.client.get(batch.url)
            self.assertContains(page, f"谱面 #{chart.pk} 的音频读取失败")

    def test_only_staff_with_chart_view_permission_can_batch_download(self):
        chart, _ = self.upload()
        user = make_user("download-viewer")
        viewer = APIClient()
        viewer.force_login(user)
        response = self.download([chart.pk], client=viewer)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)
        user.is_staff = True
        user.save()
        self.assertEqual(self.download([chart.pk], client=viewer).status_code, 403)
        user.user_permissions.add(Permission.objects.get(codename="view_chart"))
        response = self.download([chart.pk], client=viewer)
        self.assertEqual(response.status_code, 200)
        response.close()
