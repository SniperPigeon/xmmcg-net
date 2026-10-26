"""Score exports use stored decimal scores and preserve the existing trimmed mean."""

from io import BytesIO
from decimal import Decimal, ROUND_HALF_UP
from openpyxl import Workbook
from .models import Chart


def trimmed_mean(scores):
    scores = sorted(Decimal(str(score)) for score in scores)
    if len(scores) >= 3:
        scores = scores[1:-1]
    return (
        (sum(scores) / len(scores)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if scores
        else None
    )


def safe_cell(value):
    return (
        "'" + value
        if isinstance(value, str) and value.startswith(("=", "+", "-", "@"))
        else value
    )


def export_peer_review_scores(chart_ids=None):
    charts = Chart.objects.filter(status="submitted").prefetch_related(
        "reviews__reviewer"
    )
    if chart_ids is not None:
        charts = charts.filter(pk__in=chart_ids)
    charts = list(charts)
    reviewers = sorted(
        {review.reviewer.username for chart in charts for review in chart.reviews.all()}
    )
    book = Workbook()
    scores_sheet = book.active
    scores_sheet.title = "评分"
    comments_sheet = book.create_sheet("评分与评语")
    metadata = ["谱面ID", "标题", "谱师名义"]
    scores_sheet.append(
        metadata + [safe_cell(name) for name in reviewers] + ["去高低均分", "真爱票数"]
    )
    comments_sheet.append(
        metadata
        + [
            safe_cell(name + label)
            for name in reviewers
            for label in (" 评分", " 评语")
        ]
        + ["去高低均分", "真爱票数"]
    )
    for chart in charts:
        reviews = {review.reviewer.username: review for review in chart.reviews.all()}
        summary = [
            trimmed_mean([review.score for review in reviews.values()]),
            sum(review.favorite for review in reviews.values()),
        ]
        meta = [chart.pk, safe_cell(chart.title), safe_cell(chart.designer)]
        scores_sheet.append(
            meta
            + [reviews[name].score if name in reviews else None for name in reviewers]
            + summary
        )
        comments_sheet.append(
            meta
            + [
                value
                for name in reviewers
                for value in (
                    (reviews[name].score, safe_cell(reviews[name].comment))
                    if name in reviews
                    else (None, None)
                )
            ]
            + summary
        )
    for sheet in book:
        sheet.freeze_panes = "D2"
        sheet.auto_filter.ref = sheet.dimensions
        for column in sheet.columns:
            sheet.column_dimensions[column[0].column_letter].width = 22
    output = BytesIO()
    book.save(output)
    return output.getvalue()
