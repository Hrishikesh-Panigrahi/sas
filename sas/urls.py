
from django.contrib import admin
from django.urls import path, include
from sas.views import index
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('dashboard/', index, name='index'),
    path('', include('Login.urls')),
    path('users/', include('users.urls')),
    path('course/', include('course.urls')),
    path('student/', include('student.urls')),
    path('/', include('attendance.urls')),
    path('timetable/', include('timetable.urls')),
    path('class/', include('cls.urls')),
]

urlpatterns += static(settings.STATIC_URL, document_root = settings.STATIC_ROOT)