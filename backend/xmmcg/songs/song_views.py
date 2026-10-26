from django.db import transaction
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from users.models import identity_id
from .draws import join_draw, run_draw, selection_phase
from .models import CompetitionPhase, Song, SongDraw
from .phases import require_capability
from .serializers import SongSerializer, SongUploadSerializer
from .uploads import discard_new_assets, store_new_assets


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def songs_root(request):
    require_capability("songs_enabled")
    if request.method == "GET":
        return Response(
            SongSerializer(
                Song.objects.filter(
                    phase__is_active=True, phase__kind="song_selection"
                ),
                many=True,
                context={"request": request},
            ).data
        )
    serializer = SongUploadSerializer(data=request.data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    phase = selection_phase()
    if Song.objects.filter(user=request.user).count() >= settings.MAX_SONGS_PER_USER:
        raise ValidationError(
            f"已达到每个用户最多 {settings.MAX_SONGS_PER_USER} 首歌曲的限制"
        )
    song = Song(user=request.user, phase=phase, **serializer.validated_data)
    try:
        store_new_assets(song)
        with transaction.atomic():
            phase = CompetitionPhase.objects.select_for_update().get(pk=phase.pk)
            if not phase.is_active or phase.status != "active":
                raise ValidationError("歌曲上传阶段已结束或停用")
            if SongDraw.objects.filter(
                phase=phase, completed_at__isnull=False
            ).exists():
                raise ValidationError("抽选已完成，不能继续上传歌曲")
            if (
                Song.objects.filter(user=request.user).count()
                >= settings.MAX_SONGS_PER_USER
            ):
                raise ValidationError(
                    f"已达到每个用户最多 {settings.MAX_SONGS_PER_USER} 首歌曲的限制"
                )
            join_draw(request.user)
            song.save()
    except Exception:
        discard_new_assets(song)
        raise
    return Response(SongSerializer(song, context={"request": request}).data, status=201)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def join(request):
    entry = join_draw(request.user)
    return Response({"joined": True, "phase_id": entry.draw.phase_id})


@api_view(["POST"])
@permission_classes([IsAdminUser])
def draw(request, phase_id):
    get_object_or_404(CompetitionPhase, pk=phase_id)
    result = run_draw(phase_id)
    return Response(
        {"completed_at": result.completed_at, "participants": result.entries.count()}
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_draws(request):
    require_capability("songs_enabled")
    from .models import SongDrawEntry

    entries = SongDrawEntry.objects.filter(
        user_id=identity_id(request.user), draw__phase__is_active=True
    ).select_related("song", "draw__phase")
    return Response(
        [
            {
                "phase": entry.draw.phase.name,
                "completed": bool(entry.draw.completed_at),
                "song": SongSerializer(entry.song, context={"request": request}).data
                if entry.song
                else None,
            }
            for entry in entries
        ]
    )
