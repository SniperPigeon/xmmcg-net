from django.contrib import admin
from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "main_account", "qqid", "preferred_name")
    search_fields = ("user__username", "preferred_name")
    readonly_fields = ("created_at", "updated_at")

    def has_add_permission(self, request):
        return False
