from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='timetable'),
    path('class/<int:cls_id>/', views.class_timetable, name='timetable-class'),
    path('class/<int:cls_id>/generate/', views.generator, name='timetable-generator'),
    path('class/<int:cls_id>/generate/run', views.generator_run, name='timetable-generator-run'),
    path('class/<int:cls_id>/generate/assist', views.generator_assist, name='timetable-generator-assist'),
    path('class/<int:cls_id>/generate/apply', views.generator_apply, name='timetable-generator-apply'),
    path('slot/<int:id>/delete', views.delete_slot, name='timetable-slot-delete'),
]
