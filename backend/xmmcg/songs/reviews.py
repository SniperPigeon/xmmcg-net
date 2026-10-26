"""每人每谱一份评分，不分配本人或绑定账号参与制作的谱面。"""

from collections import Counter
from decimal import Decimal
import random

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from users.models import identity_id
from .models import Chart, ContestSettings, PeerReview, PeerReviewAllocation
from .phases import require_capability


def authors(chart):
    return {identity_id(chart.user)} | {
        identity_id(user) for user in chart.contributors.all()
    }


def reviewable_charts():
    return (
        Chart.objects.filter(status="submitted")
        .select_related("user__profile")
        .prefetch_related("contributors__profile")
    )


def reviewer_ids():
    result = set()
    for chart in reviewable_charts():
        result.update(authors(chart))
    return set(
        get_user_model()
        .objects.filter(pk__in=result, is_active=True)
        .values_list("pk", flat=True)
    )


def require_reviewer(user):
    person = identity_id(user)
    if person not in reviewer_ids():
        raise PermissionDenied("提交谱面后才可参与评分（绑定小号的投稿也计入）")
    return person


@transaction.atomic
def allocate_reviews(*, commit=False):
    config = ContestSettings.current()
    # 在同一短写事务中分配任务，保留已有任务和已提交评分。
    config = ContestSettings.objects.select_for_update().get(pk=config.pk)
    charts = list(reviewable_charts())
    participants = reviewer_ids()
    if not charts or not participants:
        raise ValidationError("没有可分配的谱面或评分者")
    pairs = set(PeerReviewAllocation.objects.values_list("reviewer_id", "chart_id"))
    pairs.update(PeerReview.objects.values_list("reviewer_id", "chart_id"))
    task_counts = Counter(person for person, chart in pairs)
    chart_counts = Counter(chart for person, chart in pairs)
    additions = []
    random.SystemRandom().shuffle(charts)
    for chart in charts:
        eligible = list(participants - authors(chart))
        random.SystemRandom().shuffle(eligible)
        eligible.sort(key=lambda uid: task_counts[uid])
        for person in eligible:
            if chart_counts[chart.pk] >= config.reviews_per_chart:
                break
            if (person, chart.pk) in pairs:
                continue
            additions.append(PeerReviewAllocation(reviewer_id=person, chart=chart))
            pairs.add((person, chart.pk))
            task_counts[person] += 1
            chart_counts[chart.pk] += 1
    if commit:
        PeerReviewAllocation.objects.bulk_create(additions)
    return {
        "committed": commit,
        "new_tasks": len(additions),
        "charts_count": len(charts),
        "reviewers_count": len(participants),
        "target": config.reviews_per_chart,
        "shortfalls": [
            {
                "chart_id": chart.pk,
                "title": chart.title,
                "missing": config.reviews_per_chart - chart_counts[chart.pk],
            }
            for chart in charts
            if chart_counts[chart.pk] < config.reviews_per_chart
        ],
        "tasks_per_reviewer": [
            {"user_id": uid, "count": task_counts[uid]} for uid in sorted(participants)
        ],
    }


class ReviewInput(serializers.Serializer):
    chart_id = serializers.IntegerField(min_value=1)
    score = serializers.DecimalField(
        max_digits=7, decimal_places=2, min_value=Decimal("0")
    )
    comment = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=20000
    )
    favorite = serializers.BooleanField(required=False, default=False)


@transaction.atomic
def submit_reviews(user, items):
    require_capability("review")
    person = require_reviewer(user)
    config = ContestSettings.current()
    config = ContestSettings.objects.select_for_update().get(pk=config.pk)
    serializer = ReviewInput(data=items, many=True)
    serializer.is_valid(raise_exception=True)
    rows = serializer.validated_data
    if not rows or len(rows) > 1000:
        raise ValidationError("请提交 1 至 1000 条评分")
    ids = [row["chart_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValidationError("一次提交不能包含重复谱面")
    if PeerReview.objects.filter(reviewer_id=person, chart_id__in=ids).exists():
        raise ValidationError("包含已经提交过的评分，请刷新任务列表")
    used_favorites = PeerReview.objects.filter(
        reviewer_id=person, favorite=True
    ).count()
    if used_favorites + sum(row["favorite"] for row in rows) > config.max_favorites:
        raise ValidationError(f"每人最多 {config.max_favorites} 张真爱票")
    charts = {chart.pk: chart for chart in reviewable_charts().filter(pk__in=ids)}
    allocations = dict(
        PeerReviewAllocation.objects.filter(
            reviewer_id=person, chart_id__in=ids
        ).values_list("chart_id", "id")
    )
    for row in rows:
        chart = charts.get(row["chart_id"])
        if chart is None:
            raise ValidationError("谱面不存在或已归档")
        if person in authors(chart):
            raise ValidationError("不能给本人或绑定账号参与创作的谱面评分")
        if row["score"] > config.max_score:
            raise ValidationError(f"评分不能超过 {config.max_score}")
    PeerReview.objects.bulk_create(
        [
            PeerReview(
                reviewer_id=person,
                allocation_id=allocations.get(row["chart_id"]),
                **row,
            )
            for row in rows
        ]
    )
    return len(rows)
