from django.contrib import admin
from django.urls import path
from advisory import views

urlpatterns = [
    path('admin/', admin.site.urls),

    path('', views.register, name="register"),
    path('register/', views.register),

    path('login/', views.login_view, name="login"),

    path('home/', views.home, name="home"),

    path('logout/', views.logout_view, name="logout"),
]