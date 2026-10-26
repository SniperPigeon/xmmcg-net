from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path
from .models import (
    Announcement,
    Banner,
    Chart,
    CompetitionPhase,
    Competition,
    LegacyRecord,
    PeerReview,
    PeerReviewAllocation,
    Song,
    SongDraw,
    SongDrawEntry,
)
from .competitions import (
    CONFIG_FIELDS,
    activate_competition,
    archive_competition,
    copy_phases,
)
from .reviews import allocate_reviews
from .draws import run_draw
from .exports import export_peer_review_scores
from .majdata_service import sync_chart
from .bundles import BundleError, chart_bundle_response


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "is_active", "is_pinned", "priority")
    list_editable = ("is_active", "is_pinned", "priority")


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ("title", "is_active", "priority")
    list_editable = ("is_active", "priority")


class CompetitionForm(forms.ModelForm):
    copy_from = forms.ModelChoiceField(
        queryset=Competition.objects.all(),
        required=False,
        label="复制配置来源",
        help_text="仅新建时使用；选择后沿用该届的投稿开关、评分开关和评分参数。",
    )
    include_phases = forms.BooleanField(
        required=False,
        label="同时复制阶段模板",
        help_text="复制的阶段默认停用，请调整日期并启用。不会复制作品、抽选结果或评分。",
    )

    class Meta:
        model = Competition
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields.pop("copy_from", None)
            self.fields.pop("include_phases", None)

    def clean(self):
        data = super().clean()
        if data.get("include_phases") and not data.get("copy_from"):
            self.add_error("copy_from", "请先选择要复制的比赛")
        return data


@admin.register(Competition)
class CompetitionAdmin(admin.ModelAdmin):
    form = CompetitionForm
    change_form_template = "admin/competition.html"
    list_display = ("name", "status", "activated_at", "archived_at")
    list_filter = ("status",)
    search_fields = ("name",)
    readonly_fields = ("status", "created_at", "activated_at", "archived_at")

    def get_fields(self, request, obj=None):
        fields = (
            "name",
            "status",
            *CONFIG_FIELDS,
            "created_at",
            "activated_at",
            "archived_at",
        )
        return (
            fields if obj else ("name", "copy_from", "include_phases", *CONFIG_FIELDS)
        )

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return (
            obj is None or obj.status != "archived"
        ) and super().has_change_permission(request, obj)

    def save_model(self, request, obj, form, change):
        source = form.cleaned_data.get("copy_from") if not change else None
        if source:
            for field in CONFIG_FIELDS:
                setattr(obj, field, getattr(source, field))
        super().save_model(request, obj, form, change)
        if source and form.cleaned_data.get("include_phases"):
            copy_phases(source, obj)

    def get_urls(self):
        return [
            path(
                "<int:competition_id>/activate/",
                self.admin_site.admin_view(self.activate),
                name="competition_activate",
            ),
            path(
                "<int:competition_id>/archive/",
                self.admin_site.admin_view(self.archive),
                name="competition_archive",
            ),
            path(
                "<int:competition_id>/allocate/",
                self.admin_site.admin_view(self.allocate),
                name="competition_allocate",
            ),
            path(
                "<int:competition_id>/export/",
                self.admin_site.admin_view(self.export),
                name="competition_export",
            ),
        ] + super().get_urls()

    def lifecycle(self, request, competition_id, action):
        competition = get_object_or_404(Competition, pk=competition_id)
        if not self.has_change_permission(request, competition):
            raise PermissionDenied
        label, operation = (
            ("启用比赛", activate_competition)
            if action == "activate"
            else ("归档比赛", archive_competition)
        )
        if request.method == "POST":
            try:
                operation(competition.pk)
                self.message_user(request, f"{competition.name}：已{label[:2]}")
            except Exception as error:
                self.message_user(request, str(error), level=messages.ERROR)
            return redirect("admin:songs_competition_change", competition.pk)
        return TemplateResponse(
            request,
            "admin/competition_confirm.html",
            {
                **self.admin_site.each_context(request),
                "title": label,
                "competition": competition,
                "action": action,
                "charts_count": competition.charts.count(),
                "songs_count": competition.songs.count(),
                "reviews_count": PeerReview.objects.filter(
                    chart__competition=competition
                ).count(),
            },
        )

    def activate(self, request, competition_id):
        return self.lifecycle(request, competition_id, "activate")

    def archive(self, request, competition_id):
        return self.lifecycle(request, competition_id, "archive")

    def allocate(self, request, competition_id):
        competition = get_object_or_404(Competition, pk=competition_id)
        if not self.has_change_permission(request, competition):
            raise PermissionDenied
        if request.method == "POST":
            try:
                result = allocate_reviews(commit=True, competition_id=competition.pk)
                self.message_user(
                    request,
                    f"新增 {result['new_tasks']} 个评分任务；{len(result['shortfalls'])} 张谱面存在缺额",
                )
            except Exception as error:
                self.message_user(request, str(error), level=messages.ERROR)
            return redirect("admin:songs_competition_change", competition.pk)
        try:
            preview = allocate_reviews(competition_id=competition.pk)
        except Exception as error:
            preview = {"error": str(error)}
        return TemplateResponse(
            request,
            "admin/allocation_preview.html",
            {
                **self.admin_site.each_context(request),
                "title": f"{competition.name}：评分任务分配预览",
                "preview": preview,
            },
        )

    def export(self, request, competition_id):
        competition = get_object_or_404(Competition, pk=competition_id)
        if not self.has_view_permission(request, competition):
            raise PermissionDenied
        response = HttpResponse(
            export_peer_review_scores(competition=competition),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="scores-{competition.pk}.xlsx"'
        )
        return response


@admin.register(CompetitionPhase)
class PhaseAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "competition",
        "kind",
        "start_time",
        "end_time",
        "is_active",
        "status",
    )
    list_filter = ("competition", "kind", "is_active")
    actions = ["draw_songs"]

    def has_change_permission(self, request, obj=None):
        return (
            obj is None or obj.competition.status != "archived"
        ) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return (
            obj is None or obj.competition.status != "archived"
        ) and super().has_delete_permission(request, obj)

    @transaction.atomic
    def delete_queryset(self, request, queryset):
        if queryset.filter(competition__status="archived").exists():
            raise PermissionDenied("已归档比赛的阶段不能删除")
        super().delete_queryset(request, queryset)

    @transaction.atomic
    def delete_model(self, request, obj):
        if Competition.objects.filter(
            pk=obj.competition_id, status="archived"
        ).exists():
            raise PermissionDenied("已归档比赛的阶段不能删除")
        super().delete_model(request, obj)

    def get_readonly_fields(self, request, obj=None):
        return ("competition",) if obj else ()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "competition":
            kwargs["queryset"] = Competition.objects.exclude(status="archived")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.action(description="执行歌曲抽选（每阶段仅一次）", permissions=["change"])
    def draw_songs(self, request, queryset):
        for phase in queryset:
            try:
                draw = run_draw(phase.pk)
                self.message_user(
                    request, f"{phase.name}：已抽选 {draw.entries.count()} 位参与者"
                )
            except Exception as error:
                self.message_user(request, str(error), level=messages.ERROR)


@admin.register(Chart)
class ChartAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "competition",
        "designer",
        "user",
        "status",
        "net_sync_status",
    )
    list_filter = ("competition", "status", "net_sync_status")
    search_fields = ("title", "designer", "user__username")
    readonly_fields = (
        "guid",
        "competition",
        "user",
        "contributors",
        "title",
        "designer",
        "source_song",
        "audio_file",
        "cover_image",
        "background_video",
        "chart_file",
        "submission_key",
        "net_sync_status",
        "net_sync_error",
        "net_url",
        "net_response",
        "net_synced_at",
        "legacy_metadata",
        "created_at",
        "submitted_at",
    )
    actions = ["download_charts", "retry_net", "export_scores"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return (
            obj is None or obj.competition.status != "archived"
        ) and super().has_change_permission(request, obj)

    @admin.action(description="重试失败的 Net 同步", permissions=["change"])
    def retry_net(self, request, queryset):
        for chart in queryset:
            if chart.competition.status != "active":
                self.message_user(
                    request, f"{chart.title}：比赛未启用或已归档", level=messages.ERROR
                )
                continue
            sync_chart(chart)
            self.message_user(
                request, f"{chart.title}：{chart.get_net_sync_status_display()}"
            )

    @admin.action(description="导出评分与评语", permissions=["view"])
    def export_scores(self, request, queryset):
        response = HttpResponse(
            export_peer_review_scores(queryset.values_list("id", flat=True)),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="scores.xlsx"'
        return response

    @admin.action(description="批量下载所选谱面（ZIP）", permissions=["view"])
    def download_charts(self, request, queryset):
        try:
            return chart_bundle_response(
                queryset.order_by("id").iterator(), filename="charts.zip", batch=True
            )
        except BundleError as error:
            self.message_user(request, str(error), level=messages.ERROR)


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Song)
class SongAdmin(ReadOnlyAdmin):
    list_display = ("id", "title", "competition", "user", "phase")
    list_filter = ("competition",)


@admin.register(PeerReview)
class ReviewAdmin(ReadOnlyAdmin):
    list_filter = ("chart__competition",)
    list_display = ("reviewer", "chart", "score", "favorite", "created_at")


@admin.register(PeerReviewAllocation)
class AllocationAdmin(ReadOnlyAdmin):
    list_filter = ("chart__competition",)
    list_display = ("reviewer", "chart", "allocated_at")


@admin.register(LegacyRecord)
class LegacyAdmin(ReadOnlyAdmin):
    list_display = ("kind", "original_id")
    list_filter = ("kind",)


@admin.register(SongDraw)
class DrawAdmin(ReadOnlyAdmin):
    list_display = ("phase", "completed_at")
    list_filter = ("phase__competition",)


@admin.register(SongDrawEntry)
class DrawEntryAdmin(ReadOnlyAdmin):
    list_display = ("draw", "user", "song")
    list_filter = ("draw__phase__competition",)
