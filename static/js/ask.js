/* SAS: Ask SAS. Each question and its answer is one entry, newest first.
   Answers and tables are inserted with textContent only. */
(function () {
  'use strict';
  var root = document.getElementById('ask');
  if (!root) return;
  var thread = root.querySelector('[data-thread]');
  var form = root.querySelector('[data-form]');
  var input = form.querySelector('input');
  var history = [];
  var busy = false;

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  }
  function csrf() {
    var t = document.querySelector('[name=csrfmiddlewaretoken]');
    return t ? t.value : '';
  }
  function now() {
    var d = new Date();
    return ('0' + d.getHours()).slice(-2) + ':' + ('0' + d.getMinutes()).slice(-2);
  }

  function entry(question) {
    var item = el('article', 'ask-msg bot');
    var head = el('div', 'ask-q');
    var icon = el('i', 'fas fa-search text-muted small');
    icon.setAttribute('aria-hidden', 'true');
    head.appendChild(icon);
    head.appendChild(el('strong', '', question));
    head.appendChild(el('span', 'when', now()));
    var body = el('div', 'ask-bubble');
    item.appendChild(head);
    item.appendChild(body);
    thread.insertBefore(item, thread.firstChild);
    return body;
  }

  function table(t) {
    var card = el('div', 'ask-table');
    card.appendChild(el('div', 'ask-table-title', t.title + (t.count !== undefined ? ' · ' + t.count : '')));
    var wrap = el('div', 'table-responsive');
    var tbl = el('table', 'table table-sm');
    var head = el('thead'), tr = el('tr');
    t.columns.forEach(function (c) { tr.appendChild(el('th', '', String(c))); });
    head.appendChild(tr);
    tbl.appendChild(head);
    var body = el('tbody');
    t.rows.forEach(function (row) {
      var r = el('tr');
      row.forEach(function (v) { r.appendChild(el('td', typeof v === 'number' ? 'tabular' : '', String(v))); });
      body.appendChild(r);
    });
    tbl.appendChild(body);
    wrap.appendChild(tbl);
    card.appendChild(wrap);
    if (t.note) card.appendChild(el('div', 'small text-muted', t.note));
    return card;
  }

  function ask(question) {
    if (busy || !question) return;
    busy = true;
    var welcome = root.querySelector('[data-welcome]');
    if (welcome) welcome.remove();
    var reply = entry(question);
    reply.appendChild(el('div', 'ask-typing', '')).innerHTML = '<span></span><span></span><span></span>';
    input.value = '';
    fetch(root.getAttribute('data-url'), {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
      body: JSON.stringify({ question: question, history: history })
    }).then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    }).then(function (data) {
      reply.textContent = '';
      if (data.notice) reply.appendChild(el('div', 'small text-warning mb-1', data.notice));
      data.answer.split(/\n{2,}/).forEach(function (para) { reply.appendChild(el('p', '', para)); });
      (data.tables || []).forEach(function (t) { if (t.rows && t.rows.length) reply.appendChild(table(t)); });
      history.push({ q: question, a: data.answer });
      history = history.slice(-3);
    }).catch(function () {
      reply.textContent = '';
      reply.appendChild(el('p', 'text-danger mb-0', "Sorry, that didn't work. Please try again."));
    }).then(function () {
      busy = false;
      input.focus({ preventScroll: true });
    });
  }

  form.addEventListener('submit', function (e) { e.preventDefault(); ask(input.value.trim()); });
  root.addEventListener('click', function (e) {
    var chip = e.target.closest('[data-suggestion]');
    if (chip) ask(chip.textContent.trim());
  });
  input.focus();
})();
