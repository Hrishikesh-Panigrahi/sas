"""Installable-app URLs. Included at the site root: the service worker must be
served from / to control every page."""
from django.urls import path

from . import pwa

urlpatterns = [
    path('manifest.webmanifest', pwa.manifest, name='pwa-manifest'),
    path('sw.js', pwa.service_worker, name='pwa-sw'),
    path('offline/', pwa.offline, name='pwa-offline'),
]
