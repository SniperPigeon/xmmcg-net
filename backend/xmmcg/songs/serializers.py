import hashlib
import re
from pathlib import PurePosixPath

from django.conf import settings
from rest_framework import serializers
from .models import Announcement, Banner, Chart, CompetitionPhase, Song
from .submissions import can_retry_sync


def validate_asset(value, extensions, limit, label):
    if PurePosixPath(value.name).suffix.lower() not in extensions:
        raise serializers.ValidationError(f"{label}格式不支持")
    if value.size == 0 or value.size > limit * 1024 * 1024:
        raise serializers.ValidationError(f"{label}不能为空，大小不能超过 {limit} MB")
    return value


class AssetValidationMixin:
    def validate_audio_file(self, value):
        return validate_asset(
            value,
            {".mp3", ".ogg", ".wav", ".flac", ".m4a", ".aac", ".wma"},
            settings.MAX_AUDIO_SIZE_MB,
            "音频",
        )

    def validate_cover_image(self, value):
        return validate_asset(
            value,
            {".jpg", ".jpeg", ".png", ".gif", ".webp"},
            settings.MAX_COVER_SIZE_MB,
            "封面",
        )

    def validate_background_video(self, value):
        return validate_asset(value, {".mp4"}, settings.MAX_VIDEO_SIZE_MB, "视频")


class ChartUploadSerializer(AssetValidationMixin, serializers.ModelSerializer):
    submission_key = serializers.UUIDField(required=True)
    collaborator_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        default=list,
        write_only=True,
    )

    class Meta:
        model = Chart
        fields = (
            "title",
            "designer",
            "chart_file",
            "audio_file",
            "cover_image",
            "background_video",
            "submission_key",
            "collaborator_ids",
        )
        extra_kwargs = {
            "title": {"required": False, "allow_blank": True},
            "designer": {"required": False, "allow_blank": True},
            "chart_file": {"required": True, "allow_null": False},
            "audio_file": {"required": True, "allow_null": False},
            "cover_image": {"required": True, "allow_null": False},
        }

    def validate_chart_file(self, value):
        validate_asset(value, {".txt"}, settings.MAX_CHART_SIZE_MB, "谱面")
        try:
            content = value.read().decode("utf-8-sig")
        except UnicodeDecodeError:
            raise serializers.ValidationError("谱面需要使用 UTF-8 编码")
        finally:
            value.seek(0)
        self.metadata = {
            key: match.group(1).strip()
            if (match := re.search(r"^\s*&" + key + r"=([^\r\n]*)", content, re.M))
            else ""
            for key in ("title", "des")
        }
        return value

    def validate(self, attrs):
        attrs["title"] = (
            attrs.get("title") or self.metadata.get("title") or "未命名谱面"
        )
        attrs["designer"] = (
            attrs.get("designer")
            or self.metadata.get("des")
            or self.context["request"].user.username
        )
        if len(attrs["title"]) > 200 or len(attrs["designer"]) > 100:
            raise serializers.ValidationError("标题或谱师名义过长")
        return attrs


class ChartSerializer(serializers.ModelSerializer):
    is_collaboration = serializers.SerializerMethodField()
    contributors = serializers.SerializerMethodField()
    can_retry_sync = serializers.SerializerMethodField()

    def get_is_collaboration(self, chart):
        return any(user.pk != chart.user_id for user in chart.contributors.all())

    def get_contributors(self, chart):
        request = self.context.get("request")
        user = request.user if request else None
        authors = list(chart.contributors.all())
        if not user or not user.is_authenticated:
            return []
        if user.pk not in {chart.user_id, *(author.pk for author in authors)} and not (
            user.is_staff
            and (
                user.has_perm("songs.view_chart") or user.has_perm("songs.change_chart")
            )
        ):
            return []
        by_id = {chart.user_id: chart.user, **{author.pk: author for author in authors}}
        return [
            {"id": author.pk, "username": author.username} for author in by_id.values()
        ]

    def get_can_retry_sync(self, chart):
        request = self.context.get("request")
        return can_retry_sync(request.user if request else None, chart)

    chart_file_url = serializers.FileField(source="chart_file", read_only=True)
    audio_url = serializers.FileField(source="audio_file", read_only=True)
    cover_url = serializers.FileField(source="cover_image", read_only=True)
    video_url = serializers.FileField(source="background_video", read_only=True)

    class Meta:
        model = Chart
        fields = (
            "id",
            "guid",
            "is_collaboration",
            "contributors",
            "can_retry_sync",
            "title",
            "designer",
            "status",
            "chart_file_url",
            "audio_url",
            "cover_url",
            "video_url",
            "created_at",
            "submitted_at",
            "net_sync_status",
            "net_url",
        )


class SongUploadSerializer(AssetValidationMixin, serializers.ModelSerializer):
    class Meta:
        model = Song
        fields = (
            "title",
            "audio_file",
            "cover_image",
            "background_video",
            "netease_url",
        )

    def validate(self, validated_data):
        audio = validated_data["audio_file"]
        digest = hashlib.sha256()
        for chunk in audio.chunks():
            digest.update(chunk)
        audio.seek(0)
        return {
            **validated_data,
            "audio_hash": digest.hexdigest(),
            "file_size": audio.size,
        }


class SongSerializer(serializers.ModelSerializer):
    audio_url = serializers.FileField(source="audio_file", read_only=True)
    cover_url = serializers.FileField(source="cover_image", read_only=True)
    video_url = serializers.FileField(source="background_video", read_only=True)

    class Meta:
        model = Song
        fields = ("id", "title", "audio_url", "cover_url", "video_url", "netease_url")


class PhaseSerializer(serializers.ModelSerializer):
    status = serializers.CharField(read_only=True)
    time_remaining = serializers.CharField(read_only=True)
    progress_percent = serializers.IntegerField(read_only=True)

    class Meta:
        model = CompetitionPhase
        fields = (
            "id",
            "name",
            "phase_key",
            "kind",
            "description",
            "start_time",
            "end_time",
            "order",
            "is_active",
            "status",
            "time_remaining",
            "progress_percent",
        )


class AnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = ("id", "title", "content", "category", "is_pinned", "created_at")


class BannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Banner
        fields = ("id", "title", "content", "image_url", "link", "button_text", "color")
