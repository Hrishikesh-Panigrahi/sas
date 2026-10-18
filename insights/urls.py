from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='insights'),
    path('analysis', views.analysis, name='insights-analysis'),
    path('ask/', views.ask, name='ask'),
]
