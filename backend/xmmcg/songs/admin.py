from django.contrib import admin, messages
from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path
from .models import (
    Announcement,
    Banner,
    Chart,
    CompetitionPhase,
    ContestSettings,
    LegacyRecord,
    PeerReview,
    PeerReviewAllocation,
    Song,
    SongDraw,
    SongDrawEntry,
)
from .reviews import allocate_reviews
from .draws import run_draw
from .exports import export_peer_review_scores
from .majdata_service import sync_chart


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "is_active", "is_pinned", "priority")
    list_editable = ("is_active", "is_pinned", "priority")


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ("title", "is_active", "priority")
    list_editable = ("is_active", "priority")


@admin.register(CompetitionPhase)
class PhaseAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "start_time", "end_time", "is_active", "status")
    list_filter = ("kind", "is_active")
    actions = ["draw_songs"]

    @admin.action(description="执行歌曲抽选（每阶段仅一次）")
    def draw_songs(self, request, queryset):
        for phase in queryset:
            try:
                draw = run_draw(phase.pk)
                self.message_user(
                    request, f"{phase.name}：已抽选 {draw.entries.count()} 位参与者"
                )
            except Exception as error:
                self.message_user(request, str(error), level=messages.ERROR)


@admin.register(ContestSettings)
class SettingsAdmin(admin.ModelAdmin):
    change_form_template = "admin/contest_settings.html"

    def has_add_permission(self, request):
        return not ContestSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def get_urls(self):
        return [
            path(
                "allocate/",
                self.admin_site.admin_view(self.allocate),
                name="contest_allocate",
            )
        ] + super().get_urls()

    def allocate(self, request):
        if not self.has_change_permission(request):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied
        if request.method == "POST":
            try:
                result = allocate_reviews(commit=True)
                self.message_user(
                    request,
                    f"新增 {result['new_tasks']} 个评分任务；{len(result['shortfalls'])} 张谱面存在缺额",
                )
            except Exception as error:
                self.message_user(request, str(error), level=messages.ERROR)
            return redirect("admin:songs_contestsettings_changelist")
        try:
            preview = allocate_reviews()
        except Exception as error:
            preview = {"error": str(error)}
        return TemplateResponse(
            request,
            "admin/allocation_preview.html",
            {
                **self.admin_site.each_context(request),
                "title": "评分任务分配预览",
                "preview": preview,
            },
        )


@admin.register(Chart)
class ChartAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "designer", "user", "status", "net_sync_status")
    list_filter = ("status", "net_sync_status")
    search_fields = ("title", "designer", "user__username")
    readonly_fields = (
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
    actions = ["retry_net", "export_scores"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="重试失败的 Net 同步")
    def retry_net(self, request, queryset):
        for chart in queryset:
            sync_chart(chart)
            self.message_user(
                request, f"{chart.title}：{chart.get_net_sync_status_display()}"
            )

    @admin.action(description="导出评分与评语")
    def export_scores(self, request, queryset):
        response = HttpResponse(
            export_peer_review_scores(queryset.values_list("id", flat=True)),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="scores.xlsx"'
        return response


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Song)
class SongAdmin(ReadOnlyAdmin):
    list_display = ("id", "title", "user", "phase")


@admin.register(PeerReview)
class ReviewAdmin(ReadOnlyAdmin):
    list_display = ("reviewer", "chart", "score", "favorite", "created_at")


@admin.register(PeerReviewAllocation)
class AllocationAdmin(ReadOnlyAdmin):
    list_display = ("reviewer", "chart", "allocated_at")


@admin.register(LegacyRecord)
class LegacyAdmin(ReadOnlyAdmin):
    list_display = ("kind", "original_id")
    list_filter = ("kind",)


admin.site.register(SongDraw, ReadOnlyAdmin)
admin.site.register(SongDrawEntry, ReadOnlyAdmin)
