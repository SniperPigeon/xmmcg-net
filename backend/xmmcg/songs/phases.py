from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from .models import CompetitionPhase, ContestSettings, SongDraw


def active_phase(kind):
    now = timezone.now()
    return CompetitionPhase.objects.filter(
        kind=kind, is_active=True, start_time__lte=now, end_time__gt=now
    ).first()


def phase_allows(kind, default=False):
    phases = CompetitionPhase.objects.filter(kind=kind)
    return bool(active_phase(kind)) if phases.exists() else default


def capabilities():
    config = ContestSettings.current()
    selection = active_phase("song_selection")
    return {
        "songs_enabled": CompetitionPhase.objects.filter(
            kind="song_selection", is_active=True
        ).exists(),
        "song_upload": bool(selection)
        and not SongDraw.objects.filter(
            phase=selection, completed_at__isnull=False
        ).exists(),
        "chart_upload": config.submissions_open
        and phase_allows("submission", default=True),
        "review": config.reviews_open and phase_allows("review", default=True),
    }


def require_capability(name):
    if not capabilities()[name]:
        raise PermissionDenied("此操作当前未开放")
