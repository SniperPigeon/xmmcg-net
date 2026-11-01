from unittest.mock import patch

from django.core.files.storage import default_storage
from django.test import TestCase
from rest_framework.test import APIClient

from songs.competitions import activate_competition, archive_competition
from songs.models import Chart, CollaborationConsent, Competition, PeerReviewAllocation
from songs.reviews import allocate_reviews
from songs.uploads import store_new_assets
from .test_contest import upload_files
from .test_peer_review_allocation import make_chart, make_user


class CollaborationTests(TestCase):
    def setUp(self):
        self.competition = Competition.objects.create(name="合作比赛", status="active")
        self.alice = make_user("collab-alice")
        self.bob = make_user("collab-bob")
        self.carol = make_user("collab-carol")

    def client_for(self, user):
        client = APIClient()
        client.force_authenticate(user)
        return client

    def grant(self, author, uploader):
        response = self.client_for(author).post(
            "/api/charts/collaboration-consents/",
            {"uploader_id": uploader.pk},
            format="json",
        )
        self.assertIn(response.status_code, (200, 201), response.data)
        return response.data["id"]

    def upload(self, user, authors=(), **kwargs):
        return self.client_for(user).post(
            "/api/charts/",
            upload_files(collaborator_ids=[author.pk for author in authors], **kwargs),
            format="multipart",
        )

    def quota(self, user):
        return self.client_for(user).get("/api/charts/submission-status/").data

    def test_defaults_one_per_account_and_consent_required(self):
        self.assertEqual(self.competition.max_chart_submissions, 1)
        self.assertEqual(self.competition.submission_quota_scope, "account")
        self.assertTrue(self.competition.allow_collaboration)
        self.assertTrue(self.competition.require_collaborator_approval)
        with patch("songs.chart_views.store_new_assets") as save:
            self.assertEqual(self.upload(self.alice, [self.bob]).status_code, 400)
        save.assert_not_called()
        self.assertFalse(Chart.objects.exists())

    def test_consent_is_targeted_revocable_and_idempotent(self):
        consent_id = self.grant(self.bob, self.alice)
        self.assertEqual(self.grant(self.bob, self.alice), consent_id)
        self.assertEqual(CollaborationConsent.objects.count(), 1)
        self.assertEqual(self.quota(self.bob)["used"], 0)
        choices = (
            self.client_for(self.alice).get("/api/charts/collaboration-accounts/").data
        )
        self.assertEqual(
            choices,
            [{"id": self.bob.pk, "username": self.bob.username, "available": True}],
        )
        self.assertEqual(self.upload(self.carol, [self.bob]).status_code, 400)
        url = f"/api/charts/collaboration-consents/{consent_id}/"
        self.assertEqual(self.client_for(self.alice).delete(url).status_code, 404)
        self.assertEqual(self.client_for(self.bob).delete(url).status_code, 204)
        self.assertEqual(self.upload(self.alice, [self.bob]).status_code, 400)
        self.assertEqual(
            self.client_for(self.alice).get("/api/charts/collaboration-accounts/").data,
            [],
        )

    def test_coauthors_each_use_one_slot_and_see_shared_submission(self):
        consent_id = self.grant(self.bob, self.alice)
        other_consent_id = self.grant(self.bob, self.carol)
        response = self.upload(self.alice, [self.bob])
        self.assertEqual(response.status_code, 201, response.data)
        chart = Chart.objects.get()
        self.assertEqual(
            set(chart.contributors.values_list("pk", flat=True)),
            {self.alice.pk, self.bob.pk},
        )
        self.assertEqual(chart.net_sync_status, "disabled")
        self.assertTrue(response.data["chart"]["is_collaboration"])
        for user in (self.alice, self.bob):
            self.assertEqual(
                (
                    self.quota(user)["used"],
                    self.quota(user)["remaining"],
                    self.quota(user)["can_upload"],
                ),
                (1, 0, False),
            )
            own = self.client_for(user).get("/api/charts/me/").data
            self.assertEqual(own["count"], 1)
            self.assertEqual(
                {row["id"] for row in own["results"][0]["contributors"]},
                {self.alice.pk, self.bob.pk},
            )
            self.assertEqual(
                self.client_for(user).get("/api/users/me/").data["chartsCount"], 1
            )
            self.assertEqual(self.upload(user).status_code, 400)
        self.assertEqual(self.upload(self.carol, [self.bob]).status_code, 400)
        self.assertIsNone(
            CollaborationConsent.objects.get(pk=other_consent_id).used_by_id
        )
        self.assertEqual(
            CollaborationConsent.objects.get(pk=consent_id).used_by_id, chart.pk
        )
        self.assertEqual(
            self.client_for(self.bob)
            .delete(f"/api/charts/collaboration-consents/{consent_id}/")
            .status_code,
            400,
        )
        self.assertFalse(
            self.client_for(self.bob)
            .get("/api/charts/me/")
            .data["results"][0]["can_retry_sync"]
        )
        self.assertEqual(
            self.client_for(self.bob).post(f"/api/charts/{chart.pk}/sync/").status_code,
            403,
        )
        anonymous = APIClient().get(f"/api/charts/{chart.pk}/").data
        self.assertTrue(anonymous["is_collaboration"])
        self.assertEqual(anonymous["contributors"], [])
        self.assertEqual(
            self.client_for(self.carol)
            .get(f"/api/charts/{chart.pk}/")
            .data["contributors"],
            [],
        )
        repeated = self.client_for(self.alice).post(
            "/api/charts/",
            {"submission_key": str(chart.submission_key)},
            format="multipart",
        )
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(repeated.data["chart"]["id"], chart.pk)
        self.assertEqual(
            APIClient().get("/api/contest/status/").data["participants"], 2
        )

    def test_accounts_have_independent_slots_but_review_identity_still_shared(self):
        alias = make_user("collab-bob-alt", self.bob)
        self.grant(self.bob, self.alice)
        self.assertEqual(self.upload(self.alice, [self.bob]).status_code, 201)
        joint = Chart.objects.get()
        self.assertEqual(self.upload(alias).status_code, 201)
        self.assertEqual(self.upload(self.carol).status_code, 201)
        self.assertEqual(self.quota(self.bob)["used"], 1)
        self.assertEqual(self.quota(alias)["used"], 1)
        allocate_reviews(commit=True)
        self.assertFalse(
            PeerReviewAllocation.objects.filter(
                chart=joint, reviewer__in=[self.alice, self.bob, alias]
            ).exists()
        )
        own = Chart.objects.get(user=alias)
        self.assertFalse(
            PeerReviewAllocation.objects.filter(chart=own, reviewer=self.bob).exists()
        )
        for user in (self.alice, self.bob, alias):
            response = self.client_for(user).post(
                "/api/reviews/submit/",
                {"reviews": [{"chart_id": joint.pk, "score": 40}]},
                format="json",
            )
            self.assertEqual(response.status_code, 400)
        self.assertEqual(
            APIClient().get("/api/contest/status/").data["participants"], 3
        )

    def test_identity_scope_deduplicates_one_chart_across_linked_authors(self):
        alias = make_user("collab-bob-alt", self.bob)
        self.competition.submission_quota_scope = "identity"
        self.competition.save()
        self.grant(self.bob, self.alice)
        self.grant(alias, self.alice)
        response = self.upload(self.alice, [self.bob, alias])
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self.quota(self.bob)["used"], 1)
        self.assertEqual(self.quota(alias)["used"], 1)
        self.assertEqual(self.upload(alias).status_code, 400)

    def test_configurable_limit_and_fresh_single_use_consent(self):
        self.competition.max_chart_submissions = 2
        self.competition.save()
        first = self.grant(self.bob, self.alice)
        self.assertEqual(self.upload(self.alice, [self.bob]).status_code, 201)
        self.assertEqual(self.upload(self.alice, [self.bob]).status_code, 400)
        second = self.grant(self.bob, self.alice)
        self.assertNotEqual(first, second)
        self.assertEqual(self.upload(self.alice, [self.bob]).status_code, 201)
        self.assertEqual(self.upload(self.alice).status_code, 400)
        self.competition.max_chart_submissions = 0
        self.competition.save()
        self.assertIsNone(self.quota(self.alice)["remaining"])
        self.assertEqual(self.upload(self.alice).status_code, 201)

    def test_disabling_collaboration_and_optional_approval(self):
        self.competition.allow_collaboration = False
        self.competition.save()
        self.assertEqual(
            self.client_for(self.bob)
            .post(
                "/api/charts/collaboration-consents/",
                {"uploader_id": self.alice.pk},
                format="json",
            )
            .status_code,
            403,
        )
        self.assertEqual(self.upload(self.alice, [self.bob]).status_code, 400)
        self.competition.allow_collaboration = True
        self.competition.require_collaborator_approval = False
        self.competition.save()
        self.assertEqual(self.upload(self.alice, [self.bob]).status_code, 201)
        self.assertFalse(CollaborationConsent.objects.exists())

    def test_invalid_coauthors_rejected_before_object_storage(self):
        consent = self.grant(self.bob, self.alice)
        with patch("songs.chart_views.store_new_assets") as save:
            self.assertEqual(self.upload(self.alice, [self.alice]).status_code, 400)
            self.assertEqual(
                self.upload(self.alice, [self.bob, self.bob]).status_code, 400
            )
            self.bob.is_active = False
            self.bob.save()
            self.assertEqual(self.upload(self.alice, [self.bob]).status_code, 400)
        save.assert_not_called()
        self.assertIsNone(CollaborationConsent.objects.get(pk=consent).used_by_id)

    def test_revoke_during_storage_write_cleans_up_without_consuming_slots(self):
        consent_id = self.grant(self.bob, self.alice)
        before = set(default_storage.objects)

        def store_then_revoke(chart):
            store_new_assets(chart)
            CollaborationConsent.objects.get(pk=consent_id).delete()

        with patch("songs.chart_views.store_new_assets", side_effect=store_then_revoke):
            response = self.upload(self.alice, [self.bob])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(default_storage.objects), before)
        self.assertFalse(Chart.objects.exists())
        self.assertEqual(self.quota(self.alice)["used"], 0)
        self.assertEqual(self.quota(self.bob)["used"], 0)

    def test_archive_does_not_free_slots_in_same_edition_and_next_edition_resets(self):
        self.grant(self.bob, self.alice)
        self.assertEqual(self.upload(self.alice, [self.bob]).status_code, 201)
        Chart.objects.update(status="archived")
        self.assertEqual(self.upload(self.bob).status_code, 400)
        archive_competition(self.competition.pk)
        new = Competition.objects.create(name="下一届合作比赛")
        activate_competition(new.pk)
        self.assertEqual(self.quota(self.bob)["used"], 0)
        self.assertEqual(
            self.client_for(self.bob).get("/api/charts/collaboration-consents/").data,
            [],
        )
        self.assertEqual(self.upload(self.alice, [self.bob]).status_code, 400)
        self.grant(self.bob, self.alice)
        self.assertEqual(self.upload(self.alice, [self.bob]).status_code, 201)

    def test_legacy_contributors_already_consume_quota(self):
        chart = make_chart(self.alice, competition=self.competition)
        chart.contributors.add(self.bob)
        self.assertEqual(self.quota(self.bob)["used"], 1)
        self.assertEqual(self.upload(self.bob).status_code, 400)
