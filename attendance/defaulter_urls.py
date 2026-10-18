"""Defaulter list URLs, included under /reports/ in sas/urls.py."""
from django.urls import path

from . import defaulter_views as views

urlpatterns = [
    path('defaulters/', views.defaulter_list, name='defaulters'),
    path('defaulters.pdf', views.defaulter_list_download, name='defaulters-pdf'),
    path('letters.pdf', views.warning_letters, name='defaulters-letters'),
    path('letters/<int:student_id>.pdf', views.warning_letter, name='defaulter-letter'),
]
