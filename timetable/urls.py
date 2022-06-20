from django.urls import path
from . import views

urlpatterns = [
    path('CreateTimeTable', views.createTT, name='createTimeTable'),
    path('UpdateTimeTable', views.updateTT, name='updateTimeTable'),
]
