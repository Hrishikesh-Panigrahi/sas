/* SAS service worker.
 *
 * Served at /sw.js by sas.pwa.service_worker, which prepends
 *   self.__SAS__ = {version, staticUrl, offlineUrl, logoutUrl, disabled};
 * The version is a hash of the app's static files, so a deploy that changes
 * them installs a new worker and drops the old static cache.
 *
 * Strategies:
 * - /static/ files: cache first (core files precached on install).
 * - Page navigations (GET, same origin): network first; the latest copy of
 *   each page is kept so it opens offline, otherwise the offline page.
 * - Google Fonts: stale-while-revalidate.
 * - Everything else, including every POST and other cross-origin requests,
 *   goes straight to the network and is never cached.
 */
(function () {
  'use strict';

  var CONFIG = self.__SAS__ || {};
  var VERSION = CONFIG.version || 'dev';
  var ORIGIN = self.location.origin;
  var STATIC_URL = new URL(CONFIG.staticUrl || '/static/', ORIGIN).href;
  var OFFLINE_URL = new URL(CONFIG.offlineUrl || '/offline/', ORIGIN).href;
  var LOGOUT_PATH = new URL(CONFIG.logoutUrl || '/logout', ORIGIN).pathname;

  var STATIC_CACHE = 'sas-static-' + VERSION;
  var PAGES_CACHE = 'sas-pages';
  var FONTS_CACHE = 'sas-fonts';
  var CURRENT = [STATIC_CACHE, PAGES_CACHE, FONTS_CACHE];
  var MAX_PAGES = 60;

  var PRECACHE = [
    'css/app.css',
    'js/app.js',
    'js/offline.js',
    'vendor/jquery/jquery.min.js',
    'vendor/bootstrap/bootstrap.min.css',
    'vendor/bootstrap/js/bootstrap.bundle.min.js',
    'vendor/datatables/dataTables.bootstrap4.min.css',
    'vendor/datatables/jquery.dataTables.min.js',
    'vendor/datatables/dataTables.bootstrap4.min.js',
    'vendor/fontawesome-free/css/all.min.css',
    'vendor/fontawesome-free/webfonts/fa-solid-900.woff2',
    'vendor/fontawesome-free/webfonts/fa-regular-400.woff2',
    'vendor/fontawesome-free/webfonts/fa-brands-400.woff2',
    'img/favicon.svg',
    'img/icon-192.png',
    'img/icon-512.png',
    'img/icon-maskable-512.png'
  ].map(function (path) { return STATIC_URL + path; });

  function cacheOfflinePage(cache) {
    // Fetched without cookies: the offline page is the same for everyone.
    return fetch(new Request(OFFLINE_URL, { cache: 'reload', credentials: 'omit' })).then(function (response) {
      if (!response.ok) throw new Error('Offline page returned ' + response.status);
      return cache.put(OFFLINE_URL, response);
    });
  }

  self.addEventListener('install', function (event) {
    if (CONFIG.disabled) {
      self.skipWaiting();
      return;
    }
    event.waitUntil(Promise.all([
      caches.open(STATIC_CACHE).then(function (cache) {
        return Promise.all(PRECACHE.map(function (url) {
          return fetch(new Request(url, { cache: 'reload' })).then(function (response) {
            if (response.ok) return cache.put(url, response);
          }).catch(function () { /* one missing file shouldn't stop the install */ });
        }));
      }),
      caches.open(PAGES_CACHE).then(cacheOfflinePage)
    ]).then(function () {
      return self.skipWaiting();
    }));
  });

  self.addEventListener('activate', function (event) {
    event.waitUntil(caches.keys().then(function (names) {
      return Promise.all(names.filter(function (name) {
        return name.indexOf('sas-') === 0 && (CONFIG.disabled || CURRENT.indexOf(name) === -1);
      }).map(function (name) {
        return caches.delete(name);
      }));
    }).then(function () {
      if (CONFIG.disabled) return self.registration.unregister();
      return self.clients.claim();
    }));
  });

  self.addEventListener('fetch', function (event) {
    if (CONFIG.disabled) return;
    var request = event.request;
    // A DevTools quirk: these requests can't be answered by a worker.
    if (request.cache === 'only-if-cached' && request.mode !== 'same-origin') return;
    var url = new URL(request.url);

    if (request.method !== 'GET') {
      // Signing out: forget the pages kept for offline use, so whoever uses
      // this device next can't read them.
      if (request.method === 'POST' && url.origin === ORIGIN && url.pathname === LOGOUT_PATH) {
        event.waitUntil(forgetPages());
      }
      return;
    }

    if (request.url.indexOf(STATIC_URL) === 0) {
      event.respondWith(cacheFirst(request));
      return;
    }
    if (url.origin === ORIGIN) {
      if (request.mode === 'navigate') event.respondWith(networkFirst(event));
      return;
    }
    if (url.hostname === 'fonts.googleapis.com' || url.hostname === 'fonts.gstatic.com') {
      event.respondWith(staleWhileRevalidate(event, FONTS_CACHE));
    }
  });

  function cacheFirst(request) {
    return caches.open(STATIC_CACHE).then(function (cache) {
      return cache.match(request, { ignoreVary: true }).then(function (hit) {
        if (hit) return hit;
        return fetch(request).then(function (response) {
          if (response.ok) cache.put(request, response.clone()).catch(function () {});
          return response;
        });
      });
    });
  }

  function isCacheablePage(response) {
    if (!response || !response.ok || response.type !== 'basic') return false;
    var type = response.headers.get('Content-Type') || '';
    var control = response.headers.get('Cache-Control') || '';
    return type.indexOf('text/html') !== -1 && control.indexOf('no-store') === -1;
  }

  function networkFirst(event) {
    var request = event.request;
    return fetch(request).then(function (response) {
      if (isCacheablePage(response)) {
        var copy = response.clone();
        event.waitUntil(caches.open(PAGES_CACHE).then(function (cache) {
          return cache.put(request, copy).then(function () { return trimPages(cache); });
        }).catch(function () {}));
      }
      return response;
    }).catch(function () {
      return caches.open(PAGES_CACHE).then(function (cache) {
        return cache.match(request, { ignoreVary: true }).then(function (hit) {
          return hit || cache.match(OFFLINE_URL);
        });
      }).then(function (hit) {
        return hit || new Response(
          '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">' +
          '<title>Offline</title><p style="font-family:system-ui;padding:2rem">You\'re offline. Reconnect and try again.</p>',
          { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } });
      });
    });
  }

  function trimPages(cache) {
    return cache.keys().then(function (keys) {
      var extra = keys.filter(function (key) { return key.url !== OFFLINE_URL; });
      extra = extra.slice(0, Math.max(0, extra.length - MAX_PAGES));
      return Promise.all(extra.map(function (key) { return cache.delete(key); }));
    });
  }

  function forgetPages() {
    return caches.delete(PAGES_CACHE).then(function () {
      return caches.open(PAGES_CACHE);
    }).then(cacheOfflinePage).catch(function () {});
  }

  function staleWhileRevalidate(event, cacheName) {
    var request = event.request;
    return caches.open(cacheName).then(function (cache) {
      return cache.match(request).then(function (hit) {
        var network = fetch(request).then(function (response) {
          // Stylesheets from fonts.googleapis.com arrive opaque (no CORS).
          if (response.ok || response.type === 'opaque') {
            return cache.put(request, response.clone()).then(function () { return response; });
          }
          return response;
        });
        if (hit) {
          event.waitUntil(network.catch(function () {}));
          return hit;
        }
        return network.catch(function () { return Response.error(); });
      });
    });
  }
})();
