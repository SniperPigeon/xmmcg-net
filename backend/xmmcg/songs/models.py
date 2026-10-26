"""比赛数据模型：完整谱面独立于歌曲素材和抽选结果。"""

import uuid
from decimal import Decimal
from pathlib import PurePosixPath

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


def asset_key(instance, filename, category):
    return f"{category}/{uuid.uuid4().hex}/{PurePosixPath(filename).name}"


# 历史迁移引用了这些文件名函数，需要保留可导入的名称。
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
    # 仅用于执行初始迁移。
    return {"songs": True, "charts": True, "profile": True, "eval": True}


class Banner(models.Model):
    """首页轮换 Banner。"""

    title = models.CharField(
        max_length=100, verbose_name="标题", help_text="Banner 标题"
    )
    content = models.TextField(verbose_name="内容", help_text="Banner 描述内容")
    image_url = models.CharField(
        null=True,
        blank=True,
        verbose_name="背景图片地址",
        help_text="背景图片 URL（可选）",
    )
    link = models.URLField(
        null=True, blank=True, verbose_name="链接", help_text="点击跳转链接（可选）"
    )
    button_text = models.CharField(
        max_length=50, default="了解更多", verbose_name="按钮文本", help_text="按钮文本"
    )
    color = models.CharField(
        max_length=20, default="#409EFF", verbose_name="背景色", help_text="背景色"
    )
    priority = models.IntegerField(
        default=0, verbose_name="优先级", help_text="优先级，越大越靠前"
    )
    is_active = models.BooleanField(
        default=True, verbose_name="是否启用", help_text="是否启用"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        ordering = ["-priority", "-created_at"]
        verbose_name = verbose_name_plural = "Banner"

    def __str__(self):
        return self.title


class Announcement(models.Model):
    """首页公告。"""

    title = models.CharField(max_length=200, verbose_name="标题", help_text="公告标题")
    content = models.TextField(help_text="支持 Markdown", verbose_name="内容")
    category = models.CharField(
        max_length=20,
        default="news",
        choices=[("news", "新闻"), ("event", "活动"), ("notice", "通知")],
        verbose_name="分类",
        help_text="公告分类",
    )
    priority = models.IntegerField(
        default=0, verbose_name="优先级", help_text="优先级，越大越靠前"
    )
    is_pinned = models.BooleanField(
        default=False, verbose_name="是否置顶", help_text="是否置顶"
    )
    is_active = models.BooleanField(
        default=True, verbose_name="是否启用", help_text="是否启用"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        ordering = ["-is_pinned", "-priority", "-created_at"]
        verbose_name = verbose_name_plural = "公告"

    def __str__(self):
        return self.title


class CompetitionPhase(models.Model):
    """比赛阶段管理模型，用于日程展示及功能开放控制。"""

    KIND_CHOICES = [
        ("display", "仅展示"),
        ("song_selection", "歌曲上传与抽选"),
        ("submission", "谱面投稿"),
        ("review", "评分"),
    ]
    name = models.CharField(max_length=100, verbose_name="名称")
    phase_key = models.CharField(max_length=50, unique=True, verbose_name="阶段标识")
    kind = models.CharField(
        max_length=30, choices=KIND_CHOICES, default="display", verbose_name="类型"
    )
    description = models.TextField(
        blank=True, verbose_name="描述", help_text="阶段描述，显示在主页时间轴"
    )
    start_time = models.DateTimeField(verbose_name="开始时间", help_text="阶段开始时间")
    end_time = models.DateTimeField(verbose_name="结束时间", help_text="阶段结束时间")
    order = models.PositiveIntegerField(
        default=0, verbose_name="显示顺序", help_text="显示顺序（从小到大）"
    )
    is_active = models.BooleanField(
        default=True, verbose_name="启用", help_text="开关不随时间自动修改"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

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
    id = models.PositiveSmallIntegerField(
        primary_key=True, default=1, editable=False, verbose_name="ID"
    )
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
    """用户上传的歌曲素材。"""

    id = models.AutoField(primary_key=True, verbose_name="ID")
    unique_key = models.UUIDField(
        default=uuid.uuid4, editable=False, unique=True, verbose_name="唯一标识"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="songs",
        verbose_name="用户",
    )
    phase = models.ForeignKey(
        CompetitionPhase,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="songs",
        verbose_name="比赛阶段",
    )
    title = models.CharField(max_length=100, verbose_name="标题", help_text="歌曲标题")
    audio_file = models.FileField(
        upload_to=get_audio_filename, verbose_name="音频文件", help_text="音频文件"
    )
    cover_image = models.ImageField(
        upload_to=get_cover_filename,
        null=True,
        blank=True,
        verbose_name="封面图片",
        help_text="封面图片（可选）",
    )
    background_video = models.FileField(
        upload_to=get_video_filename,
        null=True,
        blank=True,
        verbose_name="背景视频",
        help_text="背景视频（bg.mp4或pv.mp4，最大20MB，可选）",
    )
    netease_url = models.URLField(
        null=True,
        blank=True,
        verbose_name="网易云音乐链接",
        help_text="网易云音乐链接（可选）",
    )
    audio_hash = models.CharField(
        max_length=64,
        db_index=True,
        verbose_name="音频哈希",
        help_text="音频文件 SHA256 hash，用于识别重复",
    )
    file_size = models.IntegerField(
        default=0, verbose_name="文件大小", help_text="音频文件大小（字节）"
    )
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="创建时间", help_text="创建时间"
    )
    updated_at = models.DateTimeField(
        auto_now=True, verbose_name="更新时间", help_text="最后更新时间"
    )

    class Meta:
        ordering = ["-id"]
        verbose_name = verbose_name_plural = "歌曲素材"

    def __str__(self):
        return self.title


class Chart(models.Model):
    """用户提交的完整谱面。"""

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
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="charts",
        verbose_name="用户",
        help_text="谱面创建者",
    )
    # 保留历史共同作者用于排除本人评分，不恢复两阶段创作流程。
    contributors = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="contributed_charts",
        verbose_name="共同作者",
    )
    source_song = models.ForeignKey(
        Song,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="charts",
        verbose_name="来源歌曲",
    )
    title = models.CharField(max_length=200, default="", verbose_name="标题")
    designer = models.CharField(
        max_length=100, default="未填写", verbose_name="谱师名义", help_text="谱师名义"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="submitted",
        verbose_name="状态",
        help_text="谱面状态",
    )
    audio_file = models.FileField(
        upload_to=get_chart_audio_filename,
        null=True,
        blank=True,
        verbose_name="音频文件",
        help_text="谱面对应音频文件",
    )
    cover_image = models.ImageField(
        upload_to=get_chart_cover_filename,
        null=True,
        blank=True,
        verbose_name="封面图片",
        help_text="谱面封面图片",
    )
    background_video = models.FileField(
        upload_to=get_chart_video_filename,
        null=True,
        blank=True,
        verbose_name="背景视频",
        help_text="谱面背景视频（可选）",
    )
    chart_file = models.FileField(
        upload_to=get_chart_filename,
        null=True,
        blank=True,
        verbose_name="谱面文件",
        help_text="谱面文件（maidata.txt）",
    )
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="创建时间", help_text="创建时间"
    )
    submitted_at = models.DateTimeField(
        null=True, blank=True, verbose_name="提交时间", help_text="提交时间"
    )
    submission_key = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False, verbose_name="投稿标识"
    )
    net_sync_status = models.CharField(
        max_length=16,
        choices=SYNC_CHOICES,
        default="pending",
        verbose_name="Net 同步状态",
    )
    net_sync_error = models.TextField(blank=True, verbose_name="Net 同步说明")
    net_url = models.URLField(blank=True, max_length=1000, verbose_name="Net 地址")
    net_response = models.JSONField(
        default=dict, blank=True, verbose_name="Net 返回结果"
    )
    net_synced_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Net 同步时间"
    )
    legacy_metadata = models.JSONField(
        default=dict, blank=True, verbose_name="历史信息"
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = verbose_name_plural = "谱面"

    def __str__(self):
        return f"{self.title} — {self.designer}"


class PeerReviewAllocation(models.Model):
    """互评任务分配。"""

    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assigned_peer_reviews",
        verbose_name="评分者",
        help_text="评分者",
    )
    chart = models.ForeignKey(
        Chart,
        on_delete=models.CASCADE,
        related_name="review_allocations",
        verbose_name="谱面",
        help_text="被评分的谱面",
    )
    allocated_at = models.DateTimeField(
        auto_now_add=True, verbose_name="分配时间", help_text="分配时间"
    )

    class Meta:
        ordering = ["allocated_at"]
        unique_together = ("reviewer", "chart")
        verbose_name = verbose_name_plural = "评分任务"

    def __str__(self):
        return f"{self.reviewer} → {self.chart}"


class PeerReview(models.Model):
    """互评打分记录。"""

    allocation = models.OneToOneField(
        PeerReviewAllocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="review",
        verbose_name="评分任务",
        help_text="对应的分配任务（系统分配的任务有allocation，额外评分没有）",
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="given_peer_reviews",
        verbose_name="评分者",
        help_text="评分者",
    )
    chart = models.ForeignKey(
        Chart,
        on_delete=models.CASCADE,
        related_name="reviews",
        verbose_name="谱面",
        help_text="被评分的谱面",
    )
    score = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name="评分",
        help_text="评分",
    )
    comment = models.TextField(
        blank=True, default="", verbose_name="评语", help_text="评论（可选）"
    )
    favorite = models.BooleanField(
        default=False, verbose_name="真爱票", help_text="是否标记为喜欢"
    )
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="创建时间", help_text="评分时间"
    )

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
        CompetitionPhase,
        on_delete=models.PROTECT,
        related_name="draw",
        verbose_name="比赛阶段",
    )
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="完成时间")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = verbose_name_plural = "歌曲抽选"

    def __str__(self):
        return self.phase.name


class SongDrawEntry(models.Model):
    draw = models.ForeignKey(
        SongDraw,
        on_delete=models.CASCADE,
        related_name="entries",
        verbose_name="歌曲抽选",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name="用户"
    )
    song = models.ForeignKey(
        Song, on_delete=models.PROTECT, null=True, blank=True, verbose_name="歌曲"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["draw", "user"], name="one_draw_entry_per_person"
            )
        ]


class LegacyRecord(models.Model):
    kind = models.CharField(max_length=60, verbose_name="类型")
    original_id = models.PositiveIntegerField(verbose_name="原记录ID")
    data = models.JSONField(verbose_name="归档数据")

    class Meta:
        verbose_name = verbose_name_plural = "旧业务归档"
        constraints = [
            models.UniqueConstraint(
                fields=["kind", "original_id"], name="unique_legacy_record"
            )
        ]
