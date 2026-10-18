from django.urls import path
from . import checkin, views

urlpatterns = [
    path('attendance/', views.home, name='attendance-home'),
    path('attendance/class/<int:assign_id>/', views.lectures, name='attendance-attendance_date'),
    path('attendance/class/<int:assign_id>/create/Lecture', views.create_lecture, name='create_lecture'),
    path('attendance/class/<int:assign_id>/report', views.report, name='attendance-report'),
    path('attendance/slot/<int:slot_id>/start', views.start_from_slot, name='attendance-start'),
    path('attendance/<int:attendancecls_id>/', views.mark, name='attendance'),
    path('attendance/<int:attendancecls_id>/delete', views.delete_lecture, name='attendance-lecture-delete'),
    path('editattendance/<int:attendancecls_id>', views.mark, name='edit-attendance'),
    path('attendance/<int:lecture_id>/checkin/start', checkin.start, name='checkin-start'),
    path('attendance/<int:lecture_id>/checkin/', checkin.live, name='checkin-live'),
    path('attendance/<int:lecture_id>/checkin/state', checkin.state, name='checkin-state'),
    path('attendance/<int:lecture_id>/checkin/finish', checkin.finish, name='checkin-finish'),
    path('c/<int:session_id>/<str:token>', checkin.scan, name='checkin-scan'),
    path('checkin/', checkin.code, name='checkin-code'),
]
