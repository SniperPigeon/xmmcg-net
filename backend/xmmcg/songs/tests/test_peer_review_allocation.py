from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework.exceptions import ValidationError
from songs.models import Chart, Competition, PeerReview, PeerReviewAllocation
from songs.reviews import allocate_reviews, submit_reviews
from users.models import UserProfile


def make_user(name, main=None):
    user = get_user_model().objects.create_user(
        username=name, password="long-password-902"
    )
    UserProfile.objects.create(user=user, main_account=main)
    return user


def make_competition():
    return Competition.current() or Competition.objects.create(
        name="测试比赛", status="active"
    )


def make_chart(user, title="chart", competition=None):
    chart = Chart.objects.create(
        competition=competition or make_competition(),
        user=user,
        title=title,
        designer=user.username,
    )
    chart.contributors.add(user)
    return chart


class ReviewTests(TestCase):
    def setUp(self):
        self.users = [make_user(f"user{i}") for i in range(4)]
        self.charts = [make_chart(user) for user in self.users]
        self.config = Competition.current()
        self.config.reviews_per_chart = 3
        self.config.save()

    def test_preview_does_not_write(self):
        result = allocate_reviews()
        self.assertEqual(result["new_tasks"], 12)
        self.assertFalse(PeerReviewAllocation.objects.exists())

    def test_balanced_no_self_and_idempotent(self):
        result = allocate_reviews(commit=True)
        self.assertEqual(result["shortfalls"], [])
        for chart in self.charts:
            self.assertEqual(chart.review_allocations.count(), 3)
            self.assertFalse(
                chart.review_allocations.filter(reviewer=chart.user).exists()
            )
        self.assertEqual(allocate_reviews(commit=True)["new_tasks"], 0)

    def test_aliases_are_one_person(self):
        alias = make_user("alias", self.users[0])
        own = make_chart(alias)
        allocate_reviews(commit=True)
        self.assertFalse(own.review_allocations.filter(reviewer=self.users[0]).exists())
        self.assertFalse(PeerReviewAllocation.objects.filter(reviewer=alias).exists())
        with self.assertRaises(ValidationError):
            submit_reviews(self.users[0], [{"chart_id": own.pk, "score": 40}])
        with self.assertRaises(ValidationError):
            submit_reviews(alias, [{"chart_id": self.charts[0].pk, "score": 40}])

    def test_shared_historical_authors_are_excluded(self):
        self.charts[0].contributors.add(self.users[1])
        allocate_reviews(commit=True)
        self.assertFalse(
            self.charts[0].review_allocations.filter(reviewer=self.users[1]).exists()
        )

    def test_decimal_and_comment_persist_and_survive_reallocation(self):
        allocate_reviews(commit=True)
        submit_reviews(
            self.users[0],
            [
                {
                    "chart_id": self.charts[1].pk,
                    "score": "42.75",
                    "comment": "好谱",
                    "favorite": True,
                }
            ],
        )
        review = PeerReview.objects.get()
        self.assertEqual(review.score, Decimal("42.75"))
        self.assertEqual(review.comment, "好谱")
        self.assertIsNotNone(review.allocation)
        allocate_reviews(commit=True)
        self.assertTrue(PeerReview.objects.filter(pk=review.pk).exists())
        review.allocation.delete()
        review.refresh_from_db()
        self.assertIsNone(review.allocation)

    def test_atomic_batch_rejects_self_review_without_partial_writes(self):
        with self.assertRaises(ValidationError):
            submit_reviews(
                self.users[0],
                [
                    {"chart_id": self.charts[1].pk, "score": 20},
                    {"chart_id": self.charts[0].pk, "score": 50},
                ],
            )
        self.assertFalse(PeerReview.objects.exists())

    def test_favorites_limit_counts_past_and_alias_reviews(self):
        self.config.max_favorites = 1
        self.config.save()
        submit_reviews(
            self.users[0],
            [{"chart_id": self.charts[1].pk, "score": 20, "favorite": True}],
        )
        alias = make_user("alias", self.users[0])
        with self.assertRaises(ValidationError):
            submit_reviews(
                alias, [{"chart_id": self.charts[2].pk, "score": 20, "favorite": True}]
            )

    def test_duplicate_system_and_extra_score_rejected(self):
        submit_reviews(self.users[0], [{"chart_id": self.charts[1].pk, "score": 20}])
        with self.assertRaises(ValidationError):
            submit_reviews(
                self.users[0], [{"chart_id": self.charts[1].pk, "score": 30}]
            )

    def test_insufficient_reviewers_reports_missing(self):
        self.config.reviews_per_chart = 8
        self.config.save()
        result = allocate_reviews(commit=True)
        self.assertEqual(len(result["shortfalls"]), 4)
        self.assertEqual(result["shortfalls"][0]["missing"], 5)

    def test_non_admin_cannot_allocate(self):
        client = APIClient()
        client.force_authenticate(self.users[0])
        self.assertEqual(
            client.post(
                "/api/reviews/allocate/", {"commit": True}, format="json"
            ).status_code,
            403,
        )

    def test_completed_tasks_remain_visible(self):
        allocate_reviews(commit=True)
        submit_reviews(self.users[0], [{"chart_id": self.charts[1].pk, "score": 20}])
        client = APIClient()
        client.force_authenticate(self.users[0])
        response = client.get("/api/reviews/tasks/")
        self.assertEqual(sum(item["completed"] for item in response.data["tasks"]), 1)

    def test_configured_score_limit_and_closed_review(self):
        self.config.max_score = 10
        self.config.save()
        with self.assertRaises(ValidationError):
            submit_reviews(
                self.users[0], [{"chart_id": self.charts[1].pk, "score": "10.25"}]
            )
        self.config.reviews_open = False
        self.config.save()
        client = APIClient()
        client.force_authenticate(self.users[0])
        self.assertEqual(
            client.post(
                "/api/reviews/submit/",
                {"reviews": [{"chart_id": self.charts[1].pk, "score": 5}]},
                format="json",
            ).status_code,
            403,
        )
