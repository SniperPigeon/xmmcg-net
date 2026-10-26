import random
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from users.models import identity_id
from .models import CompetitionPhase, Song, SongDraw, SongDrawEntry
from .phases import active_phase


def selection_phase():
    phase = active_phase("song_selection")
    if phase is None:
        raise ValidationError("当前没有开放的歌曲上传与抽选阶段")
    return phase


@transaction.atomic
def join_draw(user):
    phase = CompetitionPhase.objects.select_for_update().get(pk=selection_phase().pk)
    draw, _ = SongDraw.objects.get_or_create(phase=phase)
    if draw.completed_at:
        raise ValidationError("本阶段已完成抽选")
    entry, _ = SongDrawEntry.objects.get_or_create(draw=draw, user_id=identity_id(user))
    return entry


@transaction.atomic
def run_draw(phase_id):
    # The same lock is used by uploads/joining, so the pool cannot change mid-draw.
    phase = CompetitionPhase.objects.select_for_update().get(pk=phase_id)
    if (
        phase.kind != "song_selection"
        or not phase.is_active
        or phase.status == "upcoming"
    ):
        raise ValidationError("该阶段尚未开放或已禁用")
    draw, _ = SongDraw.objects.get_or_create(phase=phase)
    if draw.completed_at:
        return draw
    songs = list(Song.objects.filter(phase=phase))
    entries = list(draw.entries.all())
    if not songs or not entries:
        raise ValidationError("抽选需要至少一首歌曲和一位参与者")
    rng = random.SystemRandom()
    rng.shuffle(songs)
    rng.shuffle(entries)
    for index, entry in enumerate(entries):
        # Balanced reuse allows fewer songs than participants without special bidding rules.
        entry.song = songs[index % len(songs)]
    SongDrawEntry.objects.bulk_update(entries, ["song"])
    draw.completed_at = timezone.now()
    draw.save(update_fields=["completed_at"])
    return draw
