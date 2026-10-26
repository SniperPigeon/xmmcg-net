import random
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from users.models import identity_id
from .models import CompetitionPhase, Song, SongDraw, SongDrawEntry
from .phases import active_phase
from .competitions import require_active


def selection_phase(competition_id=None):
    competition = require_active(competition_id)
    phase = active_phase("song_selection", competition)
    if phase is None:
        raise ValidationError("当前没有开放的歌曲上传与抽选阶段")
    return phase


@transaction.atomic
def join_draw(user, competition_id=None):
    phase = CompetitionPhase.objects.select_for_update().get(
        pk=selection_phase(competition_id).pk
    )
    draw, _ = SongDraw.objects.get_or_create(phase=phase)
    if draw.completed_at:
        raise ValidationError("本阶段已完成抽选")
    entry, _ = SongDrawEntry.objects.get_or_create(draw=draw, user_id=identity_id(user))
    return entry


@transaction.atomic
def run_draw(phase_id):
    # 抽选和报名使用同一短写事务，避免抽选期间改变参与者或曲目池。
    phase = CompetitionPhase.objects.select_for_update().get(pk=phase_id)
    require_active(phase.competition_id)
    if (
        phase.kind != "song_selection"
        or not phase.is_active
        or phase.status == "upcoming"
    ):
        raise ValidationError("该阶段尚未开放或已禁用")
    draw, _ = SongDraw.objects.get_or_create(phase=phase)
    if draw.completed_at:
        return draw
    songs = list(Song.objects.filter(phase=phase, competition_id=phase.competition_id))
    entries = list(draw.entries.all())
    if not songs or not entries:
        raise ValidationError("抽选需要至少一首歌曲和一位参与者")
    rng = random.SystemRandom()
    rng.shuffle(songs)
    rng.shuffle(entries)
    for index, entry in enumerate(entries):
        # 曲目少于参与者时均衡复用，不引入竞价或保底规则。
        entry.song = songs[index % len(songs)]
    SongDrawEntry.objects.bulk_update(entries, ["song"])
    draw.completed_at = timezone.now()
    draw.save(update_fields=["completed_at"])
    return draw
