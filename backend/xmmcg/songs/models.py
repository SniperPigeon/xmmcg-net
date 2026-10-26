"""The contest's records. A chart is independent of songs and draws."""

import uuid
from decimal import Decimal
from pathlib import PurePosixPath

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


def asset_key(instance, filename, category):
    return f"{category}/{uuid.uuid4().hex}/{PurePosixPath(filename).name}"


# Keep these names importable: historical migrations reference them.
def get_audio_filename(instance, filename):
    return asset_key(instance, filename, "songs/audio")


def get_cover_filename(instance, filename):
    return asset_key(instance, filename, "songs/covers")


def get_video_filename(instance, filename):
    return asset_key(instance, filename, "songs/video")


def get_chart_filename(instance, filename):
    return asset_key(instance, "maidata.txt", "charts/data")


def get_chart_audio_filename(instance, filename):
    return asset_key(instance, filename, "charts/audio")


def get_chart_cover_filename(instance, filename):
    return asset_key(instance, filename, "charts/covers")


def get_chart_video_filename(instance, filename):
    return asset_key(instance, filename, "charts/video")


def get_default_page_access():
    # Required only when applying migration 0001.
    return {"songs": True, "charts": True, "profile": True, "eval": True}


class Banner(models.Model):
    title = models.CharField(max_length=100)
    content = models.TextField()
    image_url = models.CharField(null=True, blank=True)
    link = models.URLField(null=True, blank=True)
    button_text = models.CharField(max_length=50, default="了解更多")
    color = models.CharField(max_length=20, default="#409EFF")
    priority = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-priority", "-created_at"]
        verbose_name = verbose_name_plural = "Banner"

    def __str__(self):
        return self.title


class Announcement(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField(help_text="支持 Markdown")
    category = models.CharField(
        max_length=20,
        default="news",
        choices=[("news", "新闻"), ("event", "活动"), ("notice", "通知")],
    )
    priority = models.IntegerField(default=0)
    is_pinned = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_pinned", "-priority", "-created_at"]
        verbose_name = verbose_name_plural = "公告"

    def __str__(self):
        return self.title


class CompetitionPhase(models.Model):
    KIND_CHOICES = [
        ("display", "仅展示"),
        ("song_selection", "歌曲上传与抽选"),
        ("submission", "谱面投稿"),
        ("review", "评分"),
    ]
    name = models.CharField(max_length=100)
    phase_key = models.CharField(max_length=50, unique=True)
    kind = models.CharField(max_length=30, choices=KIND_CHOICES, default="display")
    description = models.TextField(blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(
        default=True, verbose_name="启用", help_text="开关不随时间自动修改"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "start_time"]
        verbose_name = verbose_name_plural = "比赛阶段"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_time__gt=models.F("start_time")),
                name="phase_positive_duration",
            )
        ]

    @property
    def status(self):
        now = timezone.now()
        if now < self.start_time:
            return "upcoming"
        return "active" if now < self.end_time else "ended"

    @property
    def progress_percent(self):
        duration = (self.end_time - self.start_time).total_seconds()
        if duration <= 0:
            return 0
        return max(
            0,
            min(
                100,
                int(
                    100 * (timezone.now() - self.start_time).total_seconds() / duration
                ),
            ),
        )

    @property
    def time_remaining(self):
        if self.status == "ended":
            return "已结束"
        remaining = (
            self.start_time if self.status == "upcoming" else self.end_time
        ) - timezone.now()
        return f"{max(0, remaining.days)} 天 {max(0, remaining.seconds // 3600)} 小时"

    def __str__(self):
        return self.name


class ContestSettings(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    submissions_open = models.BooleanField(default=True, verbose_name="允许投稿")
    reviews_open = models.BooleanField(default=True, verbose_name="允许评分")
    reviews_per_chart = models.PositiveIntegerField(
        default=8, validators=[MinValueValidator(1)], verbose_name="每谱目标评分数"
    )
    max_score = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=50,
        validators=[MinValueValidator(Decimal("0.25"))],
        verbose_name="满分",
    )
    max_favorites = models.PositiveIntegerField(
        default=3, verbose_name="每人真爱票上限"
    )

    class Meta:
        verbose_name = verbose_name_plural = "比赛配置"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(id=1), name="one_contest_settings"
            )
        ]

    @classmethod
    def current(cls):
        return cls.objects.get_or_create(pk=1)[0]

    def __str__(self):
        return "比赛配置"


class Song(models.Model):
    id = models.AutoField(primary_key=True)
    unique_key = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="songs"
    )
    phase = models.ForeignKey(
        CompetitionPhase,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="songs",
    )
    title = models.CharField(max_length=100)
    audio_file = models.FileField(upload_to=get_audio_filename)
    cover_image = models.ImageField(upload_to=get_cover_filename, null=True, blank=True)
    background_video = models.FileField(
        upload_to=get_video_filename, null=True, blank=True
    )
    netease_url = models.URLField(null=True, blank=True)
    audio_hash = models.CharField(max_length=64, db_index=True)
    file_size = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        verbose_name = verbose_name_plural = "歌曲素材"

    def __str__(self):
        return self.title


class Chart(models.Model):
    STATUS_CHOICES = [("submitted", "已投稿"), ("archived", "历史归档")]
    SYNC_CHOICES = [
        ("pending", "待同步"),
        ("syncing", "同步中"),
        ("synced", "已同步"),
        ("failed", "同步失败"),
        ("unknown", "需核对远端结果"),
        ("disabled", "未启用同步"),
    ]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="charts"
    )
    # Historical shared authorship is retained without any two-stage workflow.
    contributors = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="contributed_charts"
    )
    source_song = models.ForeignKey(
        Song, null=True, blank=True, on_delete=models.SET_NULL, related_name="charts"
    )
    title = models.CharField(max_length=200, default="")
    designer = models.CharField(max_length=100, default="未填写")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="submitted"
    )
    audio_file = models.FileField(
        upload_to=get_chart_audio_filename, null=True, blank=True
    )
    cover_image = models.ImageField(
        upload_to=get_chart_cover_filename, null=True, blank=True
    )
    background_video = models.FileField(
        upload_to=get_chart_video_filename, null=True, blank=True
    )
    chart_file = models.FileField(upload_to=get_chart_filename, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    submission_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    net_sync_status = models.CharField(
        max_length=16, choices=SYNC_CHOICES, default="pending"
    )
    net_sync_error = models.TextField(blank=True)
    net_url = models.URLField(blank=True, max_length=1000)
    net_response = models.JSONField(default=dict, blank=True)
    net_synced_at = models.DateTimeField(null=True, blank=True)
    legacy_metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = verbose_name_plural = "谱面"

    def __str__(self):
        return f"{self.title} — {self.designer}"


class PeerReviewAllocation(models.Model):
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assigned_peer_reviews",
    )
    chart = models.ForeignKey(
        Chart, on_delete=models.CASCADE, related_name="review_allocations"
    )
    allocated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["allocated_at"]
        unique_together = ("reviewer", "chart")
        verbose_name = verbose_name_plural = "评分任务"

    def __str__(self):
        return f"{self.reviewer} → {self.chart}"


class PeerReview(models.Model):
    allocation = models.OneToOneField(
        PeerReviewAllocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="review",
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="given_peer_reviews",
    )
    chart = models.ForeignKey(Chart, on_delete=models.CASCADE, related_name="reviews")
    score = models.DecimalField(
        max_digits=7, decimal_places=2, validators=[MinValueValidator(0)]
    )
    comment = models.TextField(blank=True, default="")
    favorite = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = verbose_name_plural = "评分记录"
        constraints = [
            models.UniqueConstraint(
                fields=["reviewer", "chart"], name="one_review_per_person_chart"
            )
        ]


class SongDraw(models.Model):
    phase = models.OneToOneField(
        CompetitionPhase, on_delete=models.PROTECT, related_name="draw"
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = verbose_name_plural = "歌曲抽选"

    def __str__(self):
        return self.phase.name


class SongDrawEntry(models.Model):
    draw = models.ForeignKey(SongDraw, on_delete=models.CASCADE, related_name="entries")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    song = models.ForeignKey(Song, on_delete=models.PROTECT, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["draw", "user"], name="one_draw_entry_per_person"
            )
        ]


class LegacyRecord(models.Model):
    kind = models.CharField(max_length=60)
    original_id = models.PositiveIntegerField()
    data = models.JSONField()

    class Meta:
        verbose_name = verbose_name_plural = "旧业务归档"
        constraints = [
            models.UniqueConstraint(
                fields=["kind", "original_id"], name="unique_legacy_record"
            )
        ]
