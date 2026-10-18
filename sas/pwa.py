"""Installable-app (PWA) support: web app manifest, service worker and offline page.

The service worker source lives in static/js/sw.js but must be served from the
site root so it can control every page. `service_worker` serves it with a
small config prepended, including a version derived from the app's static
files, so each deploy that changes them installs a fresh worker and cache.
"""
import hashlib
import json
import os

from django.conf import settings
from django.contrib.staticfiles import finders
from django.http import Http404, HttpResponse, HttpResponseNotModified, JsonResponse
from django.shortcuts import render
from django.template.loader import get_template
from django.templatetags.static import static
from django.urls import NoReverseMatch, reverse
from django.views.decorators.http import require_safe

APP_NAME = 'SAS — Student Attendance'
SHORT_NAME = 'SAS'
THEME_COLOR = '#4f46e5'
BACKGROUND_COLOR = '#f4f6fb'
SW_SOURCE = 'js/sw.js'

# Static files whose changes should roll out a new service worker version:
# the app's own assets plus the minified vendor files and fonts it precaches.
_VERSIONED_DIRS = ('css/', 'js/', 'img/')
_VERSIONED_SUFFIXES = ('.min.css', '.min.js', '.woff2')


def _url(name, fallback):
    try:
        return reverse(name)
    except NoReverseMatch:
        return fallback


@require_safe
def manifest(request):
    data = {
        'id': '/dashboard/',
        'name': APP_NAME,
        'short_name': SHORT_NAME,
        'description': 'Take attendance, check timetables and follow attendance, even on a patchy connection.',
        'lang': 'en',
        'dir': 'ltr',
        'start_url': '/dashboard/',
        'scope': '/',
        'display': 'standalone',
        'orientation': 'any',
        'theme_color': THEME_COLOR,
        'background_color': BACKGROUND_COLOR,
        'categories': ['education', 'productivity'],
        'icons': [
            {'src': static('img/icon-192.png'), 'sizes': '192x192', 'type': 'image/png', 'purpose': 'any'},
            {'src': static('img/icon-512.png'), 'sizes': '512x512', 'type': 'image/png', 'purpose': 'any'},
            {'src': static('img/icon-maskable-512.png'), 'sizes': '512x512', 'type': 'image/png',
             'purpose': 'maskable'},
        ],
    }
    response = JsonResponse(data, content_type='application/manifest+json',
                            json_dumps_params={'ensure_ascii': False, 'indent': 2})
    response['Cache-Control'] = 'public, max-age=3600'
    return response


def _versioned_files():
    """(relative path, absolute path) of every static file that feeds the version."""
    found = []
    for finder in finders.get_finders():
        if not isinstance(finder, finders.FileSystemFinder):
            continue   # app static (e.g. admin) never reaches the service worker's precache
        for path, storage in finder.list(['*.map', 'scss', 'less', 'svgs', 'sprites', 'metadata']):
            rel = path.replace(os.sep, '/')
            if rel.startswith(_VERSIONED_DIRS) or rel.endswith(_VERSIONED_SUFFIXES):
                found.append((rel, storage.path(path)))
    try:
        found.append(('templates/offline.html', get_template('offline.html').origin.name))
    except Exception:   # noqa: BLE001 - the version still works without it
        pass
    return sorted(found)


_version = {'key': None, 'value': None}


def asset_version():
    """Short hash of the service worker and the static files it caches.

    Content-based, so every server instance of a deploy agrees on it. Outside
    DEBUG it is computed once per process (files only change with a deploy);
    with DEBUG, sizes and modification times are checked on every call and
    the files re-read when one of them changes.
    """
    if _version['value'] and not settings.DEBUG:
        return _version['value']
    files = _versioned_files()
    stats = []
    for rel, path in files:
        try:
            st = os.stat(path)
        except OSError:
            continue
        stats.append((rel, st.st_size, st.st_mtime_ns))
    key = tuple(stats)
    if _version['key'] != key:
        digest = hashlib.sha256()
        for rel, path in files:
            try:
                with open(path, 'rb') as fh:
                    content = fh.read()
            except OSError:
                continue
            digest.update(rel.encode() + b'\0' + content + b'\0')
        _version.update(key=key, value=digest.hexdigest()[:12])
    return _version['value']


def _sw_source():
    path = finders.find(SW_SOURCE)
    if not path:
        candidate = os.path.join(settings.STATIC_ROOT or '', SW_SOURCE)
        path = candidate if os.path.isfile(candidate) else None
    if not path:
        raise Http404('Service worker source not found.')
    with open(path, encoding='utf-8') as fh:
        return fh.read()


@require_safe
def service_worker(request):
    config = {
        'version': asset_version(),
        'staticUrl': settings.STATIC_URL,
        'offlineUrl': _url('pwa-offline', '/offline/'),
        'logoutUrl': _url('logout', '/logout'),
        # Set PWA_DISABLED = True to ship a worker that clears its caches and
        # unregisters itself (a kill switch if caching ever misbehaves).
        'disabled': bool(getattr(settings, 'PWA_DISABLED', False)),
    }
    body = 'self.__SAS__ = %s;\n%s' % (json.dumps(config, sort_keys=True), _sw_source())
    # Browsers re-check the worker on navigations; an ETag lets them do it with a 304.
    etag = '"%s"' % hashlib.sha256(body.encode('utf-8')).hexdigest()[:32]
    headers = {'ETag': etag, 'Service-Worker-Allowed': '/', 'Cache-Control': 'no-cache'}
    if etag in [tag.strip() for tag in request.headers.get('If-None-Match', '').split(',')]:
        response = HttpResponseNotModified()
    else:
        response = HttpResponse(body, content_type='application/javascript')
    for name, value in headers.items():
        response[name] = value
    return response


@require_safe
def offline(request):
    return render(request, 'offline.html', {
        'title': "You're offline",
        'dashboard_url': _url('index', '/dashboard/'),
    })
