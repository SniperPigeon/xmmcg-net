from django.contrib import admin
from django.contrib.auth.models import Permission
from django.test import TestCase, RequestFactory

from songs.models import (
    CollaborationConsent,
    PeerReview,
    PeerReviewAllocation,
    Song,
    SongDraw,
    SongDrawEntry,
    LegacyRecord,
)
from .test_peer_review_allocation import make_user, make_competition, make_chart


class AdminEditPermissionTests(TestCase):
    def test_existing_records_require_model_change_permission(self):
        user = make_user("edit-permissions")
        user.is_staff = True
        user.save()
        request = RequestFactory().get("/admin/")
        for model in (
            CollaborationConsent,
            PeerReview,
            PeerReviewAllocation,
            Song,
            SongDraw,
            SongDrawEntry,
            LegacyRecord,
        ):
            with self.subTest(model=model):
                user.user_permissions.clear()
                request.user = type(user).objects.get(pk=user.pk)
                model_admin = admin.site._registry[model]
                self.assertFalse(model_admin.has_change_permission(request))
                user.user_permissions.add(
                    Permission.objects.get(
                        content_type__app_label=model._meta.app_label,
                        codename="change_" + model._meta.model_name,
                    )
                )
                request.user = type(user).objects.get(pk=user.pk)
                self.assertTrue(model_admin.has_change_permission(request))

    def test_edit_collaboration_authorization(self):
        competition = make_competition()
        author, uploader, replacement = [
            make_user(n)
            for n in ("consent-author", "consent-uploader", "consent-replacement")
        ]
        staff = make_user("consent-admin")
        staff.is_staff = True
        staff.save()
        staff.user_permissions.add(
            Permission.objects.get(codename="change_collaborationconsent")
        )
        consent = CollaborationConsent.objects.create(
            competition=competition, author=author, uploader=uploader
        )
        chart = make_chart(replacement, competition=competition)
        self.client.force_login(staff)
        url = f"/admin/songs/collaborationconsent/{consent.pk}/change/"
        response = self.client.post(
            url,
            {
                "competition": competition.pk,
                "author": author.pk,
                "uploader": replacement.pk,
                "used_by": chart.pk,
            },
        )
        self.assertEqual(response.status_code, 302)
        consent.refresh_from_db()
        self.assertEqual(consent.uploader_id, replacement.pk)
        self.assertEqual(consent.used_by_id, chart.pk)
        response = self.client.post(
            url,
            {
                "competition": competition.pk,
                "author": author.pk,
                "uploader": author.pk,
                "used_by": chart.pk,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["adminform"].form.errors)
        consent.refresh_from_db()
        self.assertEqual(consent.uploader_id, replacement.pk)
