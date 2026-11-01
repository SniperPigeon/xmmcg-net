from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .competitions import require_active
from .models import CollaborationConsent, Competition
from .phases import require_capability
from .submissions import ensure_quota, quota_used, submission_status


def require_collaboration():
    competition = require_capability("chart_upload")
    if not competition.allow_collaboration:
        raise PermissionDenied("本届比赛未开放合作谱面")
    return competition


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def status(request):
    return Response(submission_status(Competition.current(), request.user))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def accounts(request):
    competition = require_collaboration()
    purpose = request.query_params.get("purpose", "collaborator")
    if purpose not in ("collaborator", "uploader"):
        raise ValidationError("账号查找用途无效")
    query = request.query_params.get("q", "").strip()
    users = (
        get_user_model()
        .objects.filter(is_active=True)
        .exclude(pk=request.user.pk)
        .select_related("profile")
    )
    if purpose == "collaborator" and competition.require_collaborator_approval:
        users = users.filter(
            pk__in=CollaborationConsent.objects.filter(
                competition=competition, uploader=request.user, used_by__isnull=True
            ).values("author_id")
        )
    elif len(query) < 2:
        return Response([])
    if query:
        users = users.filter(username__icontains=query)
    return Response(
        [
            {
                "id": user.pk,
                "username": user.username,
                "available": competition.max_chart_submissions == 0
                or quota_used(competition, user) < competition.max_chart_submissions,
            }
            for user in users.order_by("username")[:20]
        ]
    )


class ConsentInput(serializers.Serializer):
    uploader_id = serializers.IntegerField(min_value=1)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def consents(request):
    if request.method == "GET":
        rows = (
            CollaborationConsent.objects.filter(
                competition=Competition.current(), author=request.user
            )
            .select_related("uploader")
            .order_by("-created_at")
        )
        return Response(
            [
                {
                    "id": row.pk,
                    "uploader": {
                        "id": row.uploader_id,
                        "username": row.uploader.username,
                    },
                    "used": row.used_by_id is not None,
                }
                for row in rows
            ]
        )
    data = ConsentInput(data=request.data)
    data.is_valid(raise_exception=True)
    with transaction.atomic():
        competition = require_collaboration()
        if not competition.require_collaborator_approval:
            raise ValidationError("本届比赛无需提前授权，可由上传者直接选择合作谱师")
        uploader = get_object_or_404(
            get_user_model().objects.select_related("profile"),
            pk=data.validated_data["uploader_id"],
            is_active=True,
        )
        if uploader.pk == request.user.pk:
            raise ValidationError("不能授权自己")
        ensure_quota(competition, request.user)
        ensure_quota(competition, uploader)
        consent, created = CollaborationConsent.objects.get_or_create(
            competition=competition,
            author=request.user,
            uploader=uploader,
            used_by__isnull=True,
        )
    return Response(
        {
            "id": consent.pk,
            "uploader": {"id": uploader.pk, "username": uploader.username},
            "used": False,
        },
        status=201 if created else 200,
    )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def revoke(request, consent_id):
    consent = get_object_or_404(
        CollaborationConsent, pk=consent_id, author=request.user
    )
    require_active(consent.competition_id)
    if consent.used_by_id:
        raise ValidationError("授权已用于投稿，不能撤销已提交的合作关系")
    consent.delete()
    return Response(status=204)
