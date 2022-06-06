from django.urls import path
from . import views


urlpatterns = [
    path('Sign-Up', views.register, name='register'),

]