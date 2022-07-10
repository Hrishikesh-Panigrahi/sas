from django.urls import path
from . import views

urlpatterns = [
    path('CreateTimeTable', views.createTT, name='createTimeTable'),
    path('test', views.test_C),
    path('EditTimeTable', views.editTT, name='editTimeTable'),
    path('UpdateTimeTable', views.updateTT, name='updateTimeTable'),
    path('Requests', views.requests, name='requests'),
]
