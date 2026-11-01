"""通过认证接口和后台走完整赛程，再独立核对数据库与成绩文件。"""

from decimal import Decimal
from io import BytesIO
import re
from unittest.mock import patch

from django.test import TestCase
from openpyxl import load_workbook
from rest_framework.test import APIClient

from songs.models import (
    Chart,
    Competition,
    PeerReview,
    PeerReviewAllocation,
    Song,
    SongDraw,
)
from .test_contest import upload_files
from .test_peer_review_allocation import make_user


class CompleteCompetitionTests(TestCase):
    password = "long-password-902"

    def post(self, client, url, data=None, format="json"):
        token = client.get("/api/users/csrf/").data["csrfToken"]
        return client.post(url, data or {}, format=format, HTTP_X_CSRFTOKEN=token)

    def login(self, username):
        client = APIClient(enforce_csrf_checks=True)
        response = self.post(
            client,
            "/api/users/login/",
            {"username": username, "password": self.password},
        )
        self.assertEqual(response.status_code, 200, response.data)
        return client

    def config(self, admin, *, pk=None, upload=True, review=False):
        data = {
            "name": "完整赛程验证",
            "reviews_per_chart": 3,
            "max_score": "50",
            "max_favorites": 2,
            "allow_collaboration": "on",
            "require_collaborator_approval": "on",
            "max_chart_submissions": 1,
            "submission_quota_scope": "account",
            "_continue": "保存并继续编辑",
        }
        if upload:
            data["submissions_open"] = "on"
        if review:
            data["reviews_open"] = "on"
        url = (
            f"/admin/songs/competition/{pk}/change/"
            if pk
            else "/admin/songs/competition/add/"
        )
        response = self.post(admin, url, data, format="multipart")
        self.assertEqual(response.status_code, 302)
        return int(re.search(r"/competition/(\d+)/", response.url)[1])

    @patch(
        "songs.majdata_service.upload_chart",
        side_effect=AssertionError("禁止真实 Net 上传"),
    )
    def test_free_submission_to_archived_results_and_next_edition(self, net_upload):
        admin_user = make_user("flow-admin")
        admin_user.is_staff = admin_user.is_superuser = True
        admin_user.save()
        admin = self.login(admin_user.username)
        competition_id = self.config(admin)
        self.assertFalse(
            admin.get("/api/contest/status/").data["capabilities"]["chart_upload"]
        )
        self.assertEqual(
            self.post(
                admin,
                f"/admin/songs/competition/{competition_id}/activate/",
                format="multipart",
            ).status_code,
            302,
        )
        clients, users, roots, owners, charts = {}, {}, {}, {}, []
        names = ["flow-a", "flow-b", "flow-c", "flow-d", "flow-e", "flow-a1", "flow-a2"]
        for index, name in enumerate(names):
            client = APIClient(enforce_csrf_checks=True)
            payload = {
                "username": name,
                "password": self.password,
                "password_confirm": self.password,
            }
            if index >= 5:
                payload.update(
                    main_account_id=users[names[0]], main_password=self.password
                )
            else:
                payload.update(
                    email=f"{name}@example.invalid", qqid=str(8000000 + index)
                )
            response = self.post(client, "/api/users/register/", payload)
            self.assertEqual(response.status_code, 201, response.data)
            users[name] = response.data["user"]["id"]
            roots[name] = users[names[0]] if index >= 5 else users[name]
            clients[name] = self.login(name)
            files = upload_files()
            key = files["submission_key"]
            response = self.post(
                clients[name], "/api/charts/", files, format="multipart"
            )
            self.assertEqual(response.status_code, 201, response.data)
            chart = response.data["chart"]
            self.assertEqual(chart["net_sync_status"], "disabled")
            charts.append(chart["id"])
            owners[chart["id"]] = roots[name]
            again = self.post(clients[name], "/api/charts/", {"submission_key": key})
            self.assertEqual(again.data["chart"]["id"], chart["id"])
        status = admin.get("/api/contest/status/").data
        self.assertEqual((status["participants"], status["submissions"]), (5, 7))
        self.assertFalse(status["capabilities"]["songs_enabled"])
        self.assertEqual((Song.objects.count(), SongDraw.objects.count()), (0, 0))
        self.assertEqual(
            self.post(
                clients[names[0]],
                "/api/reviews/submit/",
                {"reviews": [{"chart_id": charts[1], "score": 20}]},
            ).status_code,
            403,
        )
        self.config(admin, pk=competition_id, upload=False, review=True)
        self.assertEqual(
            self.post(
                clients[names[0]], "/api/charts/", upload_files(), format="multipart"
            ).status_code,
            403,
        )
        preview = self.post(admin, "/api/reviews/allocate/", {"commit": False})
        self.assertEqual(preview.data["new_tasks"], 21)
        self.assertEqual(PeerReviewAllocation.objects.count(), 0)
        allocated = self.post(admin, "/api/reviews/allocate/", {"commit": True})
        self.assertEqual(allocated.data["new_tasks"], 21)
        self.assertEqual(allocated.data["shortfalls"], [])
        self.assertEqual(
            self.post(admin, "/api/reviews/allocate/", {"commit": True}).data[
                "new_tasks"
            ],
            0,
        )
        expected = {}
        for index, name in enumerate(names[:5]):
            tasks = clients[name].get("/api/reviews/tasks/").data["tasks"]
            self.assertTrue(tasks)
            self.assertTrue(
                all(owners[row["chart_id"]] != users[name] for row in tasks)
            )
            data = [
                {
                    "chart_id": row["chart_id"],
                    "score": "0"
                    if index == 0 and position == 0
                    else str(
                        Decimal(5 * (index + 1) + row["chart_id"] % 5) + Decimal("0.25")
                    ),
                    "comment": f"中文评语 {name}/{row['chart_id']}",
                    "favorite": position == 0,
                }
                for position, row in enumerate(tasks)
            ]
            if index == 0:
                alias_tasks = clients[names[5]].get("/api/reviews/tasks/").data["tasks"]
                self.assertEqual(
                    [row["chart_id"] for row in alias_tasks],
                    [row["chart_id"] for row in tasks],
                )
                invalid = self.post(
                    clients[name],
                    "/api/reviews/submit/",
                    {"reviews": [data[0], {"chart_id": charts[5], "score": 20}]},
                )
                self.assertEqual(invalid.status_code, 400)
                self.assertEqual(PeerReview.objects.count(), 0)
            sender = clients[names[5]] if index == 0 else clients[name]
            response = self.post(sender, "/api/reviews/submit/", {"reviews": data})
            self.assertEqual(response.status_code, 200, response.data)
            for row in data:
                expected[(users[name], row["chart_id"])] = {
                    **row,
                    "username": name,
                    "allocated": True,
                }
            self.assertEqual(
                self.post(
                    sender, "/api/reviews/submit/", {"reviews": [data[0]]}
                ).status_code,
                400,
            )
        self.assertEqual(
            clients[names[6]].get("/api/reviews/tasks/").data["favorites_used"], 1
        )
        for name in names[:5]:
            available = clients[name].get("/api/reviews/available/").data
            if available:
                extra = {
                    "chart_id": available[0]["id"],
                    "score": "47.50",
                    "comment": "额外评分评语",
                    "favorite": True,
                }
                self.assertNotEqual(owners[extra["chart_id"]], users[name])
                self.assertEqual(
                    self.post(
                        clients[name], "/api/reviews/submit/", {"reviews": [extra]}
                    ).status_code,
                    200,
                )
                expected[(users[name], extra["chart_id"])] = {
                    **extra,
                    "username": name,
                    "allocated": False,
                }
                break
        self.assertEqual(len(expected), 22)
        records = {
            (row.reviewer_id, row.chart_id): row for row in PeerReview.objects.all()
        }
        self.assertEqual(set(records), set(expected))
        for pair, row in expected.items():
            record = records[pair]
            self.assertEqual(record.score, Decimal(row["score"]))
            self.assertEqual(
                (record.comment, record.favorite, record.allocation_id is not None),
                (row["comment"], row["favorite"], row["allocated"]),
            )
        self.assertFalse(
            PeerReview.objects.filter(
                reviewer_id__in=[users[names[5]], users[names[6]]]
            ).exists()
        )
        self.assertEqual(PeerReviewAllocation.objects.count(), 21)
        export = admin.get("/api/reviews/export/")
        self.assertEqual(export.status_code, 200)
        book = load_workbook(BytesIO(export.content))
        self.assertEqual(book.sheetnames, ["评分", "评分与评语"])
        rows = list(book["评分"].values)
        header = rows[1]
        self.assertEqual(len(rows[2:]), 7)
        for row in rows[2:]:
            reviews = [r for (_, cid), r in expected.items() if cid == row[0]]
            scores = sorted(Decimal(r["score"]) for r in reviews)
            average = (sum(scores[1:-1]) / (len(scores) - 2)).quantize(Decimal("0.01"))
            self.assertEqual(Decimal(str(row[-2])), average)
            self.assertEqual(row[-1], sum(r["favorite"] for r in reviews))
            for review in reviews:
                self.assertEqual(
                    Decimal(str(row[header.index(review["username"])])),
                    Decimal(review["score"]),
                )
        self.config(admin, pk=competition_id, upload=False, review=False)
        self.assertEqual(
            self.post(
                clients[names[0]], "/api/reviews/submit/", {"reviews": []}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.post(
                admin,
                f"/admin/songs/competition/{competition_id}/archive/",
                format="multipart",
            ).status_code,
            302,
        )
        history = load_workbook(
            BytesIO(
                admin.get(f"/admin/songs/competition/{competition_id}/export/").content
            )
        )
        for title in book.sheetnames:
            self.assertEqual(list(book[title].values), list(history[title].values))
        next_id = self.config(admin, review=True)
        self.assertEqual(
            self.post(
                admin,
                f"/admin/songs/competition/{next_id}/activate/",
                format="multipart",
            ).status_code,
            302,
        )
        current = clients[names[0]].get("/api/reviews/tasks/").data
        self.assertEqual(
            (current["tasks"], current["favorites_used"], current["can_review"]),
            ([], 0, False),
        )
        self.assertEqual(
            (
                PeerReview.objects.count(),
                PeerReviewAllocation.objects.count(),
                Chart.objects.count(),
            ),
            (22, 21, 7),
        )
        self.assertEqual(Competition.objects.get(pk=competition_id).status, "archived")
        net_upload.assert_not_called()
