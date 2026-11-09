from django.contrib.auth.models import Permission
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from songs.models import Chart
from .test_contest import upload_files
from .test_peer_review_allocation import make_competition, make_user


class ChartEditingTests(TestCase):
    def setUp(self):
        self.competition = make_competition()
        self.author = make_user("edit-author")
        self.staff = make_user("edit-staff")
        self.staff.is_staff = True
        self.staff.save()
        self.staff.user_permissions.add(Permission.objects.get(codename="change_chart"))
        api = APIClient()
        api.force_authenticate(self.author)
        self.assertEqual(
            api.post("/api/charts/", upload_files(), format="multipart").status_code,
            201,
        )
        self.chart = Chart.objects.get()
        self.url = f"/admin/songs/chart/{self.chart.pk}/change/"
        self.client.force_login(self.staff)

    def payload(self, **kwargs):
        return {
            "title": "新曲名",
            "designer": "新名义",
            "status": "submitted",
            **kwargs,
        }

    def test_edit_metadata_and_ignore_system_field_tampering(self):
        response = self.client.get(self.url)
        fields = response.context["adminform"].form.fields
        self.assertEqual(
            set(fields),
            {
                "title",
                "designer",
                "status",
                "chart_file",
                "audio_file",
                "cover_image",
                "background_video",
            },
        )
        original = (
            self.chart.guid,
            self.chart.user_id,
            self.chart.competition_id,
            self.chart.chart_file.name,
        )
        response = self.client.post(
            self.url,
            self.payload(
                user=self.staff.pk,
                contributors=[self.staff.pk],
                net_sync_status="synced",
            ),
        )
        self.assertEqual(response.status_code, 302)
        self.chart.refresh_from_db()
        self.assertEqual((self.chart.title, self.chart.designer), ("新曲名", "新名义"))
        self.assertEqual(
            (
                self.chart.guid,
                self.chart.user_id,
                self.chart.competition_id,
                self.chart.chart_file.name,
            ),
            original,
        )
        self.assertEqual(list(self.chart.contributors.all()), [self.author])
        self.assertEqual(self.chart.net_sync_status, "disabled")

    def test_replace_assets_and_flag_remote_copy(self):
        old_key = self.chart.chart_file.name
        old_content = default_storage.open(old_key).read()
        Chart.objects.filter(pk=self.chart.pk).update(
            net_sync_status="synced", net_url="https://example.com/chart"
        )
        data = upload_files()
        data.pop("submission_key")
        response = self.client.post(self.url, {**data, "status": "submitted"})
        self.assertEqual(response.status_code, 302)
        self.chart.refresh_from_db()
        self.assertNotEqual(old_key, self.chart.chart_file.name)
        self.assertEqual(default_storage.open(old_key).read(), old_content)
        self.assertEqual(self.chart.net_sync_status, "unknown")
        self.assertEqual(self.chart.net_url, "https://example.com/chart")
        self.assertIn("后台已修改素材", self.chart.net_sync_error)

    def test_invalid_names_and_chart_rejected_without_writing(self):
        before = set(default_storage.objects)
        for overrides in (
            {"title": "  "},
            {"designer": "  "},
            {"chart_file": SimpleUploadedFile("bad.exe", b"bad")},
            {"chart_file": SimpleUploadedFile("bad.txt", b"\xff")},
        ):
            response = self.client.post(self.url, self.payload(**overrides))
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["adminform"].form.errors)
        self.assertEqual(set(default_storage.objects), before)
        self.chart.refresh_from_db()
        self.assertEqual(self.chart.title, "任意曲名")

    def test_archive_and_view_only_permission_reject_changes(self):
        self.staff.user_permissions.clear()
        self.staff.user_permissions.add(Permission.objects.get(codename="view_chart"))
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(self.client.post(self.url, self.payload()).status_code, 403)
        self.staff.user_permissions.add(Permission.objects.get(codename="change_chart"))
        self.competition.status = "archived"
        self.competition.save()
        self.assertEqual(self.client.post(self.url, self.payload()).status_code, 403)

    def test_sync_in_progress_rejects_changes(self):
        Chart.objects.filter(pk=self.chart.pk).update(net_sync_status="syncing")
        response = self.client.post(self.url, self.payload())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "谱面正在同步到 Net")
        self.chart.refresh_from_db()
        self.assertEqual(self.chart.title, "任意曲名")
