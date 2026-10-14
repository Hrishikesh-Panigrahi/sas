from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='timetable'),
    path('class/<int:cls_id>/', views.class_timetable, name='timetable-class'),
    path('slot/<int:id>/delete', views.delete_slot, name='timetable-slot-delete'),
]
