from decimal import Decimal
from io import BytesIO
from django.test import TestCase
from openpyxl import load_workbook
from songs.models import PeerReview
from songs.exports import export_peer_review_scores, trimmed_mean
from .test_peer_review_allocation import make_user, make_chart


class ExportTests(TestCase):
    def test_decimal_scores_comments_favorites_and_formula_escaping(self):
        chart = make_chart(make_user("author"), "=unsafe")
        for index, score in enumerate(["41.25", "42.50", "43.75"]):
            PeerReview.objects.create(
                chart=chart,
                reviewer=make_user(f"r{index}"),
                score=score,
                comment="=unsafe",
                favorite=index == 1,
            )
        workbook = load_workbook(BytesIO(export_peer_review_scores()))
        row = list(workbook["评分"].values)[1]
        self.assertEqual(row[1], "'=unsafe")
        self.assertEqual(row[-2:], (42.5, 1))
        self.assertEqual(list(workbook["评分与评语"].values)[1][4], "'=unsafe")

    def test_trimmed_mean(self):
        self.assertEqual(trimmed_mean([1, 2, 50]), Decimal("2.00"))
        self.assertEqual(trimmed_mean([1, 2]), Decimal("1.50"))
        self.assertIsNone(trimmed_mean([]))
