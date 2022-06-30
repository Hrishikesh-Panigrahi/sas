from django.urls import path
from . import views

urlpatterns = [
    path('', views.loginUser, name='Login'),
    path('logout', views.logoutUser, name='logout'),
]
