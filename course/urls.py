from django.urls import path
from course.views import Index

urlpatterns = [
    path('', Index.as_view())
]
