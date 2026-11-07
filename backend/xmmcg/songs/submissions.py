"""独立与合作投稿共用名额；写入前必须在 SQLite IMMEDIATE 事务中复核。"""

from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework.exceptions import ValidationError
from users.models import identity_id
from .models import Chart, CollaborationConsent
from .phases import capabilities


def participation_charts(competition, account_ids):
    return (
        Chart.objects.filter(competition=competition)
        .filter(Q(user_id__in=account_ids) | Q(contributors__id__in=account_ids))
        .distinct()
    )


def quota_accounts(competition, user):
    if competition.submission_quota_scope == "account":
        return [user.pk]
    root = identity_id(user)
    return list(
        get_user_model()
        .objects.filter(Q(pk=root) | Q(profile__main_account_id=root))
        .values_list("pk", flat=True)
    )


def quota_used(competition, user):
    return (
        participation_charts(competition, quota_accounts(competition, user))
        .filter(status="submitted")
        .count()
    )


def ensure_quota(competition, user):
    if (
        competition.max_chart_submissions
        and quota_used(competition, user) >= competition.max_chart_submissions
    ):
        label = (
            "账号" if competition.submission_quota_scope == "account" else "大小号组"
        )
        raise ValidationError(
            f"{user.username} 的{label}已达到本届 {competition.max_chart_submissions} 张谱面上限（含合作投稿）"
        )


def submission_status(competition, user):
    if competition is None:
        return {
            "competition_id": None,
            "can_upload": False,
            "used": 0,
            "limit": 0,
            "remaining": 0,
            "scope": "account",
            "allow_collaboration": False,
            "require_collaborator_approval": False,
        }
    used = quota_used(competition, user)
    limit = competition.max_chart_submissions
    return {
        "competition_id": competition.pk,
        "can_upload": capabilities(competition)["chart_upload"]
        and (limit == 0 or used < limit),
        "used": used,
        "limit": limit,
        "remaining": max(0, limit - used) if limit else None,
        "scope": competition.submission_quota_scope,
        "allow_collaboration": competition.allow_collaboration,
        "require_collaborator_approval": competition.require_collaborator_approval,
    }


def validate_authors(competition, uploader, collaborator_ids):
    if (
        len(collaborator_ids) != len(set(collaborator_ids))
        or uploader.pk in collaborator_ids
    ):
        raise ValidationError("合作谱师不能重复选择，也无需选择上传者本人")
    if collaborator_ids and not competition.allow_collaboration:
        raise ValidationError("本届比赛未开放合作谱面")
    ids = [uploader.pk, *collaborator_ids]
    authors = list(
        get_user_model()
        .objects.filter(pk__in=ids, is_active=True)
        .select_related("profile")
    )
    if len(authors) != len(ids):
        raise ValidationError("投稿账号或合作谱师不存在，或已停用")
    for author in authors:
        ensure_quota(competition, author)
    consents = list(
        CollaborationConsent.objects.filter(
            competition=competition,
            uploader=uploader,
            author_id__in=collaborator_ids,
            used_by__isnull=True,
        )
    )
    if competition.require_collaborator_approval and len(consents) != len(
        collaborator_ids
    ):
        raise ValidationError("部分合作谱师尚未授权你投稿，或授权已撤销/使用")
    return authors, consents


def can_retry_sync(user, chart):
    return bool(
        user
        and user.is_authenticated
        and (
            chart.user_id == user.pk
            or (user.is_staff and user.has_perm("songs.change_chart"))
        )
    )
