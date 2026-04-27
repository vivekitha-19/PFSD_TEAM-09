"""
URL patterns for authentication – FarmAI v4

Changes:
  - analytics/ now redirects to profile/ (analytics are IN the profile page)
  - analytics/data/ now returns per-user data only (same as profile/data/)
  - All other routes unchanged
"""
from django.urls import path
from . import auth_views

urlpatterns = [
    # ── Auth pages & API ──────────────────────────────────────────
    path("login/",            auth_views.login_view,       name="login"),
    path("register/",         auth_views.register_api,     name="register"),
    path("logout/",           auth_views.logout_api,       name="logout"),
    path("me/",               auth_views.current_user_api, name="current_user"),

    # ── Profile (now includes analytics) ─────────────────────────
    path("profile/",          auth_views.profile_page,     name="profile"),
    path("profile/data/",     auth_views.profile_data_api, name="profile_data"),

    # ── Analytics (kept for backward compat → redirects to profile) ──
    path("analytics/",        auth_views.analytics_page,   name="analytics"),
    path("analytics/data/",   auth_views.analytics_data_api, name="analytics_data"),
]
