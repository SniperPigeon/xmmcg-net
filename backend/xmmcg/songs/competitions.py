"""比赛生命周期。SQLite IMMEDIATE 事务串行化换届与业务写入。"""

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import Competition, CompetitionPhase


CONFIG_FIELDS = (
    "submissions_open",
    "reviews_open",
    "reviews_per_chart",
    "max_score",
    "max_favorites",
)


def require_active(competition_id=None):
    competition = Competition.objects.filter(status="active").first()
    if competition is None or (
        competition_id is not None and competition.pk != competition_id
    ):
        raise ValidationError("比赛尚未启用或已归档，请刷新页面")
    return competition


@transaction.atomic
def activate_competition(competition_id):
    competition = Competition.objects.get(pk=competition_id)
    if competition.status != "draft":
        raise ValidationError("只能启用筹备中的比赛")
    if Competition.objects.filter(status="active").exists():
        raise ValidationError("请先归档当前比赛，再启用新比赛")
    competition.status = "active"
    competition.activated_at = timezone.now()
    competition.save(update_fields=["status", "activated_at"])
    return competition


@transaction.atomic
def archive_competition(competition_id):
    competition = Competition.objects.get(pk=competition_id)
    if competition.status != "active":
        raise ValidationError("只能归档进行中的比赛")
    if competition.charts.filter(net_sync_status="syncing").exists():
        raise ValidationError(
            "仍有谱面正在同步 Net，请等待完成；异常中断的同步需先人工核对"
        )
    competition.status = "archived"
    competition.archived_at = timezone.now()
    competition.save(update_fields=["status", "archived_at"])
    return competition


def copy_phases(source, target):
    # 只复制模板，保留日期供管理员调整；不带入抽选结果或开放开关。
    CompetitionPhase.objects.bulk_create(
        [
            CompetitionPhase(
                competition=target,
                name=phase.name,
                phase_key=phase.phase_key,
                kind=phase.kind,
                description=phase.description,
                start_time=phase.start_time,
                end_time=phase.end_time,
                order=phase.order,
                is_active=False,
            )
            for phase in source.phases.all()
        ]
    )
