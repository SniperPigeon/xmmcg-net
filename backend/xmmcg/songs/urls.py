from django.urls import path
from . import views, chart_views, song_views, review_views

urlpatterns = [
    path("contest/status/", views.get_status),
    path("contest/phases/", views.get_phases),
    path("contest/banners/", views.get_banners),
    path("contest/announcements/", views.get_announcements),
    path("charts/", chart_views.charts_root),
    path("charts/me/", chart_views.my_charts),
    path("charts/<int:chart_id>/", chart_views.chart_detail),
    path("charts/<int:chart_id>/bundle/", chart_views.download_bundle),
    path("charts/<int:chart_id>/sync/", chart_views.retry_sync),
    path("songs/", song_views.songs_root),
    path("songs/draw/join/", song_views.join),
    path("songs/draw/me/", song_views.my_draws),
    path("songs/draw/<int:phase_id>/", song_views.draw),
    path("reviews/tasks/", review_views.tasks),
    path("reviews/available/", review_views.available),
    path("reviews/submit/", review_views.submit),
    path("reviews/allocate/", review_views.allocate),
    path("reviews/export/", review_views.export),
]
