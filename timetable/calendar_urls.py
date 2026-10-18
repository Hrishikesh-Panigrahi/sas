"""Calendar subscription URLs, included at the site root."""
from django.urls import path

from . import calendar_views

urlpatterns = [
    path('calendar/', calendar_views.page, name='calendar'),
    path('calendar/<slug:token>.ics', calendar_views.feed, name='calendar-feed'),
]
