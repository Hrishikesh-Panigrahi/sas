/* SAS - offline attendance.
 *
 * - On the marking form (form[data-mark-form]), a save made while offline, or
 *   when the server can't be reached, is kept on this device (IndexedDB, or
 *   localStorage where IndexedDB is unavailable) instead of being lost.
 * - Kept sheets are sent on every page load, when the browser comes back
 *   online, when the tab becomes visible and every 30 seconds while any wait.
 * - A small pill (bottom right) shows "Offline" and "N waiting to sync".
 *
 * Online saves are untouched: after a quick reachability check the form is
 * submitted normally. Vanilla JS, no dependencies.
 *
 * Script attributes (set by templates/partials/pwa_scripts.html):
 *   data-ping-url   a cheap same-origin URL used to check the server is reachable
 *   data-login-url  the sign-in page (a replay that lands there needs a new sign-in)
 *   data-user       the signed-in user's id ("" when signed out); sheets are only
 *                   sent for the user who saved them
 *   data-sync="off" show the queue but never send (the offline page)
 */
(function () {
  'use strict';

  var script = document.currentScript || document.querySelector('script[src*="offline.js"]');
  function attr(name, fallback) {
    var value = script && script.getAttribute(name);
    return value === null || value === undefined ? fallback : value;
  }

  var PING_URL = attr('data-ping-url', '/manifest.webmanifest');
  var LOGIN_PATH = new URL(attr('data-login-url', '/'), location.href).pathname;
  var USER = attr('data-user', null);            // null: unknown, '': signed out
  var CAN_SYNC = attr('data-sync', 'on') !== 'off';
  var DB_NAME = 'sas-offline';
  var STORE = 'outbox';
  var LS_KEY = 'sas-outbox';
  var PROBE_TIMEOUT = 8000;
  var RETRY_EVERY = 30000;

  // ---------- Storage: IndexedDB with a localStorage fallback ----------

  var outbox = (function () {
    var dbPromise = null;

    function openDb() {
      if (!dbPromise) {
        dbPromise = new Promise(function (resolve, reject) {
          var request;
          try {
            if (!window.indexedDB) throw new Error('IndexedDB unavailable');
            request = window.indexedDB.open(DB_NAME, 1);
          } catch (err) {
            reject(err);
            return;
          }
          request.onupgradeneeded = function () {
            var db = request.result;
            if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE, { keyPath: 'url' });
          };
          request.onsuccess = function () { resolve(request.result); };
          request.onerror = function () { reject(request.error); };
          request.onblocked = function () { reject(new Error('IndexedDB blocked')); };
        });
      }
      return dbPromise;
    }

    function run(mode, operation) {
      return openDb().then(function (db) {
        return new Promise(function (resolve, reject) {
          var tx = db.transaction(STORE, mode);
          var request = operation(tx.objectStore(STORE));
          tx.oncomplete = function () { resolve(request ? request.result : undefined); };
          tx.onerror = tx.onabort = function () { reject(tx.error); };
        });
      });
    }

    function lsRead() {
      try {
        var items = JSON.parse(window.localStorage.getItem(LS_KEY) || '[]');
        return Array.isArray(items) ? items : [];
      } catch (err) {
        return [];
      }
    }

    function lsWrite(items) {
      if (items.length) window.localStorage.setItem(LS_KEY, JSON.stringify(items));
      else window.localStorage.removeItem(LS_KEY);
    }

    function valid(item) {
      return item && typeof item.url === 'string' && typeof item.body === 'string';
    }

    return {
      all: function () {
        var fromLs = lsRead();
        return run('readonly', function (store) { return store.getAll(); })
          .catch(function () { return []; })
          .then(function (fromDb) {
            var byUrl = {};
            (fromDb || []).concat(fromLs).filter(valid).forEach(function (item) {
              var seen = byUrl[item.url];
              if (!seen || String(item.savedAt) > String(seen.savedAt)) byUrl[item.url] = item;
            });
            return Object.keys(byUrl).map(function (url) { return byUrl[url]; }).sort(function (a, b) {
              return String(a.savedAt).localeCompare(String(b.savedAt));
            });
          });
      },
      put: function (item) {
        return run('readwrite', function (store) { return store.put(item); }).then(function () {
          try { lsWrite(lsRead().filter(function (i) { return i.url !== item.url; })); } catch (err) { /* ignore */ }
        }, function () {
          var items = lsRead().filter(function (i) { return i.url !== item.url; });
          items.push(item);
          lsWrite(items);   // throws (rejecting the promise) if storage is full or blocked
        });
      },
      remove: function (url) {
        try {
          var items = lsRead();
          var rest = items.filter(function (i) { return i.url !== url; });
          if (rest.length !== items.length) lsWrite(rest);
        } catch (err) { /* ignore */ }
        return run('readwrite', function (store) { return store.delete(url); }).catch(function () {});
      }
    };
  })();

  function isMine(item) {
    // Sheets saved by someone else on this device wait for them to sign in.
    return !USER || !item.user || String(item.user) === USER;
  }

  function mine() {
    return outbox.all().then(function (items) { return items.filter(isMine); });
  }

  // ---------- Small helpers ----------

  function text(el) {
    return el ? el.textContent.replace(/\s+/g, ' ').trim() : '';
  }

  function plural(n, one, many) {
    return n + ' ' + (n === 1 ? one : many);
  }

  function label(item) {
    return item.subtitle || String(item.title || '').replace(/\s*\u00b7\s*SAS\s*$/, '') || 'a lecture';
  }

  function formUrl(form) {
    var url = new URL(form.getAttribute('action') || location.href, location.href);
    url.hash = '';
    return url.href;
  }

  function cookie(name) {
    var parts = document.cookie ? document.cookie.split(';') : [];
    for (var i = 0; i < parts.length; i++) {
      var pair = parts[i].trim();
      if (pair.indexOf(name + '=') === 0) return decodeURIComponent(pair.slice(name.length + 1));
    }
    return '';
  }

  function currentCsrfToken() {
    var input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    return cookie('csrftoken') || (input && input.value) || '';
  }

  // ---------- Status pills and toasts ----------

  var ui = null;

  function ensureUi() {
    if (ui) return ui;
    var style = document.createElement('style');
    style.textContent = [
      '.sas-dock{position:fixed;right:16px;bottom:16px;z-index:1080;display:flex;flex-direction:column;align-items:flex-end;gap:8px;max-width:calc(100vw - 32px);pointer-events:none;font-family:inherit}',
      '.sas-dock>*{pointer-events:auto}',
      '.sas-toasts{display:flex;flex-direction:column;align-items:flex-end;gap:8px}',
      '.sas-pills{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:8px}',
      '.sas-pill,.sas-toast{background:#fff;color:#0f172a;border:1px solid #e4e7ee;border-radius:8px;box-shadow:0 4px 12px rgba(15,23,42,.08),0 1px 3px rgba(15,23,42,.06)}',
      '.sas-pill{display:inline-flex;align-items:center;gap:8px;padding:6px 12px;font:inherit;font-size:.8125rem;font-weight:600;line-height:1.3;color:#334155}',
      'button.sas-pill{cursor:pointer}',
      'button.sas-pill:hover{border-color:#cfd5e1;background:#f8fafc}',
      'button.sas-pill:focus-visible{outline:2px solid #4f46e5;outline-offset:2px}',
      '.sas-dot{width:8px;height:8px;border-radius:50%;background:#4f46e5;flex-shrink:0}',
      '.sas-pill.is-offline .sas-dot{background:#94a3b8}',
      '.sas-pill.is-blocked .sas-dot{background:#dc2626}',
      '.sas-pill.is-busy .sas-dot{animation:sas-pulse 1s ease-in-out infinite}',
      '.sas-toast{display:flex;align-items:flex-start;gap:10px;width:360px;width:min(360px,calc(100vw - 32px));max-width:100%;padding:10px 12px;font-size:.875rem;line-height:1.4;border-left:3px solid #4f46e5;animation:sas-in .18s ease-out}',
      '.sas-toast.success{border-left-color:#16a34a}',
      '.sas-toast.warning{border-left-color:#d97706}',
      '.sas-toast.danger{border-left-color:#dc2626}',
      '.sas-toast .sas-toast-body{flex:1;min-width:0;overflow-wrap:anywhere}',
      '.sas-toast a{font-weight:600;margin-left:4px}',
      '.sas-toast-close{border:0;background:none;color:#64748b;font-size:1.1rem;line-height:1;padding:0 2px;cursor:pointer}',
      '.sas-toast-close:hover{color:#0f172a}',
      '.sas-notice{display:flex;align-items:flex-start;gap:.6rem}',
      '@keyframes sas-in{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}',
      '@keyframes sas-pulse{50%{opacity:.35}}',
      '@media (prefers-reduced-motion:reduce){.sas-toast,.sas-pill.is-busy .sas-dot{animation:none}}',
      '@media print{.sas-dock{display:none}}'
    ].join('\n');
    document.head.appendChild(style);

    var dock = document.createElement('div');
    dock.className = 'sas-dock';
    var toasts = document.createElement('div');
    toasts.className = 'sas-toasts';
    toasts.setAttribute('role', 'status');
    toasts.setAttribute('aria-live', 'polite');
    var pills = document.createElement('div');
    pills.className = 'sas-pills';

    var offlinePill = document.createElement('span');
    offlinePill.className = 'sas-pill is-offline';
    offlinePill.hidden = true;
    offlinePill.appendChild(dot());
    offlinePill.appendChild(document.createTextNode('Offline'));

    var queuePill = document.createElement('button');
    queuePill.type = 'button';
    queuePill.className = 'sas-pill';
    queuePill.hidden = true;
    queuePill.appendChild(dot());
    var queueText = document.createElement('span');
    queuePill.appendChild(queueText);
    queuePill.addEventListener('click', function () {
      if (navigator.onLine === false) {
        toast('warning', "You're offline. Saved attendance will be sent when you're back online.");
      } else if (!CAN_SYNC) {
        location.reload();
      } else {
        sync({ manual: true });
      }
    });

    pills.appendChild(offlinePill);
    pills.appendChild(queuePill);
    dock.appendChild(toasts);
    dock.appendChild(pills);
    document.body.appendChild(dock);

    ui = { dock: dock, toasts: toasts, offlinePill: offlinePill, queuePill: queuePill, queueText: queueText };
    placeDock();
    window.addEventListener('resize', placeDock);
    return ui;
  }

  function dot() {
    var span = document.createElement('span');
    span.className = 'sas-dot';
    span.setAttribute('aria-hidden', 'true');
    return span;
  }

  // Keep clear of the marking page's sticky save bar.
  function placeDock() {
    var bar = document.querySelector('.save-bar');
    ui.dock.style.bottom = bar ? (bar.offsetHeight + 16) + 'px' : '';
  }

  function toast(kind, message, link) {
    ensureUi();
    var el = document.createElement('div');
    el.className = 'sas-toast ' + kind;
    var body = document.createElement('div');
    body.className = 'sas-toast-body';
    body.textContent = message;
    if (link) {
      var a = document.createElement('a');
      a.href = link.href;
      a.textContent = link.text;
      body.appendChild(a);
    }
    var close = document.createElement('button');
    close.type = 'button';
    close.className = 'sas-toast-close';
    close.setAttribute('aria-label', 'Dismiss');
    close.textContent = '\u00d7';
    close.addEventListener('click', function () { el.remove(); });
    el.appendChild(body);
    el.appendChild(close);
    ui.toasts.appendChild(el);
    while (ui.toasts.children.length > 3) ui.toasts.removeChild(ui.toasts.firstChild);
    setTimeout(function () { el.remove(); }, kind === 'success' ? 6000 : 10000);
  }

  var pending = 0;
  var needsSignIn = false;

  function refresh() {
    ensureUi();
    return mine().then(function (items) {
      pending = items.length;
      ui.offlinePill.hidden = navigator.onLine !== false;
      ui.queuePill.hidden = pending === 0;
      ui.queuePill.classList.toggle('is-blocked', needsSignIn);
      ui.queuePill.classList.toggle('is-busy', !!syncing);
      ui.queueText.textContent = pending + ' waiting to sync' +
        (needsSignIn ? ' \u00b7 sign in to send' : '');
      ui.queuePill.title = needsSignIn ? 'Sign in again to send them'
        : plural(pending, 'attendance sheet', 'attendance sheets') + ' saved on this device. Click to send now.';
      placeDock();
    });
  }

  // ---------- The marking form ----------

  function notice(form, kind, message) {
    var el = document.getElementById('sas-offline-notice');
    if (!el) {
      el = document.createElement('div');
      el.id = 'sas-offline-notice';
      el.setAttribute('role', 'status');
      form.parentNode.insertBefore(el, form);
    }
    el.className = 'alert alert-' + kind + ' sas-notice';
    el.textContent = '';
    var icon = document.createElement('i');
    icon.className = kind === 'success' ? 'fas fa-check-circle' : kind === 'danger' ? 'fas fa-exclamation-circle' : 'fas fa-cloud-upload-alt';
    icon.setAttribute('aria-hidden', 'true');
    var span = document.createElement('span');
    span.textContent = message;
    el.appendChild(icon);
    el.appendChild(span);
    return el;
  }

  function setBusy(form, busy) {
    form.__sasBusy = busy;
    form.setAttribute('aria-busy', busy ? 'true' : 'false');
    Array.prototype.forEach.call(form.querySelectorAll('button[type="submit"], button:not([type])'), function (button) {
      button.disabled = busy;
      var icon = button.querySelector('i');
      if (!icon) return;
      if (busy) {
        icon.__sasClass = icon.className;
        icon.className = 'fas fa-circle-notch fa-spin';
      } else if (icon.__sasClass) {
        icon.className = icon.__sasClass;
      }
    });
  }

  // Resolves true when the server answers at all (any HTTP status).
  function reachable() {
    var controller = typeof AbortController === 'function' ? new AbortController() : null;
    var timer = controller ? setTimeout(function () { controller.abort(); }, PROBE_TIMEOUT) : null;
    var url = PING_URL + (PING_URL.indexOf('?') === -1 ? '?' : '&') + 'ping=' + Date.now();
    return fetch(url, {
      method: 'GET', cache: 'no-store', credentials: 'same-origin',
      signal: controller ? controller.signal : undefined
    }).then(function () { return true; }, function () { return false; }).then(function (ok) {
      clearTimeout(timer);
      return ok;
    });
  }

  function serialize(form, submitter) {
    var params = new URLSearchParams(new FormData(form));
    if (submitter && submitter.name && !params.has(submitter.name)) params.append(submitter.name, submitter.value);
    return params.toString();
  }

  function submitNormally(form, submitter) {
    form.__sasNative = true;
    try {
      if (typeof form.requestSubmit === 'function') {
        if (submitter) form.requestSubmit(submitter);
        else form.requestSubmit();
        return;
      }
    } catch (err) {
      /* fall back to submit() below */
    } finally {
      form.__sasNative = false;
    }
    if (submitter && submitter.name) {
      var hidden = document.createElement('input');
      hidden.type = 'hidden';
      hidden.name = submitter.name;
      hidden.value = submitter.value;
      form.appendChild(hidden);
    }
    HTMLFormElement.prototype.submit.call(form);
  }

  function keep(form, body) {
    var item = {
      url: formUrl(form),
      body: body,
      title: document.title,
      subtitle: text(document.querySelector('.page-subtitle')),
      savedAt: new Date().toISOString(),
      user: USER || ''
    };
    return outbox.put(item).then(function () {
      // Nothing is unsaved any more: drop the "leave page?" warning.
      window.onbeforeunload = null;
      form.dispatchEvent(new CustomEvent('sas:queued', { bubbles: true, detail: { url: item.url } }));
      notice(form, 'info', "Saved on this device. It will be sent automatically when you're back online.");
      toast('success', "Saved on this device. It will be sent automatically when you're back online.");
      return refresh();
    }, function () {
      notice(form, 'danger', "Couldn't keep this on your device. Stay on this page and save again once you're back online.");
    });
  }

  function initMarkForm(form) {
    form.addEventListener('submit', function (event) {
      if (form.__sasNative) return;              // our own re-submit after the reachability check
      if (event.defaultPrevented) return;
      event.preventDefault();
      if (form.__sasBusy) return;
      var submitter = event.submitter || null;
      var body = serialize(form, submitter);
      if (navigator.onLine === false) {
        keep(form, body);
        return;
      }
      setBusy(form, true);
      reachable().then(function (ok) {
        setBusy(form, false);
        if (ok) submitNormally(form, submitter);
        else keep(form, body);
      });
    });
  }

  function updateTally(form) {
    var present = form.querySelectorAll('input.present:checked').length;
    var absent = form.querySelectorAll('input.absent:checked').length;
    Array.prototype.forEach.call(document.querySelectorAll('[data-tally-present]'), function (el) { el.textContent = present; });
    Array.prototype.forEach.call(document.querySelectorAll('[data-tally-absent]'), function (el) { el.textContent = absent; });
    Array.prototype.forEach.call(form.querySelectorAll('.mark-row'), function (row) {
      var box = row.querySelector('input.absent');
      row.classList.toggle('is-absent', !!(box && box.checked));
    });
  }

  // Reopened a sheet that is still waiting? Show what will be sent.
  function restore(form) {
    var url = formUrl(form);
    return mine().then(function (items) {
      var item = items.filter(function (i) { return i.url === url; })[0];
      if (!item) return;
      var params = new URLSearchParams(item.body);
      Array.prototype.forEach.call(form.querySelectorAll('input[type="radio"]'), function (input) {
        if (params.has(input.name)) input.checked = params.get(input.name) === input.value;
      });
      updateTally(form);
      var when = '';
      try {
        when = new Date(item.savedAt).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });
      } catch (err) { /* ignore */ }
      notice(form, 'info', 'This attendance was saved on this device' + (when ? ' (' + when + ')' : '') +
        " and hasn't been sent yet. It will be sent automatically" +
        (navigator.onLine === false ? " when you're back online" : '') + '; saving again replaces it.');
    }).catch(function () {});
  }

  function sentNotice(item) {
    Array.prototype.forEach.call(document.querySelectorAll('form[data-mark-form]'), function (form) {
      if (formUrl(form) === item.url) notice(form, 'success', 'Sent: the attendance you saved offline is now recorded.');
    });
  }

  // ---------- Sending saved sheets ----------

  function landedOnLogin(response) {
    if (!response.redirected || !response.url) return false;
    try {
      return new URL(response.url).pathname === LOGIN_PATH;
    } catch (err) {
      return false;
    }
  }

  function send(item) {
    var target;
    try {
      target = new URL(item.url, location.href);
    } catch (err) {
      return Promise.resolve('gone');
    }
    if (target.origin !== location.origin) return Promise.resolve('gone');
    var params = new URLSearchParams(item.body);
    // Prefer this session's token: the saved one goes stale after signing in again.
    var token = currentCsrfToken() || params.get('csrfmiddlewaretoken') || '';
    if (token) params.set('csrfmiddlewaretoken', token);
    return fetch(target.href, {
      method: 'POST',
      body: params.toString(),
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'X-CSRFToken': token },
      redirect: 'follow'
    }).then(function (response) {
      if (response.status === 401 || response.status === 403 || landedOnLogin(response)) return 'auth';
      if (response.status === 404 || response.status === 410) return 'gone';
      return response.ok ? 'sent' : 'retry';
    }, function () {
      return 'offline';
    });
  }

  var syncing = null;
  var toldSignIn = false;

  function signInPrompt(count, manual) {
    needsSignIn = true;
    if (toldSignIn && !manual) return;
    toldSignIn = true;
    var onLogin = location.pathname === LOGIN_PATH;
    toast('warning', 'Sign in again to send ' + plural(count, 'saved attendance sheet', 'saved attendance sheets') + '.',
      onLogin ? null : { href: LOGIN_PATH + '?next=' + encodeURIComponent(location.pathname + location.search), text: 'Sign in' });
  }

  function sync(options) {
    var manual = !!(options && options.manual);
    if (!CAN_SYNC || navigator.onLine === false) return refresh();
    if (syncing) return syncing;
    syncing = mine().then(function (items) {
      if (!items.length) return;
      if (USER === '') {                        // signed out: sending can only fail
        signInPrompt(items.length, manual);
        return;
      }
      ensureUi().queuePill.classList.add('is-busy');
      var failed = 0;
      var chain = Promise.resolve('next');
      items.forEach(function (item) {
        chain = chain.then(function (state) {
          if (state === 'stop') return 'stop';
          return send(item).then(function (result) {
            if (result === 'sent') {
              return outbox.remove(item.url).then(function () {
                toast('success', 'Synced attendance: ' + label(item));
                sentNotice(item);
                return 'next';
              });
            }
            if (result === 'gone') {
              return outbox.remove(item.url).then(function () {
                toast('danger', "Couldn't send attendance for " + label(item) + ': that lecture no longer exists.');
                return 'next';
              });
            }
            if (result === 'auth') {
              return mine().then(function (left) {
                signInPrompt(left.length, manual);
                return 'stop';
              });
            }
            if (result === 'offline') return 'stop';
            failed += 1;                          // server error: keep it, try again later
            return 'next';
          });
        });
      });
      return chain.then(function (state) {
        if (state !== 'stop') needsSignIn = false;
        if (failed && manual) {
          toast('warning', "Couldn't send " + plural(failed, 'sheet', 'sheets') + ' right now. They will be retried automatically.');
        }
      });
    }).catch(function () { /* storage trouble: nothing to send */ }).then(function () {
      syncing = null;
      return refresh();
    });
    return syncing;
  }

  // ---------- Start ----------

  function init() {
    ensureUi();
    var forms = Array.prototype.slice.call(document.querySelectorAll('form[data-mark-form]'));
    forms.forEach(initMarkForm);
    Promise.all(forms.map(restore)).then(refresh).then(function () { return sync(); });

    window.addEventListener('online', function () { sync(); });
    window.addEventListener('offline', function () { refresh(); });
    document.addEventListener('visibilitychange', function () {
      if (!document.hidden) sync();
    });
    setInterval(function () {
      if (pending > 0 && !needsSignIn) sync();
    }, RETRY_EVERY);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
