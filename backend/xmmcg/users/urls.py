from django.urls import path
from . import views

urlpatterns = [
    path("csrf/", views.csrf_token_view),
    path("register/", views.register),
    path("accounts/", views.search_accounts),
    path("login/", views.login),
    path("logout/", views.logout),
    path("me/", views.get_current_user),
    path("profile/", views.update_profile),
    path("change-password/", views.change_password),
]
