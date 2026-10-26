from django.contrib import admin
from django.urls import include, path
from .static_views import static_asset

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/users/", include("users.urls")),
    path("api/", include("songs.urls")),
    path("static/<path:name>", static_asset),
]
