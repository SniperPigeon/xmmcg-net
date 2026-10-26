from django.http import HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from users.models import identity_id
from .exports import export_peer_review_scores
from .models import ContestSettings, PeerReview, PeerReviewAllocation
from .phases import capabilities
from .reviews import (
    allocate_reviews,
    authors,
    reviewer_ids,
    reviewable_charts,
    submit_reviews,
)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def tasks(request):
    person = identity_id(request.user)
    config = ContestSettings.current()
    reviews = {
        review.chart_id: review
        for review in PeerReview.objects.filter(reviewer_id=person).select_related(
            "chart"
        )
    }
    allocated = PeerReviewAllocation.objects.filter(
        reviewer_id=person, chart__status="submitted"
    ).select_related("chart")

    def row(chart, allocation=None):
        review = reviews.get(chart.pk)
        return {
            "chart_id": chart.pk,
            "title": chart.title,
            "designer": chart.designer,
            "allocation_id": allocation.pk if allocation else None,
            "completed": review is not None,
            "score": str(review.score) if review else None,
            "comment": review.comment if review else "",
            "favorite": review.favorite if review else False,
        }

    result = [row(allocation.chart, allocation) for allocation in allocated]
    existing_ids = {item["chart_id"] for item in result}
    result += [
        row(review.chart)
        for review in reviews.values()
        if review.chart_id not in existing_ids
    ]
    return Response(
        {
            "tasks": result,
            "can_review": person in reviewer_ids(),
            "is_open": capabilities()["review"],
            "config": {
                "max_score": str(config.max_score),
                "max_favorites": config.max_favorites,
            },
            "favorites_used": sum(review.favorite for review in reviews.values()),
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def available(request):
    person = identity_id(request.user)
    excluded = set(
        PeerReview.objects.filter(reviewer_id=person).values_list("chart_id", flat=True)
    )
    excluded.update(
        PeerReviewAllocation.objects.filter(reviewer_id=person).values_list(
            "chart_id", flat=True
        )
    )
    return Response(
        [
            {"id": chart.pk, "title": chart.title, "designer": chart.designer}
            for chart in reviewable_charts().exclude(pk__in=excluded)
            if person not in authors(chart)
        ]
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def submit(request):
    count = submit_reviews(request.user, request.data.get("reviews", []))
    return Response({"success": True, "submitted": count})


@api_view(["POST"])
@permission_classes([IsAdminUser])
def allocate(request):
    return Response(allocate_reviews(commit=request.data.get("commit") is True))


@api_view(["GET"])
@permission_classes([IsAdminUser])
def export(request):
    response = HttpResponse(
        export_peer_review_scores(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="scores.xlsx"'
    return response
