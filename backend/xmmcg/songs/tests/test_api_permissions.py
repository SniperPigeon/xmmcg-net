from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.test import TestCase
from rest_framework.test import APIClient

from songs.models import PeerReviewAllocation, Song, SongDraw
from songs.draws import join_draw
from .test_contest import phase
from .test_peer_review_allocation import make_chart, make_user


class ManagementApiPermissionTests(TestCase):
    def setUp(self):
        self.author = make_user("permission-author")
        self.chart = make_chart(self.author)
        make_chart(make_user("permission-other"))
        self.staff = make_user("permission-staff")
        self.staff.is_staff = True
        self.staff.save()
        self.client = APIClient()
        self.client.force_login(self.staff)

    def grant(self, codename):
        self.staff.user_permissions.add(
            Permission.objects.get(content_type__app_label="songs", codename=codename)
        )

    def test_read_only_competition_staff_cannot_allocate_through_api(self):
        self.grant("view_competition")
        self.assertEqual(self.client.get("/api/reviews/export/").status_code, 200)
        response = self.client.post(
            "/api/reviews/allocate/", {"commit": True}, format="json"
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(PeerReviewAllocation.objects.exists())
        self.grant("change_competition")
        response = self.client.post(
            "/api/reviews/allocate/", {"commit": True}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(PeerReviewAllocation.objects.exists())

    def test_staff_without_competition_access_cannot_export_scores(self):
        self.assertEqual(self.client.get("/api/reviews/export/").status_code, 403)
        self.grant("change_competition")
        self.assertEqual(self.client.get("/api/reviews/export/").status_code, 200)

    def test_read_only_phase_staff_cannot_finalize_draw(self):
        stage = phase()
        Song.objects.create(
            competition=stage.competition,
            phase=stage,
            user=self.author,
            title="抽选歌曲",
            audio_file="test.mp3",
            audio_hash="test",
            file_size=4,
        )
        join_draw(self.author)
        self.grant("view_competitionphase")
        self.assertEqual(
            self.client.post(f"/api/songs/draw/{stage.pk}/").status_code, 403
        )
        self.assertIsNone(SongDraw.objects.get(phase=stage).completed_at)
        self.grant("change_competitionphase")
        self.assertEqual(
            self.client.post(f"/api/songs/draw/{stage.pk}/").status_code, 200
        )
        self.assertIsNotNone(SongDraw.objects.get(phase=stage).completed_at)

    def test_retry_requires_ownership_or_chart_change_permission(self):
        self.grant("view_chart")
        with patch("songs.chart_views.sync_chart") as sync:
            url = f"/api/charts/{self.chart.pk}/sync/"
            self.assertEqual(self.client.post(url).status_code, 403)
            sync.assert_not_called()
            self.grant("change_chart")
            self.assertEqual(self.client.post(url).status_code, 200)
            self.client.force_login(self.author)
            self.assertEqual(self.client.post(url).status_code, 200)
            self.assertEqual(sync.call_count, 2)
