"""
Dashboard App URLs Configuration

Handles routing for dashboard views including:
- Main dashboard with customer integration
- Quick actions for customer management
- Dashboard statistics API
"""

from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    # Main dashboard view with customer integration
    path("", views.dashboard_view, name="main"),
    # Dashboard quick actions for customer management
    path("quick-action/", views.dashboard_quick_action, name="quick_action"),
    # API endpoint for dashboard statistics
    path("api/stats/", views.dashboard_stats_api, name="stats_api"),
]
