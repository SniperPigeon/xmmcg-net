from uuid import UUID

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .majdata_service import sync_chart
from .models import Chart, Competition
from .phases import require_capability
from .serializers import ChartSerializer, ChartUploadSerializer
from .uploads import discard_new_assets, store_new_assets
from .bundles import chart_bundle_response


def chart_list(queryset, request):
    try:
        page = max(1, int(request.query_params.get("page", 1)))
        size = min(100, max(1, int(request.query_params.get("page_size", 20))))
    except ValueError:
        raise ValidationError("分页参数必须为整数")
    count = queryset.count()
    return Response(
        {
            "count": count,
            "page": page,
            "results": ChartSerializer(
                queryset[(page - 1) * size : page * size],
                many=True,
                context={"request": request},
            ).data,
        }
    )


@api_view(["GET", "POST"])
def charts_root(request):
    if request.method == "GET":
        return chart_list(
            Chart.objects.filter(competition=Competition.current(), status="submitted"),
            request,
        )
    if not request.user.is_authenticated:
        raise PermissionDenied("请先登录")
    competition = require_capability("chart_upload")
    try:
        key = UUID(str(request.data.get("submission_key", "")))
    except ValueError:
        raise ValidationError("缺少有效的投稿标识")
    existing = Chart.objects.filter(submission_key=key).first()
    if existing:
        if (
            existing.user_id != request.user.pk
            or existing.competition_id != competition.pk
        ):
            raise ValidationError("投稿标识已使用")
        return Response(
            {
                "success": True,
                "chart": ChartSerializer(existing, context={"request": request}).data,
            }
        )
    serializer = ChartUploadSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    chart = Chart(
        competition=competition,
        user=request.user,
        submitted_at=timezone.now(),
        **serializer.validated_data,
    )
    try:
        store_new_assets(chart)
        with transaction.atomic():
            require_capability("chart_upload", competition.pk)
            chart.save()
            chart.contributors.add(request.user)
    except Exception as error:
        discard_new_assets(chart)
        if isinstance(error, IntegrityError):
            raise ValidationError("重复投稿，请刷新我的谱面")
        raise
    sync_chart(chart)
    return Response(
        {
            "success": True,
            "chart": ChartSerializer(chart, context={"request": request}).data,
        },
        status=201,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_charts(request):
    return chart_list(
        Chart.objects.filter(user=request.user, competition=Competition.current()),
        request,
    )


@api_view(["GET"])
def chart_detail(request, chart_id):
    chart = get_object_or_404(
        Chart, pk=chart_id, competition=Competition.current(), status="submitted"
    )
    return Response(ChartSerializer(chart, context={"request": request}).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def retry_sync(request, chart_id):
    chart = get_object_or_404(
        Chart, pk=chart_id, competition=Competition.current(), status="submitted"
    )
    if chart.user_id != request.user.pk and not request.user.is_staff:
        raise PermissionDenied("只能重试自己的投稿")
    if chart.net_sync_status in ("unknown", "syncing"):
        raise ValidationError("请先由管理员核对 Net 上的上传结果")
    sync_chart(chart)
    return Response(ChartSerializer(chart, context={"request": request}).data)


@api_view(["GET"])
def download_bundle(request, chart_id):
    chart = get_object_or_404(
        Chart, pk=chart_id, competition=Competition.current(), status="submitted"
    )
    return chart_bundle_response([chart], filename=f"chart-{chart.pk}.zip")
