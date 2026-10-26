from datetime import timedelta
from io import BytesIO
from unittest.mock import patch
from uuid import uuid4
from zipfile import ZipFile

from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from songs.models import Chart, CompetitionPhase, Song, SongDrawEntry
from songs.draws import join_draw, run_draw
from songs.majdata_service import sync_chart
from .test_peer_review_allocation import make_user, make_chart, make_competition


def upload_files(**overrides):
    cover = BytesIO()
    Image.new("RGB", (2, 2)).save(cover, format="PNG")
    data = {
        "submission_key": str(uuid4()),
        "chart_file": SimpleUploadedFile(
            "original.txt", "&title=任意曲名\n&des=任意名义\n&inote_5=1,2,3,E".encode()
        ),
        "audio_file": SimpleUploadedFile(
            "any.mp3", b"audio", content_type="audio/mpeg"
        ),
        "cover_image": SimpleUploadedFile(
            "cover.png", cover.getvalue(), content_type="image/png"
        ),
    }
    return {**data, **overrides}


def phase(kind="song_selection", offset=0, competition=None):
    now = timezone.now() + timedelta(days=offset)
    return CompetitionPhase.objects.create(
        competition=competition or make_competition(),
        name=kind,
        phase_key=str(uuid4()),
        kind=kind,
        start_time=now - timedelta(hours=1),
        end_time=now + timedelta(hours=1),
    )


class ChartTests(TestCase):
    def setUp(self):
        make_competition()
        self.user = make_user("author")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_upload_without_song_phase_or_draw_and_cloud_download(self):
        with patch.object(
            default_storage, "path", side_effect=AssertionError("local path used")
        ):
            response = self.client.post(
                "/api/charts/", upload_files(), format="multipart"
            )
            self.assertEqual(response.status_code, 201, response.data)
            chart = Chart.objects.get()
            self.assertEqual(chart.title, "任意曲名")
            self.assertEqual(chart.status, "submitted")
            self.assertIsNone(chart.source_song)
            self.assertFalse(Song.objects.exists())
            bundle = self.client.get(f"/api/charts/{chart.pk}/bundle/")
            with ZipFile(BytesIO(b"".join(bundle.streaming_content))) as archive:
                self.assertEqual(
                    archive.read("maidata.txt"),
                    "&title=任意曲名\n&des=任意名义\n&inote_5=1,2,3,E".encode(),
                )
                self.assertEqual(
                    set(archive.namelist()), {"maidata.txt", "track.mp3", "bg.png"}
                )

    def test_anonymous_upload_rejected(self):
        self.client.force_authenticate(None)
        self.assertEqual(
            self.client.post("/api/charts/", upload_files()).status_code, 403
        )

    def test_repeat_request_is_idempotent(self):
        data = upload_files()
        key = data["submission_key"]
        first = self.client.post("/api/charts/", data, format="multipart")
        again = self.client.post(
            "/api/charts/", {"submission_key": key}, format="multipart"
        )
        self.assertEqual(again.status_code, 200)
        self.assertEqual(first.data["chart"]["id"], again.data["chart"]["id"])
        self.assertEqual(Chart.objects.count(), 1)

    def test_submission_period_does_not_depend_on_song_period(self):
        phase("song_selection", offset=-1)
        self.assertEqual(
            self.client.post(
                "/api/charts/", upload_files(), format="multipart"
            ).status_code,
            201,
        )
        phase("submission", offset=-1)
        self.assertEqual(
            self.client.post(
                "/api/charts/", upload_files(), format="multipart"
            ).status_code,
            403,
        )

    @override_settings(ENABLE_CHART_FORWARD_TO_MAJDATA=True)
    def test_sync_status_success_and_no_resend(self):
        chart = make_chart(self.user)
        with patch(
            "songs.majdata_service.upload_chart",
            return_value={"url": "https://majdata.net/chart/123"},
        ) as upload:
            sync_chart(chart)
            self.assertEqual(chart.net_sync_status, "synced")
            sync_chart(chart)
            self.assertEqual(upload.call_count, 1)

    @override_settings(ENABLE_CHART_FORWARD_TO_MAJDATA=True)
    def test_uncertain_remote_result_preserves_submission(self):
        with patch("songs.majdata_service.upload_chart", side_effect=TimeoutError):
            response = self.client.post(
                "/api/charts/", upload_files(), format="multipart"
            )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["chart"]["net_sync_status"], "unknown")
        chart = Chart.objects.get()
        self.assertEqual(
            self.client.post(f"/api/charts/{chart.pk}/sync/").status_code, 400
        )
        self.assertTrue(chart.chart_file.storage.exists(chart.chart_file.name))


class DrawTests(TestCase):
    def setUp(self):
        make_competition()
        self.user = make_user("songauthor")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_no_phase_disables_both_upload_and_draw(self):
        self.assertEqual(self.client.get("/api/songs/").status_code, 403)
        self.assertEqual(
            self.client.post("/api/songs/", {"title": "test"}).status_code, 403
        )
        self.assertEqual(self.client.post("/api/songs/draw/join/").status_code, 400)

    def test_upload_joins_and_one_time_draw(self):
        stage = phase()
        self.assertEqual(
            self.client.post(
                "/api/songs/",
                {"title": "song", "audio_file": SimpleUploadedFile("a.mp3", b"audio")},
                format="multipart",
            ).status_code,
            201,
        )
        alias = make_user("alias", self.user)
        join_draw(alias)
        other = make_user("other")
        join_draw(other)
        result = run_draw(stage.pk)
        self.assertEqual(result.entries.count(), 2)
        allocated = list(result.entries.values_list("user_id", "song_id"))
        self.assertEqual(
            allocated,
            list(run_draw(stage.pk).entries.values_list("user_id", "song_id")),
        )
        self.assertEqual(
            self.client.post(
                "/api/songs/",
                {
                    "title": "late",
                    "audio_file": SimpleUploadedFile("late.mp3", b"audio"),
                },
                format="multipart",
            ).status_code,
            400,
        )
        self.assertEqual(Song.objects.count(), 1)

    def test_draw_requires_admin_and_closed_phase_rejects_signup(self):
        stage = phase(offset=-1)
        self.assertEqual(
            self.client.post(f"/api/songs/draw/{stage.pk}/").status_code, 403
        )
        self.assertEqual(self.client.post("/api/songs/draw/join/").status_code, 400)
        self.assertFalse(SongDrawEntry.objects.exists())


class UploadFailureTests(TestCase):
    def test_partial_object_write_is_cleaned_up(self):
        make_competition()
        user = make_user("upload-failure")
        client = APIClient()
        client.force_authenticate(user)
        storage = default_storage
        before = set(storage.objects)
        original_save = storage._save

        def fail_cover(name, content):
            if "/covers/" in name:
                raise OSError("simulated storage failure")
            return original_save(name, content)

        with patch.object(storage, "_save", side_effect=fail_cover):
            with self.assertRaises(OSError):
                client.post("/api/charts/", upload_files(), format="multipart")
        self.assertEqual(set(storage.objects), before)
        self.assertFalse(Chart.objects.exists())
