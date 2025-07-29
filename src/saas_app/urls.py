from django.contrib import admin
from django.urls import path, include

from .views import home_page_view
from .views import about_page_view
from auth.views import login_view, register_view

urlpatterns = [
    path("", home_page_view, name="home"),
    path("about/", about_page_view, name="about"),
    path("login/", login_view, name="login"),
    path("register/", register_view, name="register"),
    path("accounts/", include("allauth.urls")),
    path("admin/", admin.site.urls),
]
