from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from .models import Competition, CompetitionPhase, SongDraw


def active_phase(kind, competition):
    now = timezone.now()
    return CompetitionPhase.objects.filter(
        competition=competition,
        kind=kind,
        is_active=True,
        start_time__lte=now,
        end_time__gt=now,
    ).first()


def phase_allows(kind, competition, default=False):
    phases = CompetitionPhase.objects.filter(competition=competition, kind=kind)
    return bool(active_phase(kind, competition)) if phases.exists() else default


def capabilities(competition):
    result = dict.fromkeys(
        ("songs_enabled", "song_upload", "chart_upload", "review"), False
    )
    if competition is None or competition.status != "active":
        return result
    selection = active_phase("song_selection", competition)
    return {
        "songs_enabled": competition.phases.filter(
            kind="song_selection", is_active=True
        ).exists(),
        "song_upload": bool(selection)
        and not SongDraw.objects.filter(
            phase=selection, completed_at__isnull=False
        ).exists(),
        "chart_upload": competition.submissions_open
        and phase_allows("submission", competition, default=True),
        "review": competition.reviews_open
        and phase_allows("review", competition, default=True),
    }


def require_capability(name, competition_id=None):
    competition = Competition.current()
    if (
        competition_id is not None
        and (competition is None or competition.pk != competition_id)
    ) or not capabilities(competition)[name]:
        raise PermissionDenied("此操作当前未开放，请确认比赛与阶段")
    return competition
