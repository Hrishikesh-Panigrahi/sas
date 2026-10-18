/* SAS — live check-in projector page: rotating QR code, countdown and who's in. */
(function () {
  'use strict';
  var root = document.getElementById('checkin');
  if (!root) return;

  var url = root.getAttribute('data-state');
  var expected = +root.getAttribute('data-expected') || 0;
  var qr = root.querySelector('[data-qr]');
  var codeEl = root.querySelector('[data-code]');
  var bar = root.querySelector('[data-bar]');
  var countEl = root.querySelector('[data-count]');
  var progress = root.querySelector('[data-progress]');
  var people = root.querySelector('[data-people]');
  var windowId = null, deadline = 0, period = 15, seen = {}, timer = null;
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function poll() {
    clearTimeout(timer);
    fetch(url + '?have=' + encodeURIComponent(windowId || ''), { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.closed) { window.location.reload(); return; }
        if (d.svg) qr.innerHTML = d.svg;   // generated server-side by segno
        windowId = d.window;
        period = d.period;
        deadline = Date.now() + d.seconds_left * 1000;
        codeEl.textContent = d.code.slice(0, 3) + ' ' + d.code.slice(3);
        countEl.textContent = d.count;
        progress.style.width = (expected ? Math.min(100, 100 * d.count / expected) : 0) + '%';
        renderPeople(d.people);
        // Poll again shortly, and right after the code changes.
        timer = setTimeout(poll, Math.min(2000, d.seconds_left * 1000 + 150));
      })
      .catch(function () { timer = setTimeout(poll, 3000); });
  }

  function renderPeople(list) {
    list.slice().reverse().forEach(function (p) {
      var key = p.name + p.at;
      if (seen[key]) return;
      seen[key] = true;
      var chip = document.createElement('span');
      chip.className = 'checkin-person' + (reduce ? '' : ' pop');
      var av = document.createElement('span');
      av.className = 'avatar';
      av.textContent = p.initials;
      var name = document.createElement('span');
      name.textContent = p.name;
      chip.appendChild(av);
      chip.appendChild(name);
      people.insertBefore(chip, people.firstChild);
    });
  }

  function tick() {
    var left = Math.max(0, deadline - Date.now());
    bar.style.width = (100 * left / (period * 1000)) + '%';
    requestAnimationFrame(tick);
  }

  // Keep the projector awake while check-in runs.
  var lock = null;
  function wake() {
    if ('wakeLock' in navigator && document.visibilityState === 'visible') {
      navigator.wakeLock.request('screen').then(function (l) { lock = l; }).catch(function () {});
    }
  }
  document.addEventListener('visibilitychange', function () { if (document.visibilityState === 'visible') { wake(); poll(); } });

  var fs = document.querySelector('[data-fullscreen]');
  if (fs) {
    fs.addEventListener('click', function () {
      if (document.fullscreenElement) document.exitFullscreen();
      else if (root.requestFullscreen) root.requestFullscreen();
    });
  }

  wake();
  poll();
  requestAnimationFrame(tick);
})();
