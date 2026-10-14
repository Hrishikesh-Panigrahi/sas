/* SAS — timetable generator page.
 * The page edits `config` (week shape, course frequencies, rules); the server
 * solves it and returns a week, which is drawn as a grid. Names are inserted with
 * textContent only.
 */
(function () {
  'use strict';
  var root = document.getElementById('generator');
  if (!root) return;

  var config = JSON.parse(document.getElementById('gen-config').textContent);
  var STANDARD = clone(config.periods);
  var ALL_DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  var COLOURS = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#4a3aa7', '#e34948'];
  var seed = 0;
  var busy = false;

  var teacherName = {};
  var courseName = {};
  config.courses.forEach(function (c) { teacherName[c.teacher_id] = c.teacher; courseName[c.course_id] = c.name; });

  // ------------------------------------------------------------ helpers
  function clone(x) { return JSON.parse(JSON.stringify(x)); }
  function q(sel) { return root.querySelector(sel); }
  function h(tag, attrs, children) {
    var el = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      if (k === 'text') el.textContent = attrs[k];
      else if (k === 'class') el.className = attrs[k];
      else if (k === 'style') el.setAttribute('style', attrs[k]);
      else if (attrs[k] !== false && attrs[k] !== null && attrs[k] !== undefined) el.setAttribute(k, attrs[k] === true ? '' : attrs[k]);
    });
    (children || []).forEach(function (c) { if (c) el.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return el;
  }
  function icon(name) { return h('i', { class: name, 'aria-hidden': 'true' }); }
  function short(day) { return day.slice(0, 3); }
  function tint(hex, alpha) {
    var n = parseInt(hex.slice(1), 16);
    return 'rgba(' + (n >> 16) + ',' + ((n >> 8) & 255) + ',' + (n & 255) + ',' + alpha + ')';
  }
  function csrf() {
    var el = document.querySelector('[name=csrfmiddlewaretoken]');
    return el ? el.value : '';
  }
  function post(url, body) {
    return fetch(url, {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
      body: JSON.stringify(body)
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (data) {
        if (!r.ok) throw new Error(data.error || 'Something went wrong. Please try again.');
        return data;
      });
    });
  }
  function showError(message) {
    var box = q('.gen-error');
    box.hidden = !message;
    box.textContent = message || '';
  }

  // ------------------------------------------------------------ week
  function renderDays() {
    var box = q('[data-days]');
    box.textContent = '';
    ALL_DAYS.forEach(function (day) {
      var on = config.days.indexOf(day) !== -1;
      var b = h('button', { type: 'button', class: 'chip' + (on ? ' on' : ''), 'aria-pressed': on ? 'true' : 'false', text: short(day) });
      b.addEventListener('click', function () {
        if (on && config.days.length === 1) return;
        config.days = on ? config.days.filter(function (d) { return d !== day; })
                         : ALL_DAYS.filter(function (d) { return d === day || config.days.indexOf(d) !== -1; });
        renderDays();
        renderBlockForm();
      });
      box.appendChild(b);
    });
  }

  function renderPeriods() {
    var box = q('[data-periods]');
    box.textContent = '';
    config.periods.sort(function (a, b) { return a.start < b.start ? -1 : 1; });
    config.periods.forEach(function (p, i) {
      var prev = config.periods[i - 1];
      if (prev && prev.end < p.start) {
        box.appendChild(h('div', { class: 'gen-break', text: (minutes(p.start) - minutes(prev.end) >= 30 ? 'Lunch' : 'Break') + ' · ' + prev.end + '–' + p.start }));
      }
      var start = h('input', { type: 'time', class: 'form-control', value: p.start, 'aria-label': 'Period ' + (i + 1) + ' start' });
      var end = h('input', { type: 'time', class: 'form-control', value: p.end, 'aria-label': 'Period ' + (i + 1) + ' end' });
      var remove = h('button', { type: 'button', class: 'btn-link-muted', title: 'Remove period', 'aria-label': 'Remove period ' + (i + 1) }, [icon('fas fa-times')]);
      start.addEventListener('change', function () { p.start = start.value; renderPeriods(); });
      end.addEventListener('change', function () { p.end = end.value; renderPeriods(); });
      remove.addEventListener('click', function () {
        if (config.periods.length > 1) { config.periods.splice(i, 1); renderPeriods(); renderRuleSelects(); }
      });
      box.appendChild(h('div', { class: 'gen-period' }, [h('span', { class: 'gen-period-n', text: String(i + 1) }), start, h('span', { text: '–' }), end, remove]));
    });
  }
  function minutes(t) { var p = t.split(':'); return (+p[0]) * 60 + (+p[1]); }
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function addMinutes(t, m) { var v = minutes(t) + m; return pad(Math.floor(v / 60) % 24) + ':' + pad(v % 60); }

  // ------------------------------------------------------------ courses
  function stepper(label, value, min, max, onChange) {
    var out = h('span', { class: 'stepper-value', text: String(value), 'aria-live': 'polite' });
    var minus = h('button', { type: 'button', class: 'stepper-btn', 'aria-label': 'Fewer ' + label.toLowerCase(), disabled: value <= min }, [icon('fas fa-minus')]);
    var plus = h('button', { type: 'button', class: 'stepper-btn', 'aria-label': 'More ' + label.toLowerCase(), disabled: value >= max }, [icon('fas fa-plus')]);
    minus.addEventListener('click', function () { onChange(Math.max(min, value - 1)); });
    plus.addEventListener('click', function () { onChange(Math.min(max, value + 1)); });
    return h('div', { class: 'gen-control' }, [h('span', { class: 'gen-control-label', text: label }), h('div', { class: 'stepper' }, [minus, out, plus])]);
  }

  function renderCourses() {
    var box = q('[data-courses]');
    box.textContent = '';
    config.courses.forEach(function (c, i) {
      var colour = COLOURS[i % COLOURS.length];
      var controls = [
        stepper('Lectures / week', c.lectures, 0, 8, function (v) { c.lectures = v; renderCourses(); }),
        stepper('Labs / batch', c.labs, 0, 4, function (v) {
          c.labs = v;
          if (v && !c.batches.length) c.batches = ['A', 'B'];
          renderCourses();
        })
      ];
      if (c.labs) {
        var len = h('select', { class: 'custom-select custom-select-sm', 'aria-label': 'Lab length for ' + c.name });
        [1, 2, 3, 4].forEach(function (n) { len.appendChild(h('option', { value: n, selected: n === c.lab_length, text: n + ' period' + (n > 1 ? 's' : '') })); });
        len.addEventListener('change', function () { c.lab_length = +len.value; });
        var chips = h('div', { class: 'gen-batches', role: 'group', 'aria-label': 'Lab batches for ' + c.name });
        ['A', 'B', 'C'].forEach(function (b) {
          var on = c.batches.indexOf(b) !== -1;
          var chip = h('button', { type: 'button', class: 'chip chip-sm' + (on ? ' on' : ''), 'aria-pressed': on ? 'true' : 'false', text: b });
          chip.addEventListener('click', function () {
            c.batches = on ? c.batches.filter(function (x) { return x !== b; }) : c.batches.concat([b]).sort();
            renderCourses();
          });
          chips.appendChild(chip);
        });
        controls.push(h('div', { class: 'gen-control' }, [h('span', { class: 'gen-control-label', text: 'Length' }), len]));
        controls.push(h('div', { class: 'gen-control' }, [h('span', { class: 'gen-control-label', text: 'Batches' }), chips]));
      }
      var off = !c.lectures && !c.labs;
      box.appendChild(h('div', { class: 'gen-course' + (off ? ' is-off' : ''), style: '--c:' + colour }, [
        h('div', { class: 'gen-course-head' }, [
          h('span', { class: 'swatch', style: 'background:' + colour, 'aria-hidden': 'true' }),
          h('div', { class: 'min-w-0' }, [
            h('div', { class: 'fw-600 text-truncate', text: c.name }),
            h('div', { class: 'small text-muted text-truncate', text: c.code + ' · ' + c.teacher + (off ? ' · not scheduled' : '') })
          ])
        ]),
        h('div', { class: 'gen-course-controls' }, controls)
      ]));
    });
  }

  // ------------------------------------------------------------ rules
  function renderRuleSelects() {
    var maxDay = q('[data-rule="max_periods_per_day"]');
    maxDay.textContent = '';
    maxDay.appendChild(h('option', { value: 0, text: 'No limit' }));
    for (var n = 2; n <= config.periods.length; n++) {
      maxDay.appendChild(h('option', { value: n, text: 'At most ' + n, selected: config.rules.max_periods_per_day === n }));
    }
    var maxRow = q('[data-rule="max_consecutive"]');
    maxRow.textContent = '';
    for (var k = 1; k <= Math.min(6, config.periods.length); k++) {
      maxRow.appendChild(h('option', { value: k, text: k + ' period' + (k > 1 ? 's' : ''), selected: config.rules.max_consecutive === k }));
    }
    q('[data-rule="avoid_first_period"]').checked = !!config.rules.avoid_first_period;
    q('[data-rule="avoid_last_period"]').checked = !!config.rules.avoid_last_period;
  }
  root.addEventListener('change', function (e) {
    var key = e.target.getAttribute('data-rule');
    if (!key) return;
    config.rules[key] = e.target.type === 'checkbox' ? e.target.checked : +e.target.value;
  });

  function ruleItems() {
    var r = config.rules, items = [];
    r.teacher_unavailable.forEach(function (b, i) {
      items.push({ icon: 'fas fa-user-slash', text: (teacherName[b.teacher_id] || 'Teacher') + ' unavailable · ' + short(b.day) + ' ' + b.start + '–' + b.end,
                   remove: function () { r.teacher_unavailable.splice(i, 1); } });
    });
    r.class_blocked.forEach(function (b, i) {
      items.push({ icon: 'fas fa-ban', text: 'Class free · ' + short(b.day) + ' ' + b.start + '–' + b.end,
                   remove: function () { r.class_blocked.splice(i, 1); } });
    });
    r.avoid_days.forEach(function (a, i) {
      items.push({ icon: 'far fa-calendar-times', text: 'Keep ' + (courseName[a.course_id] || 'course') + ' off ' + a.days.map(short).join(', '),
                   remove: function () { r.avoid_days.splice(i, 1); } });
    });
    r.preferred_time.forEach(function (p, i) {
      items.push({ icon: p.time === 'morning' ? 'fas fa-sun' : 'fas fa-cloud-sun', text: (courseName[p.course_id] || 'Course') + ' in the ' + p.time + 's',
                   remove: function () { r.preferred_time.splice(i, 1); } });
    });
    return items;
  }

  function renderRules() {
    var list = q('[data-rules]');
    list.textContent = '';
    var items = ruleItems();
    if (!items.length) {
      list.appendChild(h('li', { class: 'gen-rule-empty', text: 'None yet. Ask the assistant above, or block a time by hand below.' }));
    }
    items.forEach(function (it) {
      var x = h('button', { type: 'button', class: 'btn-link-muted', 'aria-label': 'Remove rule: ' + it.text }, [icon('fas fa-times')]);
      x.addEventListener('click', function () { it.remove(); renderRules(); });
      list.appendChild(h('li', {}, [icon(it.icon), h('span', { text: it.text }), x]));
    });
  }

  function renderBlockForm() {
    var who = q('[data-block="who"]');
    who.textContent = '';
    who.appendChild(h('option', { value: '', text: 'Whole class' }));
    Object.keys(teacherName).forEach(function (id) { who.appendChild(h('option', { value: id, text: teacherName[id] })); });
    var day = q('[data-block="day"]');
    day.textContent = '';
    config.days.forEach(function (d) { day.appendChild(h('option', { value: d, text: d })); });
  }

  // ------------------------------------------------------------ assistant
  function renderAssist(result) {
    var box = q('.gen-assist-result');
    box.textContent = '';
    if (result.notice) box.appendChild(h('div', { class: 'small text-warning mb-1', text: result.notice }));
    result.understood.forEach(function (t) {
      box.appendChild(h('div', { class: 'gen-understood' }, [icon('fas fa-check'), h('span', { text: t })]));
    });
    result.unrecognized.forEach(function (t) {
      box.appendChild(h('div', { class: 'gen-unrecognized' }, [icon('fas fa-question-circle'), h('span', { text: 'Not sure what to do with "' + t + '". Try rephrasing, or add it by hand.' })]));
    });
  }

  function mergeAssist(r) {
    var rules = config.rules;
    rules.teacher_unavailable = rules.teacher_unavailable.concat(r.teacher_unavailable);
    rules.class_blocked = rules.class_blocked.concat(r.class_blocked);
    rules.avoid_days = rules.avoid_days.concat(r.avoid_days);
    rules.preferred_time = rules.preferred_time.concat(r.preferred_time);
    r.lectures_per_week.forEach(function (l) {
      config.courses.forEach(function (c) { if (c.course_id === l.course_id) c.lectures = l.count; });
    });
    if (r.max_periods_per_day) rules.max_periods_per_day = r.max_periods_per_day;
    if (r.max_consecutive) rules.max_consecutive = r.max_consecutive;
    if (r.avoid_first_period !== 'unchanged') rules.avoid_first_period = r.avoid_first_period === 'yes';
    if (r.avoid_last_period !== 'unchanged') rules.avoid_last_period = r.avoid_last_period === 'yes';
    renderCourses();
    renderRuleSelects();
    renderRules();
  }

  // ------------------------------------------------------------ result
  function renderResult(r, used) {
    q('[data-empty]').hidden = true;
    q('[data-result]').hidden = false;
    q('[data-action="variation"]').hidden = false;

    var placed = r.slots.length, total = placed + r.unplaced.length;
    var level = r.quality >= 80 ? 'good' : r.quality >= 60 ? 'ok' : 'poor';
    var quality = q('[data-quality]');
    quality.hidden = false;
    quality.className = 'gen-quality ' + level;
    quality.textContent = '';
    quality.appendChild(h('span', { class: 'gen-quality-score', text: String(r.quality) }));
    quality.appendChild(h('span', { class: 'gen-quality-text' }, [
      h('strong', { text: level === 'good' ? 'Great fit' : level === 'ok' ? 'Workable' : 'Needs attention' }),
      h('span', { text: placed + ' of ' + total + ' sessions placed' })
    ]));

    var hl = q('[data-highlights]');
    hl.textContent = '';
    r.highlights.forEach(function (t, i) {
      var warn = i === 0 && r.unplaced.length;
      hl.appendChild(h('li', { class: warn ? 'warn' : '' }, [icon(warn ? 'fas fa-exclamation-triangle' : 'fas fa-check'), h('span', { text: t })]));
    });

    var un = q('[data-unplaced]');
    un.textContent = '';
    un.hidden = !r.unplaced.length;
    if (r.unplaced.length) {
      un.appendChild(h('div', { class: 'fw-600 mb-1', text: "Couldn't place" }));
      var ul = h('ul');
      r.unplaced.forEach(function (s) {
        ul.appendChild(h('li', {}, [h('strong', { text: s.course + (s.kind === 'Lab' ? ' lab' + (s.batch !== 'All' ? ' (batch ' + s.batch + ')' : '') : ' lecture') + ': ' }), h('span', { text: s.reason })]));
      });
      un.appendChild(ul);
    }

    drawGrid(r, used);
    drawLegend(r);
    drawStats(r);

    var existing = +root.getAttribute('data-existing');
    q('[data-apply-bar]').hidden = false;
    q('[data-apply-note]').textContent = existing
      ? 'Replaces the ' + existing + ' slot' + (existing === 1 ? '' : 's') + ' in ' + root.getAttribute('data-class') + "'s current timetable."
      : root.getAttribute('data-class') + " doesn't have a timetable yet.";
  }

  function drawGrid(r, used) {
    var grid = q('[data-grid]');
    grid.textContent = '';
    var days = used.days, periods = used.periods;
    var lanes = [];
    r.slots.forEach(function (s) { if (s.batch !== 'All' && lanes.indexOf(s.batch) === -1) lanes.push(s.batch); });
    lanes.sort();
    var L = Math.max(1, lanes.length);

    var rows = ['auto'], rowOf = [], line = 2;
    periods.forEach(function (p, i) {
      var prev = periods[i - 1];
      if (prev && prev.end < p.start) { rows.push('22px'); line++; }
      rows.push('minmax(66px, auto)');
      rowOf[i] = line++;
    });
    grid.style.gridTemplateRows = rows.join(' ');
    grid.style.gridTemplateColumns = '64px repeat(' + (days.length * L) + ', minmax(' + (L > 1 ? 74 : 130) + 'px, 1fr))';

    grid.appendChild(h('div', { class: 'gen-corner', style: 'grid-row:1;grid-column:1' }));
    days.forEach(function (d, di) {
      var col = 2 + di * L;
      grid.appendChild(h('div', { class: 'gen-dayhead', style: 'grid-row:1;grid-column:' + col + ' / span ' + L }, [
        h('span', { text: d }),
        L > 1 ? h('span', { class: 'gen-lanes', text: lanes.map(function (b) { return 'Batch ' + b; }).join(' · ') }) : null
      ]));
      grid.appendChild(h('div', { class: 'gen-daycol' + (di % 2 ? ' alt' : ''), style: 'grid-row:2 / ' + line + ';grid-column:' + col + ' / span ' + L }));
    });
    periods.forEach(function (p, i) {
      var prev = periods[i - 1];
      if (prev && prev.end < p.start) {
        grid.appendChild(h('div', { class: 'gen-breakrow', style: 'grid-row:' + (rowOf[i] - 1) + ';grid-column:1 / -1',
                                    text: (minutes(p.start) - minutes(prev.end) >= 30 ? 'Lunch' : 'Break') + ' · ' + prev.end + '–' + p.start }));
      }
      grid.appendChild(h('div', { class: 'gen-time', style: 'grid-row:' + rowOf[i] + ';grid-column:1' }, [
        h('strong', { text: p.start }), h('span', { text: p.end })
      ]));
    });

    r.slots.forEach(function (s) {
      var di = days.indexOf(s.day);
      if (di === -1) return;
      var lane = s.batch === 'All' ? 0 : lanes.indexOf(s.batch);
      var col = 2 + di * L + lane;
      var colour = COLOURS[s.colour % COLOURS.length];
      var label = s.course + ', ' + s.day + ' ' + s.start + ' to ' + s.end + (s.kind === 'Lab' ? ', lab' + (s.batch !== 'All' ? ' batch ' + s.batch : '') : '') + ', ' + s.teacher;
      // In a narrow batch lane the course code stands in for the full name.
      var lane = s.batch !== 'All' && L > 1;
      grid.appendChild(h('div', {
        class: 'gen-block' + (s.kind === 'Lab' ? ' lab' : '') + (lane ? ' lane' : ''),
        style: 'grid-row:' + rowOf[s.period] + ' / span ' + s.length + ';grid-column:' + col + ' / span ' + (s.batch === 'All' ? L : 1) +
               ';--c:' + colour + ';--t:' + tint(colour, 0.12),
        title: label, 'aria-label': label, role: 'note'
      }, [
        h('div', { class: 'gen-block-time', text: s.start + '–' + s.end }),
        h('div', { class: 'gen-block-title', text: lane ? s.code : s.course }),
        h('div', { class: 'gen-block-meta' }, [
          lane ? null : h('span', { text: s.code }),
          s.kind === 'Lab' ? h('span', { class: 'gen-tag', text: s.batch === 'All' ? 'Lab' : 'Lab · ' + s.batch }) : null
        ]),
        h('div', { class: 'gen-block-teacher', text: lane ? s.teacher.split(' ')[0] : s.teacher })
      ]));
    });
  }

  function drawLegend(r) {
    var box = q('[data-legend]');
    box.textContent = '';
    var seen = {};
    r.slots.forEach(function (s) {
      if (seen[s.course_id]) return;
      seen[s.course_id] = true;
      box.appendChild(h('span', { class: 'gen-legend-item' }, [
        h('span', { class: 'swatch', style: 'background:' + COLOURS[s.colour % COLOURS.length], 'aria-hidden': 'true' }),
        h('span', { text: s.course })
      ]));
    });
  }

  function drawStats(r) {
    var box = q('[data-stats]');
    box.textContent = '';
    var days = h('div', { class: 'col-md-6' }, [h('div', { class: 'gen-label', text: 'Periods per day' })]);
    r.stats.per_day.forEach(function (d) {
      var pct = Math.round(100 * d.periods / Math.max(1, d.capacity));
      days.appendChild(h('div', { class: 'gen-load' }, [
        h('span', { class: 'gen-load-label', text: short(d.day) }),
        h('div', { class: 'meter-bar neutral' }, [h('span', { style: 'width:' + pct + '%' })]),
        h('span', { class: 'gen-load-value', text: d.periods + ' / ' + d.capacity })
      ]));
    });
    var teachers = h('div', { class: 'col-md-6' }, [h('div', { class: 'gen-label', text: 'Teaching periods per week' })]);
    r.stats.teachers.forEach(function (t) {
      teachers.appendChild(h('div', { class: 'gen-load' }, [
        h('span', { class: 'gen-load-label wide text-truncate', text: t.name }),
        h('span', { class: 'gen-load-value', text: String(t.periods) })
      ]));
    });
    box.appendChild(days);
    box.appendChild(teachers);
  }

  // ------------------------------------------------------------ actions
  function setBusy(on, label) {
    busy = on;
    root.querySelectorAll('[data-action="generate"]').forEach(function (gen) {
      gen.disabled = on;
      gen.querySelector('span').textContent = on ? label : 'Generate timetable';
      gen.querySelector('i').className = on ? 'fas fa-circle-notch fa-spin' : 'fas fa-bolt';
    });
    q('[data-action="variation"]').disabled = on;
    q('[data-result]').classList.toggle('is-refreshing', on);
  }

  function generate() {
    if (busy) return;
    showError('');
    var used = clone(config);
    setBusy(true, 'Generating…');
    post(root.getAttribute('data-run'), { config: used, seed: seed })
      .then(function (r) {
        renderResult(r, used);
        // When the preview sits below the setup, bring the result into view.
        var box = q('.gen-preview').getBoundingClientRect();
        if (box.top > window.innerHeight * 0.6 || box.top < 0) {
          q('.gen-preview').scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
        }
      })
      .catch(function (e) { showError(e.message); })
      .then(function () { setBusy(false); });
  }

  root.addEventListener('click', function (e) {
    var target = e.target.closest('[data-action], [data-example]');
    if (!target) return;
    if (target.hasAttribute('data-example')) {
      var area = q('#gen-ask');
      area.value = (area.value.trim() ? area.value.trim().replace(/\.?$/, '. ') : '') + target.getAttribute('data-example');
      area.focus();
      return;
    }
    var action = target.getAttribute('data-action');
    if (action === 'generate') { seed = 0; generate(); }
    else if (action === 'variation') { seed += 1; generate(); }
    else if (action === 'add-period') {
      var lastP = config.periods[config.periods.length - 1];
      var start = lastP ? lastP.end : '09:00';
      config.periods.push({ start: start, end: addMinutes(start, 60) });
      renderPeriods();
      renderRuleSelects();
    } else if (action === 'reset-periods') {
      config.periods = clone(STANDARD);
      renderPeriods();
      renderRuleSelects();
    } else if (action === 'add-block') {
      var who = q('[data-block="who"]').value, day = q('[data-block="day"]').value;
      var from = q('[data-block="start"]').value, to = q('[data-block="end"]').value;
      if (!from || !to || from >= to) { showError('A blocked time needs a start before its end.'); return; }
      showError('');
      if (who) config.rules.teacher_unavailable.push({ teacher_id: +who, day: day, start: from, end: to });
      else config.rules.class_blocked.push({ day: day, start: from, end: to });
      renderRules();
    } else if (action === 'assist') {
      var text = q('#gen-ask').value.trim();
      if (!text) { q('#gen-ask').focus(); return; }
      target.disabled = true;
      target.lastChild.textContent = 'Reading…';
      post(root.getAttribute('data-assist'), { text: text })
        .then(function (r) {
          mergeAssist(r);
          renderAssist(r);
          if (r.understood.length && !r.unrecognized.length) q('#gen-ask').value = '';
        })
        .catch(function (err) { showError(err.message); })
        .then(function () { target.disabled = false; target.lastChild.textContent = 'Add these rules'; });
    } else if (action === 'apply') {
      var existing = +root.getAttribute('data-existing');
      if (existing && !window.confirm('Replace ' + root.getAttribute('data-class') + "'s current timetable (" + existing + ' slots) with this one?')) return;
      target.disabled = true;
      post(root.getAttribute('data-apply'), {})
        .then(function (r) { window.location.href = r.redirect; })
        .catch(function (err) { showError(err.message); target.disabled = false; });
    }
  });

  renderDays();
  renderPeriods();
  renderCourses();
  renderRuleSelects();
  renderRules();
  renderBlockForm();
})();
