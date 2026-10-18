/* SAS - quick roll call on the attendance marking page.
 *
 * Two phone-friendly ways to fill in the present/absent radios:
 *   Swipe: one student card at a time. Swipe right = present, left = absent.
 *   Voice: reads each name aloud, then listens for "present" / "absent".
 *
 * Every decision sets the row's radio and fires a bubbling `change` event, so
 * app.js keeps the tally, the absent highlighting and the unsaved-changes
 * warning in step. Closing the overlay keeps everything already decided.
 * Student text is inserted with textContent only. No network calls.
 */
(function () {
  'use strict';

  var overlay = document.querySelector('[data-rc]');
  var form = document.querySelector('[data-mark-form]');
  if (!overlay || !form) return;
  var markList = document.getElementById('mark-list') || form;

  // Keep the overlay out of the form and out of any stacking context in the page.
  document.body.appendChild(overlay);

  function q(sel) { return overlay.querySelector(sel); }
  function each(list, fn) { Array.prototype.forEach.call(list, fn); }

  var dialog = q('[data-rc-dialog]');
  var titleEl = q('[data-rc-title]');
  var countEl = q('[data-rc-count]');
  var barEl = q('[data-rc-bar]');
  var cardsEl = q('[data-rc-cards]');
  var stage = q('[data-rc-stage]');
  var hintEl = q('[data-rc-hint]');
  var lastEl = q('[data-rc-last]');
  var liveEl = q('[data-rc-live]');
  var voiceBar = q('[data-rc-voice]');
  var micBtn = q('[data-rc-mic]');
  var micIcon = q('[data-rc-mic-icon]');
  var voiceStatusEl = q('[data-rc-voice-status]');
  var transcriptEl = q('[data-rc-transcript]');
  var readBox = q('[data-rc-read]');
  var readWrap = q('[data-rc-read-wrap]');
  var summaryEl = q('[data-rc-summary]');
  var summaryTitle = q('[data-rc-summary-title]');
  var sumCountEl = q('[data-rc-sum-count]');
  var sumSkippedEl = q('[data-rc-sum-skipped]');
  var absentListEl = q('[data-rc-absent-list]');
  var absentNoneEl = q('[data-rc-absent-none]');
  var msgEl = q('[data-rc-msg]');
  var msgIcon = q('[data-rc-msg-icon]');
  var msgTitle = q('[data-rc-msg-title]');
  var msgText = q('[data-rc-msg-text]');
  var toSwipeBtn = q('[data-rc-to-swipe]');
  var retryBtn = q('[data-rc-retry]');
  if (!dialog || !stage || !cardsEl || !summaryEl || !msgEl) return;

  var Recognition = window.SpeechRecognition || window.webkitSpeechRecognition || null;
  var synth = ('speechSynthesis' in window && 'SpeechSynthesisUtterance' in window) ? window.speechSynthesis : null;
  var motionQuery = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
  var hoverQuery = window.matchMedia ? window.matchMedia('(hover: hover) and (pointer: fine)') : null;

  var THRESHOLD = 0.3;   // share of the card width that commits a swipe
  var FLICK = 0.5;       // px per ms; a quick flick commits a shorter swipe
  var FLY_MS = 300;
  var VOICE_HOLD_MS = 420;
  var PREF_KEY = 'sas.rollcall.readAloud';

  var state = {
    open: false,
    mode: 'swipe',      // swipe | voice
    phase: 'cards',     // cards | summary | message
    students: [],
    index: 0,
    history: [],
    opener: null
  };
  var topCard = null;
  var behindCard = null;
  var anim = null;
  var drag = null;
  var dragFrame = 0;
  var lockState = null;
  var announceTimer = 0;

  var voice = {
    rec: null, gen: 0, paused: false, pauseNote: '', speaking: false, live: false, everLive: false,
    startedAt: 0, quickEnds: 0, netErrors: 0, restartTimer: 0, speakTimer: 0, utterance: null
  };
  var readAloud = loadPref();

  // ------------------------------------------------------------ helpers
  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  }
  function clean(s) { return String(s || '').replace(/\s+/g, ' ').trim(); }
  function textOf(root, sel) { var n = root.querySelector(sel); return n ? clean(n.textContent) : ''; }
  function reducedMotion() { return !!(motionQuery && motionQuery.matches); }
  function loadPref() {
    try { var v = window.localStorage.getItem(PREF_KEY); return v === null ? true : v === '1'; } catch (e) { return true; }
  }
  function savePref(on) {
    try { window.localStorage.setItem(PREF_KEY, on ? '1' : '0'); } catch (e) { /* storage unavailable */ }
  }
  function vibrate() {
    try { if (navigator.vibrate) navigator.vibrate(12); } catch (e) { /* not allowed */ }
  }
  function announce(msg) {
    if (!liveEl) return;
    clearTimeout(announceTimer);
    liveEl.textContent = '';
    announceTimer = setTimeout(function () { liveEl.textContent = msg; }, 60);
  }

  // ------------------------------------------------------------ students
  function readStudent(row) {
    var title = row.querySelector('.title');
    var name = '';
    var note = null;
    if (title) {
      // The name is the title's own text; badges inside it (e.g. "On leave") are extras.
      for (var n = title.firstChild; n; n = n.nextSibling) {
        if (n.nodeType === 3) name += n.nodeValue;
      }
      name = clean(name) || clean(title.textContent);
      var badge = title.querySelector('.badge');
      if (badge && clean(badge.textContent)) {
        note = { text: clean(badge.textContent), title: badge.getAttribute('title') || '' };
      }
    }
    var initials = textOf(row, '.avatar');
    if (!name) name = 'Unnamed student';
    if (!initials) initials = name.charAt(0).toUpperCase();
    return {
      row: row,
      name: name,
      roll: textOf(row, '.roll'),
      initials: initials,
      email: textOf(row, '.meta'),
      note: note,
      present: row.querySelector('input.present'),
      absent: row.querySelector('input.absent')
    };
  }
  function visibleStudents() {
    var out = [];
    each(markList.querySelectorAll('.mark-row'), function (row) {
      if (row.style.display !== 'none') out.push(readStudent(row));
    });
    return out;
  }
  function statusOf(s) { return s.absent && s.absent.checked ? 'absent' : 'present'; }
  function fireChange(input) {
    var ev;
    try { ev = new Event('change', { bubbles: true }); } catch (e) {
      ev = document.createEvent('Event');
      ev.initEvent('change', true, false);
    }
    input.dispatchEvent(ev);
  }
  function setStatus(s, status) {
    var input = status === 'absent' ? s.absent : s.present;
    if (!input) return;
    input.checked = true;
    fireChange(input);
  }
  function current() { return state.students[state.index] || null; }
  function describe(s, i) {
    return (i + 1) + ' of ' + state.students.length + ': ' + s.name +
      (s.roll ? ', roll ' + s.roll : '') + ', currently ' + statusOf(s) +
      (s.note ? ', ' + s.note.text : '') + '.';
  }

  // ------------------------------------------------------------ page lock + focus
  function lockPage() {
    var root = document.documentElement;
    var body = document.body;
    var scrollbar = window.innerWidth - root.clientWidth;
    lockState = { padding: body.style.paddingRight, hidden: [] };
    root.classList.add('rc-lock');
    if (scrollbar > 0) body.style.paddingRight = scrollbar + 'px';
    each(body.children, function (child) {
      if (child === overlay || /^(SCRIPT|STYLE|LINK|TEMPLATE|NOSCRIPT)$/.test(child.tagName)) return;
      lockState.hidden.push({ el: child, aria: child.getAttribute('aria-hidden'), inert: !!child.inert });
      child.setAttribute('aria-hidden', 'true');
      if ('inert' in child) child.inert = true;
    });
  }
  function unlockPage() {
    if (!lockState) return;
    document.documentElement.classList.remove('rc-lock');
    document.body.style.paddingRight = lockState.padding;
    lockState.hidden.forEach(function (h) {
      if (h.aria === null) h.el.removeAttribute('aria-hidden'); else h.el.setAttribute('aria-hidden', h.aria);
      if ('inert' in h.el) h.el.inert = h.inert;
    });
    lockState = null;
  }
  function focusables() {
    var out = [];
    each(dialog.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'), function (node) {
      if (!node.disabled && node.getClientRects().length) out.push(node);
    });
    return out;
  }
  function ensureFocus() {
    var a = document.activeElement;
    if (!a || !dialog.contains(a) || !a.getClientRects().length) dialog.focus();
  }
  function trapTab(e) {
    var items = focusables();
    if (!items.length) { e.preventDefault(); dialog.focus(); return; }
    var first = items[0];
    var last = items[items.length - 1];
    var a = document.activeElement;
    var inside = dialog.contains(a);
    if (e.shiftKey) {
      if (!inside || a === first || a === dialog) { e.preventDefault(); last.focus(); }
    } else if (!inside || a === last) {
      e.preventDefault(); first.focus();
    }
  }

  // ------------------------------------------------------------ open / close / modes
  function open(mode, opener) {
    if (state.open) return;
    state.open = true;
    state.opener = opener || document.activeElement;
    state.students = visibleStudents();
    state.index = 0;
    state.history = [];
    setLast(null);
    lockPage();
    overlay.hidden = false;
    dialog.focus();
    startMode(mode);
  }

  function close() {
    if (!state.open) return;
    cancelAnim();
    cancelDrag();
    voiceHalt();
    voice.paused = false;
    state.open = false;
    overlay.hidden = true;
    stage.textContent = '';
    topCard = behindCard = null;
    unlockPage();
    var opener = state.opener;
    state.opener = null;
    if (opener && document.documentElement.contains(opener) && typeof opener.focus === 'function') {
      try { opener.focus(); } catch (e) { /* element can't take focus */ }
    }
  }

  function hintText() {
    var keys = hoverQuery && hoverQuery.matches ? ' Keys: \u2192 present, \u2190 absent, Backspace undo.' : '';
    if (state.mode === 'voice') return 'Say \u201cpresent\u201d or \u201cabsent\u201d \u2014 or swipe, or tap a button.' + keys;
    return 'Swipe right for present, left for absent.' + keys;
  }

  function startMode(mode) {
    voiceHalt();
    state.mode = mode === 'voice' ? 'voice' : 'swipe';
    overlay.classList.toggle('rc--voice', state.mode === 'voice');
    titleEl.textContent = state.mode === 'voice' ? 'Voice roll call' : 'Swipe roll call';
    if (hintEl) hintEl.textContent = hintText();

    if (!state.students.length) {
      showMessage({
        icon: 'fa-search',
        title: 'No students to show',
        text: 'The search box is hiding every student. Clear the search to take the roll for the whole class.',
        swipe: false, retry: false
      });
      return;
    }
    if (state.mode === 'voice') {
      var problem = voiceProblem();
      if (problem) { showMessage(problem); return; }
      voice.paused = false;
      voice.pauseNote = '';
      voice.quickEnds = 0;
      voice.netErrors = 0;
    }
    show(0, '');
  }

  function showPanel(name) {
    state.phase = name;
    cardsEl.hidden = name !== 'cards';
    summaryEl.hidden = name !== 'summary';
    msgEl.hidden = name !== 'message';
    if (voiceBar) voiceBar.hidden = !(state.mode === 'voice' && name === 'cards');
  }

  function updateProgress() {
    var total = state.students.length;
    var i = Math.min(state.index, total);
    if (countEl) countEl.textContent = total ? (state.phase === 'summary' ? total : i + 1) + ' of ' + total : '';
    if (barEl) barEl.style.width = (total ? (state.phase === 'summary' ? 100 : (i / total) * 100) : 0) + '%';
  }

  function updateUndo() {
    var off = !state.history.length;
    var a = document.activeElement;
    if (off && a && a.hasAttribute && a.hasAttribute('data-rc-undo')) dialog.focus();
    each(overlay.querySelectorAll('[data-rc-undo]'), function (b) { b.disabled = off; });
  }

  // Show the current student (or the summary when we've run out).
  function show(enterDir, prefix) {
    if (state.index >= state.students.length) { showSummary(prefix); return; }
    showPanel('cards');
    render(enterDir);
    updateProgress();
    updateUndo();
    ensureFocus();
    announce((prefix || '') + describe(current(), state.index));
    if (state.mode === 'voice') voiceStudent();
  }

  function showSummary(prefix) {
    voiceHalt();
    stage.textContent = '';
    topCard = behindCard = null;
    showPanel('summary');

    var present = 0;
    var absent = [];
    each(markList.querySelectorAll('.mark-row'), function (row) {
      var s = readStudent(row);
      if (statusOf(s) === 'absent') absent.push(s); else present++;
    });
    sumCountEl.textContent = present + ' present \u00b7 ' + absent.length + ' absent';

    var lastAction = {};
    state.history.forEach(function (h) { lastAction[h.index] = h.type; });
    var skipped = 0;
    for (var k in lastAction) {
      if (Object.prototype.hasOwnProperty.call(lastAction, k) && lastAction[k] === 'skip') skipped++;
    }
    sumSkippedEl.hidden = !skipped;
    sumSkippedEl.textContent = skipped === 1 ? '1 student skipped \u2014 left as it was.' :
      skipped + ' students skipped \u2014 left as they were.';

    absentListEl.textContent = '';
    absent.forEach(function (s) {
      var li = el('li');
      li.appendChild(el('span', 'dot red'));
      li.appendChild(el('span', 'rc-li-name', s.name));
      var meta = [];
      if (s.note) meta.push(s.note.text);
      if (s.roll) meta.push('Roll ' + s.roll);
      if (meta.length) li.appendChild(el('span', 'rc-li-meta', meta.join(' \u00b7 ')));
      absentListEl.appendChild(li);
    });
    absentListEl.hidden = !absent.length;
    absentNoneEl.hidden = !!absent.length;

    updateProgress();
    updateUndo();
    announce((prefix || '') + 'Roll call complete. ' + present + ' present, ' + absent.length + ' absent.' +
      (absent.length ? ' Absent: ' + absent.map(function (s) { return s.name; }).join(', ') + '.' : ''));
    summaryTitle.focus();
  }

  function showMessage(m) {
    voiceHalt();
    cancelAnim();
    stage.textContent = '';
    topCard = behindCard = null;
    showPanel('message');
    if (msgIcon) msgIcon.className = 'fas ' + (m.icon || 'fa-microphone-slash');
    msgTitle.textContent = m.title;
    msgText.textContent = m.text;
    toSwipeBtn.hidden = !m.swipe;
    retryBtn.hidden = !m.retry;
    if (countEl) countEl.textContent = '';
    announce(m.title + '. ' + m.text);
    msgTitle.focus();
  }

  function save() {
    var btn = form.querySelector('.save-bar button[type="submit"]') || form.querySelector('button[type="submit"]');
    close();
    if (typeof form.requestSubmit === 'function') {
      try { if (btn) form.requestSubmit(btn); else form.requestSubmit(); return; } catch (e) { /* fall back */ }
    }
    if (btn) btn.click(); else form.submit();
  }

  // ------------------------------------------------------------ cards
  function buildCard(s) {
    var card = el('div', 'rc-card');
    var stampP = el('div', 'rc-stamp rc-stamp-present', 'Present');
    var stampA = el('div', 'rc-stamp rc-stamp-absent', 'Absent');
    stampP.setAttribute('aria-hidden', 'true');
    stampA.setAttribute('aria-hidden', 'true');
    card.appendChild(stampP);
    card.appendChild(stampA);

    var avatar = el('div', 'rc-avatar', s.initials);
    avatar.setAttribute('aria-hidden', 'true');
    card.appendChild(avatar);
    card.appendChild(el('div', 'rc-name', s.name));
    if (s.email && s.email !== s.name) card.appendChild(el('div', 'rc-email', s.email));

    var chips = el('div', 'rc-chips');
    if (s.roll) chips.appendChild(el('span', 'rc-chip', 'Roll ' + s.roll));
    var status = statusOf(s);
    var chip = el('span', 'rc-chip is-' + status);
    chip.appendChild(el('span', 'dot ' + (status === 'absent' ? 'red' : 'green')));
    chip.appendChild(document.createTextNode(status === 'absent' ? 'Currently absent' : 'Currently present'));
    chips.appendChild(chip);
    if (s.note) {
      var note = el('span', 'rc-chip is-note', s.note.text);
      if (s.note.title) note.title = s.note.title;
      chips.appendChild(note);
    }
    card.appendChild(chips);
    card._stamps = [stampP, stampA];
    return card;
  }

  function render(enterDir) {
    stage.textContent = '';
    topCard = behindCard = null;
    var s = current();
    if (!s) return;
    var next = state.students[state.index + 1];
    if (next) {
      behindCard = buildCard(next);
      behindCard.classList.add('is-behind');
      behindCard.setAttribute('aria-hidden', 'true');
      stage.appendChild(behindCard);
    }
    topCard = buildCard(s);
    topCard.setAttribute('role', 'group');
    topCard.setAttribute('aria-label', s.name);
    stage.appendChild(topCard);
    bindDrag(topCard);

    if (enterDir != null && enterDir !== 0 && !reducedMotion()) {
      // Slide back in from the side it left (used by Undo).
      var card = topCard;
      card.classList.add('is-dragging');
      card.style.transform = enterDir === 'up' ? 'translate3d(0,-110%,0)' :
        'translate3d(' + (enterDir > 0 ? 120 : -120) + '%,0,0) rotate(' + (enterDir > 0 ? 18 : -18) + 'deg)';
      card.style.opacity = '0';
      void card.offsetWidth;
      card.classList.remove('is-dragging');
      card.style.transform = '';
      card.style.opacity = '';
    }
  }

  function stampCard(card, dir) {
    if (!card) return;
    card.classList.remove('over-present', 'over-absent');
    if (card._stamps) { card._stamps[0].style.opacity = ''; card._stamps[1].style.opacity = ''; }
    if (dir > 0) card.classList.add('show-present');
    else if (dir < 0) card.classList.add('show-absent');
  }

  // Move past the current card: optional pause (voice feedback), then fly off.
  function advance(dir, opts, prefix) {
    var card = topCard;
    var behind = behindCard;
    var reduce = reducedMotion();
    stampCard(card, dir);
    var a = anim = {
      timer: 0,
      done: function () { state.index++; show(null, prefix); }
    };
    function complete() {
      if (anim !== a) return;
      anim = null;
      a.done();
    }
    function fly() {
      if (anim !== a) return;
      if (reduce || !card) { complete(); return; }
      var w = stage.offsetWidth || 360;
      var dy = opts.dy || 0;
      card.classList.remove('is-dragging');
      card.classList.add('is-flying');
      card.style.transform = dir === 0 ?
        'translate3d(0,' + -(stage.offsetHeight + 160) + 'px,0)' :
        'translate3d(' + dir * (window.innerWidth / 2 + w) + 'px,' + (dy + 40) + 'px,0) rotate(' + dir * 24 + 'deg)';
      card.style.opacity = '0';
      if (behind) {
        behind.classList.remove('is-dragging');
        behind.style.transform = '';
        behind.classList.add('is-promoted');
      }
      a.timer = setTimeout(complete, FLY_MS);
    }
    if (opts.hold) a.timer = setTimeout(fly, opts.hold); else fly();
  }
  function finishAnim() {
    var a = anim;
    if (!a) return;
    anim = null;
    clearTimeout(a.timer);
    a.done();
  }
  function cancelAnim() {
    if (!anim) return;
    clearTimeout(anim.timer);
    anim = null;
  }

  function decide(status, opts) {
    opts = opts || {};
    if (!state.open || state.phase !== 'cards') return;
    if (status !== 'present' && status !== 'absent') return;
    finishAnim();
    if (state.phase !== 'cards') return;
    var s = current();
    if (!s || !topCard) return;
    if (state.mode === 'voice') voiceHalt();
    var prev = statusOf(s);
    setStatus(s, status);
    state.history.push({ type: 'mark', index: state.index, prev: prev, status: status });
    setLast(s, status);
    updateUndo();
    advance(status === 'present' ? 1 : -1, opts, s.name + ' marked ' + status + '. ');
  }

  function skip() {
    if (!state.open || state.phase !== 'cards') return;
    finishAnim();
    if (state.phase !== 'cards') return;
    var s = current();
    if (!s || !topCard) return;
    if (state.mode === 'voice') voiceHalt();
    state.history.push({ type: 'skip', index: state.index });
    setLast(s, 'skip');
    updateUndo();
    advance(0, {}, s.name + ' skipped. ');
  }

  function undo() {
    if (!state.open || state.phase === 'message') return;
    finishAnim();
    var h = state.history.pop();
    if (!h) { announce('Nothing to undo.'); return; }
    var s = state.students[h.index];
    if (!s) return;
    if (h.type === 'mark') setStatus(s, h.prev);
    voiceHalt();
    state.index = h.index;
    setLast(null);
    var dir = h.type === 'skip' ? 'up' : (h.status === 'present' ? 1 : -1);
    show(dir, h.type === 'mark' ? 'Undone: ' + s.name + ' is back to ' + h.prev + '. ' : 'Back to ' + s.name + '. ');
  }

  function setLast(s, what) {
    if (!lastEl) return;
    lastEl.textContent = '';
    if (!s) return;
    lastEl.appendChild(el('span', 'rc-last-dot is-' + what));
    lastEl.appendChild(document.createTextNode(s.name + (what === 'skip' ? ' skipped' : ' \u2014 ' + what)));
  }

  // ------------------------------------------------------------ swipe gestures
  function bindDrag(card) {
    if (!window.PointerEvent) return;
    card.addEventListener('pointerdown', onDown);
    card.addEventListener('pointermove', onMove);
    card.addEventListener('pointerup', onUp);
    card.addEventListener('pointercancel', onUp);
    card.addEventListener('lostpointercapture', onUp);
    card.addEventListener('dragstart', function (e) { e.preventDefault(); });
  }

  function onDown(e) {
    if (!state.open || state.phase !== 'cards' || drag) return;
    if (e.pointerType === 'mouse' && e.button !== 0) return;
    if (anim) { finishAnim(); return; }   // the card under the pointer just changed
    var card = e.currentTarget;
    if (card !== topCard) return;
    var now = Date.now();
    drag = {
      id: e.pointerId, card: card, x0: e.clientX, y0: e.clientY, dx: 0, dy: 0,
      w: card.offsetWidth || 320, vx: 0, lastX: e.clientX, lastT: now
    };
    try { card.setPointerCapture(e.pointerId); } catch (err) { /* capture unsupported */ }
    card.classList.add('is-dragging');
    if (behindCard) behindCard.classList.add('is-dragging');
  }

  function onMove(e) {
    if (!drag || e.pointerId !== drag.id) return;
    var now = Date.now();
    var dt = now - drag.lastT;
    if (dt > 0) drag.vx = 0.7 * ((e.clientX - drag.lastX) / dt) + 0.3 * drag.vx;
    drag.lastX = e.clientX;
    drag.lastT = now;
    drag.dx = e.clientX - drag.x0;
    drag.dy = e.clientY - drag.y0;
    if (!dragFrame) dragFrame = requestAnimationFrame(paintDrag);
  }

  function paintDrag() {
    dragFrame = 0;
    if (!drag) return;
    var c = drag.card;
    var dx = drag.dx;
    var thr = drag.w * THRESHOLD;
    var rot = Math.max(-18, Math.min(18, (dx / drag.w) * 14));
    var p = Math.min(1, Math.abs(dx) / thr);
    c.style.transform = 'translate3d(' + dx + 'px,' + drag.dy * 0.2 + 'px,0) rotate(' + rot + 'deg)';
    if (c._stamps) {
      c._stamps[0].style.opacity = dx > 0 ? p : 0;
      c._stamps[1].style.opacity = dx < 0 ? p : 0;
    }
    c.classList.toggle('over-present', dx >= thr);
    c.classList.toggle('over-absent', dx <= -thr);
    if (behindCard) {
      behindCard.style.transform = 'translate3d(0,' + 14 * (1 - p) + 'px,0) scale(' + (0.94 + 0.06 * p) + ')';
    }
  }

  function onUp(e) {
    if (!drag || e.pointerId !== drag.id) return;
    var d = drag;
    drag = null;
    if (dragFrame) { cancelAnimationFrame(dragFrame); dragFrame = 0; }
    try { if (d.card.hasPointerCapture && d.card.hasPointerCapture(d.id)) d.card.releasePointerCapture(d.id); } catch (err) { /* already released */ }
    if (Date.now() - d.lastT > 90) d.vx = 0;   // finger stopped before lifting
    var thr = d.w * THRESHOLD;
    var flick = Math.abs(d.vx) > FLICK && Math.abs(d.dx) > 24 && (d.vx > 0) === (d.dx > 0);
    if (e.type === 'pointerup' && d.card === topCard && (Math.abs(d.dx) >= thr || flick)) {
      vibrate();
      decide(d.dx > 0 ? 'present' : 'absent', { dy: d.dy * 0.2 });
    } else {
      springBack(d.card);
    }
  }

  function springBack(card) {
    card.classList.remove('is-dragging', 'over-present', 'over-absent');
    card.style.transform = '';
    if (card._stamps) { card._stamps[0].style.opacity = ''; card._stamps[1].style.opacity = ''; }
    if (behindCard) { behindCard.classList.remove('is-dragging'); behindCard.style.transform = ''; }
  }

  function cancelDrag() {
    if (dragFrame) { cancelAnimationFrame(dragFrame); dragFrame = 0; }
    drag = null;
  }

  // ------------------------------------------------------------ voice
  var PRESENT_WORDS = toSet('present yes yeah yep yup here haan ha p \u0939\u093e\u0901 \u0939\u093e\u0902');
  var ABSENT_WORDS = toSet('absent no nope nahi nahin a \u0928\u0939\u0940\u0902 \u0928\u0939\u0940');
  // Too short to trust inside a sentence: only count when they are the whole reply.
  var WEAK_WORDS = toSet('ha p a');
  // Distinct enough to act on before the recogniser has finalised the phrase.
  var EAGER_WORDS = toSet('present absent yeah yep nope haan nahi nahin \u0939\u093e\u0901 \u0939\u093e\u0902 \u0928\u0939\u0940\u0902');

  function toSet(words) {
    var set = {};
    words.split(' ').forEach(function (w) { if (w) set[w] = true; });
    return set;
  }
  function tokenize(text) {
    return String(text || '').toLowerCase()
      .replace(/['\u2019]/g, '')
      .replace(/[^a-z\u0900-\u0963\u0966-\u097f]+/g, ' ')
      .trim().split(' ').filter(Boolean);
  }
  // The last keyword in the phrase wins ("no... present" means present).
  function verdictOf(tokens) {
    var verdict = null;
    var whole = tokens.length === 1;
    for (var i = 0; i < tokens.length; i++) {
      var t = tokens[i];
      var nextT = tokens[i + 1];
      if (t === 'not' && (nextT === 'here' || nextT === 'present')) { verdict = 'absent'; i++; continue; }
      if (WEAK_WORDS[t] && !whole) continue;
      if (PRESENT_WORDS[t]) verdict = 'present';
      else if (ABSENT_WORDS[t]) verdict = 'absent';
    }
    return verdict;
  }
  function judgeResult(res) {
    var n = Math.min(res.length || 0, 3);
    for (var a = 0; a < n; a++) {
      var alt = res[a];
      if (!alt) continue;
      var tokens = tokenize(alt.transcript);
      if (!tokens.length) continue;
      if (!res.isFinal) {
        if (a > 0) break;
        var confident = (alt.confidence || 0) >= 0.85 || (tokens.length === 1 && EAGER_WORDS[tokens[0]]);
        if (!confident) break;
      }
      var v = verdictOf(tokens);
      if (v) return { status: v, text: alt.transcript };
    }
    return null;
  }

  function voiceProblem() {
    if (!Recognition) {
      return {
        title: 'Voice roll call isn\u2019t available here',
        text: 'This browser can\u2019t recognise speech. Voice works in Chrome, Edge and Safari. Swipe mode is just as quick.',
        swipe: true, retry: false
      };
    }
    if (window.isSecureContext === false) {
      return {
        title: 'Voice needs a secure connection',
        text: 'Browsers only allow the microphone on pages served over HTTPS. Open the site over HTTPS, or use Swipe mode.',
        swipe: true, retry: false
      };
    }
    return null;
  }
  function voiceActive() {
    return state.open && state.mode === 'voice' && state.phase === 'cards' && !voice.paused;
  }

  // Stop listening and speaking. Bumping `gen` makes stale callbacks no-ops.
  function voiceHalt() {
    voice.gen++;
    clearTimeout(voice.restartTimer);
    clearTimeout(voice.speakTimer);
    stopRecognition();
    if (synth && (voice.speaking || synth.speaking || synth.pending)) {
      try { synth.cancel(); } catch (e) { /* ignore */ }
    }
    voice.speaking = false;
    voice.utterance = null;
    setMicUI();
  }
  function stopRecognition() {
    var r = voice.rec;
    voice.rec = null;
    voice.live = false;
    if (r) { try { r.abort(); } catch (e) { /* already stopped */ } }
  }
  function pauseVoice(note) {
    voice.paused = true;
    voice.pauseNote = note || '';
    voiceHalt();
  }
  function toggleMic() {
    if (state.mode !== 'voice' || state.phase !== 'cards') return;
    if (voice.paused) {
      voice.paused = false;
      voice.pauseNote = '';
      voice.quickEnds = 0;
      voice.netErrors = 0;
      voiceStudent();
    } else {
      pauseVoice('');
      announce('Listening paused.');
    }
  }

  // Read the current name (if wanted), then listen for the answer.
  function voiceStudent() {
    voiceHalt();
    if (!voiceActive()) return;
    var s = current();
    if (!s) return;
    setTranscript('', true, null);
    var gen = voice.gen;
    if (readAloud && synth) speak(s.name, function () { if (gen === voice.gen) listen(); });
    else listen();
  }

  function pickVoice() {
    try {
      var voices = synth.getVoices() || [];
      for (var i = 0; i < voices.length; i++) {
        if (String(voices[i].lang || '').replace('_', '-').toLowerCase() === 'en-in') return voices[i];
      }
    } catch (e) { /* voices unavailable */ }
    return null;
  }

  function speak(text, then) {
    var gen = voice.gen;
    var finished = false;
    function done() {
      if (finished) return;
      finished = true;
      if (gen !== voice.gen) return;
      clearTimeout(voice.speakTimer);
      voice.speaking = false;
      voice.utterance = null;
      setMicUI();
      then();
    }
    try {
      var u = new window.SpeechSynthesisUtterance(text);
      u.lang = 'en-IN';
      var v = pickVoice();
      if (v) u.voice = v;
      u.rate = 1;
      u.onend = done;
      u.onerror = done;
      voice.utterance = u;   // keep a reference so the end event isn't lost to GC
      voice.speaking = true;
      setMicUI();
      if (synth.paused) synth.resume();
      synth.speak(u);
      // Some engines never fire `end`; don't wait forever.
      voice.speakTimer = setTimeout(function () {
        if (gen !== voice.gen) return;
        try { synth.cancel(); } catch (e) { /* ignore */ }
        done();
      }, 1800 + text.length * 120);
    } catch (e) {
      voice.speaking = false;
      voice.utterance = null;
      then();
    }
  }

  function listen() {
    if (!voiceActive() || voice.rec || voice.speaking) return;
    var r;
    try { r = new Recognition(); } catch (e) {
      showMessage(voiceProblem() || {
        title: 'Voice roll call couldn\u2019t start',
        text: 'Speech recognition failed to start in this browser. Swipe mode works everywhere.',
        swipe: true, retry: true
      });
      return;
    }
    r.lang = 'en-IN';
    r.interimResults = true;
    r.continuous = true;
    r.maxAlternatives = 3;
    r.onstart = function () {
      if (r !== voice.rec) return;
      voice.live = true;
      voice.everLive = true;
      setMicUI();
    };
    r.onresult = function (e) { if (r === voice.rec) onResult(e); };
    r.onerror = function (e) { if (r === voice.rec) onRecError(e); };
    r.onend = function () {
      if (r !== voice.rec) return;
      voice.rec = null;
      voice.live = false;
      setMicUI();
      if (voiceActive() && !voice.speaking) scheduleRestart();
    };
    voice.rec = r;
    voice.live = false;
    voice.startedAt = Date.now();
    try { r.start(); } catch (err) {
      voice.rec = null;
      scheduleRestart();
      return;
    }
    setMicUI();
  }

  function scheduleRestart() {
    clearTimeout(voice.restartTimer);
    var quick = Date.now() - voice.startedAt < 1500;
    voice.quickEnds = quick ? voice.quickEnds + 1 : 0;
    if (voice.quickEnds > 6) {
      pauseVoice('The microphone keeps stopping. Tap the mic to try again.');
      return;
    }
    var delay = quick ? Math.min(3000, 200 * Math.pow(2, voice.quickEnds)) : 150;
    var gen = voice.gen;
    voice.restartTimer = setTimeout(function () { if (gen === voice.gen) listen(); }, delay);
  }

  function onRecError(e) {
    var code = e && e.error;
    if (code === 'not-allowed' || code === 'service-not-allowed') {
      showMessage({
        title: 'Microphone access is blocked',
        text: 'Allow the microphone for this site (look for the camera or lock icon in the address bar), then try again. Or carry on with Swipe mode.',
        swipe: true, retry: true
      });
    } else if (code === 'audio-capture') {
      showMessage({
        title: 'No microphone found',
        text: 'Connect or enable a microphone and try again, or use Swipe mode.',
        swipe: true, retry: true
      });
    } else if (code === 'language-not-supported') {
      showMessage({
        title: 'Voice isn\u2019t supported for this language',
        text: 'This browser can\u2019t recognise English (India). Swipe mode works everywhere.',
        swipe: true, retry: false
      });
    } else if (code === 'network') {
      voice.netErrors++;
      if (voice.netErrors >= 3) {
        showMessage({
          title: 'Speech service unavailable',
          text: 'This browser needs an internet connection to recognise speech. Check your connection and try again, or use Swipe mode.',
          swipe: true, retry: true
        });
      }
    }
    // 'no-speech', 'aborted' and the rest: `end` follows and we simply listen again.
  }

  function onResult(e) {
    voice.quickEnds = 0;
    voice.netErrors = 0;
    var results = e.results;
    if (!results || !results.length) return;
    var latest = null;
    var hit = null;
    for (var i = results.length - 1; i >= (e.resultIndex || 0); i--) {
      var res = results[i];
      if (!res || !res.length) continue;
      if (!latest) latest = { text: res[0].transcript, final: res.isFinal };
      hit = judgeResult(res);
      if (hit) break;
    }
    if (hit) { heard(hit.status, hit.text); return; }
    if (latest) setTranscript(latest.text, latest.final, null);
  }

  function heard(status, text) {
    stopRecognition();
    voice.gen++;
    clearTimeout(voice.restartTimer);
    setTranscript(text, true, status);
    decide(status, { hold: VOICE_HOLD_MS });
  }

  function setTranscript(text, final, status) {
    if (!transcriptEl) return;
    text = clean(text);
    if (!text) {
      transcriptEl.className = 'rc-transcript is-hint';
      transcriptEl.textContent = 'Say \u201cpresent\u201d or \u201cabsent\u201d';
      return;
    }
    transcriptEl.className = 'rc-transcript' + (final ? '' : ' is-interim') + (status ? ' is-' + status : '');
    transcriptEl.textContent = '\u201c' + text + '\u201d';
  }

  function setMicUI() {
    if (!micBtn) return;
    var st;
    if (state.mode !== 'voice' || !state.open) st = 'paused';
    else if (voice.paused) st = 'paused';
    else if (voice.speaking) st = 'speaking';
    else st = 'listening';
    micBtn.className = 'rc-mic is-' + st + (st === 'listening' && voice.live ? ' is-live' : '');
    if (micIcon) {
      micIcon.className = 'fas ' + (st === 'paused' ? 'fa-microphone-slash' : st === 'speaking' ? 'fa-volume-up' : 'fa-microphone');
    }
    micBtn.setAttribute('aria-pressed', st === 'paused' ? 'false' : 'true');
    micBtn.setAttribute('aria-label', st === 'paused' ? 'Resume listening' : 'Pause listening');
    if (voiceStatusEl) {
      voiceStatusEl.textContent =
        st === 'paused' ? (voice.pauseNote || 'Paused \u2014 tap the mic to resume') :
        st === 'speaking' ? 'Reading the name\u2026' :
        voice.everLive ? 'Listening\u2026' : 'Starting the microphone\u2026';
    }
  }

  // ------------------------------------------------------------ wiring
  each(document.querySelectorAll('[data-rc-launch]'), function (g) { g.hidden = false; });
  if (readBox) readBox.checked = readAloud;
  if (readWrap && !synth) readWrap.hidden = true;
  if (synth) { try { synth.getVoices(); } catch (e) { /* warm-up only */ } }

  document.addEventListener('click', function (e) {
    var b = e.target && e.target.closest ? e.target.closest('[data-rc-open]') : null;
    if (!b || overlay.contains(b)) return;
    e.preventDefault();
    open(b.getAttribute('data-rc-open') === 'voice' ? 'voice' : 'swipe', b);
  });

  overlay.addEventListener('click', function (e) {
    var b = e.target && e.target.closest ? e.target.closest('button') : null;
    if (!b || !overlay.contains(b) || b.disabled) return;
    if (b.hasAttribute('data-rc-close')) close();
    else if (b.hasAttribute('data-rc-mark')) decide(b.getAttribute('data-rc-mark'));
    else if (b.hasAttribute('data-rc-undo')) undo();
    else if (b.hasAttribute('data-rc-skip')) skip();
    else if (b.hasAttribute('data-rc-save')) save();
    else if (b.hasAttribute('data-rc-mic')) toggleMic();
    else if (b.hasAttribute('data-rc-to-swipe')) startMode('swipe');
    else if (b.hasAttribute('data-rc-retry')) startMode('voice');
  });

  if (readBox) {
    readBox.addEventListener('change', function () {
      readAloud = readBox.checked;
      savePref(readAloud);
      if (!readAloud && voice.speaking) {
        voiceHalt();
        listen();
      }
    });
  }

  document.addEventListener('keydown', function (e) {
    if (!state.open) return;
    var k = e.key;
    if (k === 'Escape' || k === 'Esc') { e.preventDefault(); close(); return; }
    if (k === 'Tab') { trapTab(e); return; }
    if (e.altKey) return;
    var mod = e.ctrlKey || e.metaKey;
    var isUndo = (k === 'Backspace' && !mod) || (mod && !e.shiftKey && (k === 'z' || k === 'Z'));
    if (isUndo) {
      if (state.phase !== 'message') { e.preventDefault(); if (!e.repeat) undo(); }
      return;
    }
    if (state.phase !== 'cards' || mod || e.shiftKey) return;
    if (k === 'ArrowRight' || k === 'Right') { e.preventDefault(); if (!e.repeat) decide('present'); }
    else if (k === 'ArrowLeft' || k === 'Left') { e.preventDefault(); if (!e.repeat) decide('absent'); }
  }, true);

  // Keep focus inside the dialog (backup for browsers without `inert`).
  document.addEventListener('focusin', function (e) {
    if (state.open && !overlay.contains(e.target)) {
      var items = focusables();
      (items[0] || dialog).focus();
    }
  });

  document.addEventListener('visibilitychange', function () {
    if (document.hidden && state.open && state.mode === 'voice' && state.phase === 'cards' && !voice.paused) {
      pauseVoice('Paused while the page was in the background \u2014 tap the mic to resume');
    }
  });
  window.addEventListener('pagehide', function () { voiceHalt(); });
})();
