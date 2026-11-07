from django.contrib.auth.models import Permission
from django.test import TestCase
from rest_framework.test import APIClient

from songs.models import Chart, CollaborationConsent, PeerReview, PeerReviewAllocation
from .test_contest import upload_files
from .test_peer_review_allocation import make_chart, make_competition, make_user


class ChartDeletionTests(TestCase):
    def setUp(self):
        self.competition = make_competition()
        self.author = make_user("delete-author")
        self.coauthor = make_user("delete-coauthor")
        self.admin = make_user("delete-admin")
        self.admin.is_staff = self.admin.is_superuser = True
        self.admin.save()
        self.client.force_login(self.admin)
        self.chart = make_chart(self.author, competition=self.competition)
        self.chart.contributors.add(self.author, self.coauthor)
        self.consent = CollaborationConsent.objects.create(
            competition=self.competition,
            author=self.coauthor,
            uploader=self.author,
            used_by=self.chart,
        )

        reviewer = make_user("delete-reviewer")
        allocation = PeerReviewAllocation.objects.create(
            chart=self.chart, reviewer=reviewer
        )
        PeerReview.objects.create(
            chart=self.chart, reviewer=reviewer, allocation=allocation, score=80
        )

    def delete(self, bulk=False):
        if bulk:
            return self.client.post(
                "/admin/songs/chart/",
                {
                    "action": "delete_selected",
                    "_selected_action": [self.chart.pk],
                    "post": "yes",
                },
            )
        return self.client.post(
            f"/admin/songs/chart/{self.chart.pk}/delete/", {"post": "yes"}
        )

    def assert_deleted_and_can_upload(self):
        self.assertFalse(Chart.objects.filter(pk=self.chart.pk).exists())
        self.assertFalse(
            CollaborationConsent.objects.filter(pk=self.consent.pk).exists()
        )
        self.assertFalse(PeerReview.objects.exists())
        self.assertFalse(PeerReviewAllocation.objects.exists())
        for user in (self.author, self.coauthor):
            api = APIClient()
            api.force_authenticate(user)
            status = api.get("/api/charts/submission-status/").data
            self.assertEqual(status["used"], 0)
            self.assertTrue(status["can_upload"])
            response = api.post("/api/charts/", upload_files(), format="multipart")
            self.assertEqual(response.status_code, 201, response.data)

    def test_single_delete_confirmation_and_reupload(self):
        confirmation = self.client.get(f"/admin/songs/chart/{self.chart.pk}/delete/")
        self.assertEqual(confirmation.status_code, 200)
        self.assertTrue(Chart.objects.filter(pk=self.chart.pk).exists())
        self.assertEqual(self.delete().status_code, 302)
        self.assert_deleted_and_can_upload()

    def test_bulk_delete_and_reupload(self):
        self.assertEqual(self.delete(bulk=True).status_code, 302)
        self.assert_deleted_and_can_upload()

    def test_archived_competition_cannot_be_deleted(self):
        self.competition.status = "archived"
        self.competition.save()
        self.assertEqual(self.delete().status_code, 403)
        self.delete(bulk=True)
        self.assertTrue(Chart.objects.filter(pk=self.chart.pk).exists())

    def test_change_permission_does_not_grant_delete(self):
        self.admin.is_superuser = False
        self.admin.save()
        self.admin.user_permissions.add(Permission.objects.get(codename="change_chart"))
        self.assertEqual(self.delete().status_code, 403)
        self.delete(bulk=True)
        self.assertTrue(Chart.objects.filter(pk=self.chart.pk).exists())
