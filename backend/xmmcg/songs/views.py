"""Public contest information. Mutating operations live in domain modules."""

from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response
from users.models import identity_id
from .models import Announcement, Banner, Chart, CompetitionPhase, ContestSettings
from .phases import capabilities
from .serializers import AnnouncementSerializer, BannerSerializer, PhaseSerializer


@api_view(["GET"])
def get_banners(request):
    return Response(
        BannerSerializer(Banner.objects.filter(is_active=True), many=True).data
    )


@api_view(["GET"])
def get_announcements(request):
    return Response(
        AnnouncementSerializer(
            Announcement.objects.filter(is_active=True)[:50], many=True
        ).data
    )


@api_view(["GET"])
def get_phases(request):
    return Response(
        PhaseSerializer(CompetitionPhase.objects.filter(is_active=True), many=True).data
    )


@api_view(["GET"])
def get_status(request):
    phases = CompetitionPhase.objects.filter(is_active=True)
    now = timezone.now()
    phase = (
        phases.filter(start_time__lte=now, end_time__gt=now).first()
        or phases.filter(start_time__gt=now).order_by("start_time").first()
        or phases.order_by("-end_time").first()
    )
    charts = Chart.objects.filter(status="submitted").select_related("user__profile")
    config = ContestSettings.current()
    return Response(
        {
            "currentRound": phase.name if phase else "自由投稿",
            "status": phase.status if phase else "active",
            "statusText": {
                "active": "进行中",
                "upcoming": "待开始",
                "ended": "已结束",
            }.get(phase.status, "")
            if phase
            else "进行中",
            "participants": len({identity_id(chart.user) for chart in charts}),
            "submissions": charts.count(),
            "submissionsLabel": "谱面数",
            "capabilities": capabilities(),
            "review_config": {
                "reviews_per_chart": config.reviews_per_chart,
                "max_score": str(config.max_score),
                "max_favorites": config.max_favorites,
            },
        }
    )
