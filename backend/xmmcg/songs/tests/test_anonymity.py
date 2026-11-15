from django.test import TestCase
from rest_framework.test import APIClient

from songs.models import PeerReview, PeerReviewAllocation
from .test_contest import upload_files
from .test_peer_review_allocation import make_chart, make_user


class ChartAnonymityTests(TestCase):
    def setUp(self):
        self.author = make_user("private-uploader")
        self.collaborator = make_user("private-collaborator")
        self.reviewer = make_user("reviewer")
        self.staff = make_user("staff")
        self.staff.is_staff = self.staff.is_superuser = True
        self.staff.save()
        self.chart = make_chart(self.author, "Public song title")
        self.chart.designer = "Private designer alias"
        self.chart.save()
        self.chart.contributors.add(self.collaborator)
        self.client = APIClient()

    def assert_anonymous(self, row):
        self.assertTrue(row["title"])
        for field in (
            "designer", "contributors", "is_collaboration", "user", "user_id"
        ):
            self.assertNotIn(field, row)
        for name in (
            self.author.username, self.collaborator.username, self.chart.designer
        ):
            self.assertNotIn(name, str(row))

    def test_chart_lists_and_details_never_return_author_metadata(self):
        for user in (
            None, self.author, self.collaborator, self.reviewer, self.staff
        ):
            with self.subTest(user=user):
                self.client.force_authenticate(user)
                for url in ("/api/charts/", f"/api/charts/{self.chart.pk}/"):
                    response = self.client.get(url)
                    self.assertEqual(response.status_code, 200)
                    rows = response.data.get("results", [response.data])
                    self.assertEqual(len(rows), 1)
                    self.assert_anonymous(rows[0])
        for user in (self.author, self.collaborator):
            self.client.force_authenticate(user)
            response = self.client.get("/api/charts/me/")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["count"], 1)
            self.assert_anonymous(response.data["results"][0])

    def test_upload_repeat_and_sync_responses_are_anonymous(self):
        self.client.force_authenticate(self.author)
        response = self.client.post(
            "/api/charts/", upload_files(designer=self.chart.designer), format="multipart"
        )
        self.assertEqual(response.status_code, 201)
        self.assert_anonymous(response.data["chart"])
        chart = self.author.charts.get(pk=response.data["chart"]["id"])
        self.assertEqual(chart.designer, self.chart.designer)
        response = self.client.post(
            "/api/charts/", {"submission_key": str(chart.submission_key)}, format="multipart"
        )
        self.assertEqual(response.status_code, 200)
        self.assert_anonymous(response.data["chart"])
        response = self.client.post(f"/api/charts/{chart.pk}/sync/")
        self.assertEqual(response.status_code, 200)
        self.assert_anonymous(response.data)

    def test_review_tasks_and_extra_choices_are_anonymous(self):
        self.client.force_authenticate(self.reviewer)
        response = self.client.get("/api/reviews/available/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assert_anonymous(response.data[0])
        PeerReviewAllocation.objects.create(chart=self.chart, reviewer=self.reviewer)
        response = self.client.get("/api/reviews/tasks/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["tasks"]), 1)
        self.assert_anonymous(response.data["tasks"][0])
        extra = make_chart(self.author, "Extra song")
        PeerReview.objects.create(chart=extra, reviewer=self.reviewer, score="42.5")
        response = self.client.get("/api/reviews/tasks/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["tasks"]), 2)
        for row in response.data["tasks"]:
            self.assert_anonymous(row)
