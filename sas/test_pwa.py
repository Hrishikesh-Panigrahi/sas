"""Tests for the installable app: manifest, service worker, offline page, partials."""
import json
import struct

from django.contrib.staticfiles import finders
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase, override_settings
from django.urls import include, path, reverse

from sas import pwa
from users.models import User

# The site's URLs plus this feature's, so the tests pass whether or not
# sas/urls.py includes sas.pwa_urls yet.
urlpatterns = [
    path('', include('sas.pwa_urls')),
    path('', include('sas.urls')),
]


@override_settings(ROOT_URLCONF='sas.test_pwa')
class PwaTests(TestCase):
    def test_manifest(self):
        r = self.client.get('/manifest.webmanifest')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/manifest+json')
        data = json.loads(r.content.decode('utf-8'))
        self.assertEqual(data['name'], 'SAS Student Attendance')
        self.assertEqual(data['short_name'], 'SAS')
        self.assertEqual(data['start_url'], '/dashboard/')
        self.assertEqual(data['scope'], '/')
        self.assertEqual(data['display'], 'standalone')
        self.assertEqual(data['theme_color'], '#2a5bd7')
        self.assertEqual(data['background_color'], '#f4f6fb')
        icons = {(i['sizes'], i.get('purpose', 'any')): i for i in data['icons']}
        self.assertIn(('192x192', 'any'), icons)
        self.assertIn(('512x512', 'any'), icons)
        self.assertIn(('512x512', 'maskable'), icons)
        for icon in data['icons']:
            self.assertEqual(icon['type'], 'image/png')
            self.assertTrue(icon['src'].startswith('/static/img/icon-'), icon['src'])

    def test_icon_files_are_real_pngs_of_the_declared_size(self):
        for name, size in (('icon-192.png', 192), ('icon-512.png', 512), ('icon-maskable-512.png', 512)):
            found = finders.find('img/' + name)
            self.assertTrue(found, name)
            with open(found, 'rb') as fh:
                head = fh.read(24)
            self.assertEqual(head[:8], b'\x89PNG\r\n\x1a\n')
            self.assertEqual(struct.unpack('>II', head[16:24]), (size, size))

    def test_service_worker(self):
        r = self.client.get('/sw.js')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/javascript')
        self.assertEqual(r['Service-Worker-Allowed'], '/')
        self.assertEqual(r['Cache-Control'], 'no-cache')
        body = r.content.decode('utf-8')
        first_line, rest = body.split('\n', 1)
        self.assertTrue(first_line.startswith('self.__SAS__ = '))
        config = json.loads(first_line[len('self.__SAS__ = '):].rstrip(';'))
        self.assertEqual(config['staticUrl'], '/static/')
        self.assertEqual(config['offlineUrl'], '/offline/')
        self.assertEqual(config['logoutUrl'], reverse('logout'))
        self.assertRegex(config['version'], r'^[0-9a-f]{12}$')
        self.assertFalse(config['disabled'])
        self.assertIn("addEventListener('fetch'", rest)
        # The version is stable while files are unchanged.
        self.assertEqual(pwa.asset_version(), config['version'])

    def test_service_worker_revalidates_with_etag(self):
        etag = self.client.get('/sw.js')['ETag']
        r = self.client.get('/sw.js', HTTP_IF_NONE_MATCH=etag)
        self.assertEqual(r.status_code, 304)
        self.assertEqual(r['Service-Worker-Allowed'], '/')

    def test_service_worker_kill_switch(self):
        with self.settings(PWA_DISABLED=True):
            body = self.client.get('/sw.js').content.decode('utf-8')
        self.assertIn('"disabled": true', body.split('\n', 1)[0])

    def test_offline_page(self):
        r = self.client.get('/offline/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "You're offline")
        self.assertContains(r, "Attendance you save while offline is kept on this device and sent when you're back online.")
        self.assertContains(r, 'Retry')
        self.assertContains(r, 'rel="manifest"')
        self.assertContains(r, 'data-sync="off"')

    def test_head_partial(self):
        html = render_to_string('partials/pwa_head.html')
        self.assertIn('<link rel="manifest" href="/manifest.webmanifest">', html)
        self.assertIn('<meta name="theme-color" content="#2a5bd7">', html)
        self.assertIn('rel="apple-touch-icon"', html)
        self.assertIn('apple-mobile-web-app-capable', html)

    def test_scripts_partial(self):
        user = User.objects.create_user('t@x.test', 'correct-horse-battery', is_staff=True)
        request = RequestFactory().get('/dashboard/')
        request.user = user
        html = render_to_string('partials/pwa_scripts.html', {'user': user}, request=request)
        self.assertIn("navigator.serviceWorker.register('/sw.js', { scope: '/' })", html)
        self.assertIn('src="/static/js/offline.js"', html)
        self.assertIn('data-ping-url="/manifest.webmanifest"', html)
        self.assertIn('data-login-url="%s"' % reverse('Login'), html)
        self.assertIn('data-user="%d"' % user.pk, html)

    def test_scripts_partial_signed_out(self):
        from django.contrib.auth.models import AnonymousUser
        html = render_to_string('partials/pwa_scripts.html', {'user': AnonymousUser()})
        self.assertIn('data-user=""', html)

    @override_settings(ROOT_URLCONF='sas.urls')
    def test_partials_render_without_the_urls_wired(self):
        # Before sas.pwa_urls is included the partials must not break pages.
        try:
            reverse('pwa-sw')
        except Exception:
            html = render_to_string('partials/pwa_head.html') + render_to_string('partials/pwa_scripts.html')
            self.assertNotIn('rel="manifest"', html)
            self.assertNotIn('serviceWorker.register', html)
            self.assertIn('offline.js', html)
