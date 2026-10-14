from django.urls import path
from . import views

urlpatterns = [
    path('attendance/', views.home, name='attendance-home'),
    path('attendance/class/<int:assign_id>/', views.lectures, name='attendance-attendance_date'),
    path('attendance/class/<int:assign_id>/create/Lecture', views.create_lecture, name='create_lecture'),
    path('attendance/class/<int:assign_id>/report', views.report, name='attendance-report'),
    path('attendance/slot/<int:slot_id>/start', views.start_from_slot, name='attendance-start'),
    path('attendance/<int:attendancecls_id>/', views.mark, name='attendance'),
    path('attendance/<int:attendancecls_id>/delete', views.delete_lecture, name='attendance-lecture-delete'),
    path('editattendance/<int:attendancecls_id>', views.mark, name='edit-attendance'),
]
