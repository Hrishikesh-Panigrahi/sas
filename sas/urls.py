
from django.contrib import admin
from django.urls import path, include
from sas.views import index

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', index),
    path('users/', include('users.urls')),
    path('course/', include('course.urls')),
    path('student/', include('student.urls')),
]
