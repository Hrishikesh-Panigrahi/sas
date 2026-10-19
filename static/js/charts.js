/* SAS — small SVG charts for attendance percentages (0–100%).
 *
 * <div class="chart" data-chart="line|columns" data-source="json-script-id"
 *      data-threshold="75" data-label="Week of"></div>
 * Data: [{label, percent, present, total}, ...]. Hover or arrow keys show a tooltip;
 * every value is also in the table view next to the chart.
 */
(function () {
  'use strict';
  var NS = 'http://www.w3.org/2000/svg';
  var C = {
    series: '#2a5bd7', wash: 'rgba(42, 91, 215, .08)', ref: '#d98a0b',
    grid: '#e7eaee', ink: '#3c434d', muted: '#69717d', surface: '#ffffff'
  };

  function node(name, attrs, parent) {
    var n = document.createElementNS(NS, name);
    Object.keys(attrs).forEach(function (k) { n.setAttribute(k, attrs[k]); });
    if (parent) parent.appendChild(n);
    return n;
  }
  function label(parent, x, y, str, attrs) {
    var t = node('text', Object.assign({ x: x, y: y, fill: C.muted, 'font-size': 11 }, attrs || {}), parent);
    t.textContent = str;
    return t;
  }

  function setup(host, height) {
    host.querySelectorAll('svg, .chart-tip').forEach(function (n) { n.remove(); });
    var W = Math.max(host.clientWidth, 240);
    var svg = node('svg', { width: W, height: height, viewBox: '0 0 ' + W + ' ' + height,
                            role: 'img', tabindex: 0, 'aria-label': host.getAttribute('aria-label') || '' }, host);
    var tip = document.createElement('div');
    tip.className = 'chart-tip';
    tip.hidden = true;
    host.appendChild(tip);
    return { svg: svg, tip: tip, W: W, H: height };
  }

  function showTip(c, host, x, y, value, caption) {
    c.tip.textContent = '';
    var v = document.createElement('strong');
    v.textContent = value;
    var s = document.createElement('span');
    s.textContent = caption;
    c.tip.appendChild(v);
    c.tip.appendChild(s);
    c.tip.hidden = false;
    var w = c.tip.offsetWidth;
    c.tip.style.left = Math.max(0, Math.min(c.W - w, x - w / 2)) + 'px';
    c.tip.style.top = Math.max(0, y - c.tip.offsetHeight - 12) + 'px';
  }

  function caption(d, prefix) {
    var head = prefix ? prefix + ' ' + d.label : d.label;
    return d.total ? head + ' · ' + d.present + ' of ' + d.total : head + ' · no lectures';
  }

  function axes(c, m, threshold) {
    var plotH = c.H - m.t - m.b;
    var y = function (v) { return m.t + (1 - v / 100) * plotH; };
    [0, 25, 50, 75, 100].forEach(function (v) {
      node('line', { x1: m.l, x2: c.W - m.r, y1: y(v), y2: y(v), stroke: C.grid, 'stroke-width': 1 }, c.svg);
      label(c.svg, m.l - 8, y(v) + 4, v + '%', { 'text-anchor': 'end' });
    });
    if (threshold) {
      node('line', { x1: m.l, x2: c.W - m.r, y1: y(threshold), y2: y(threshold),
                     stroke: C.ref, 'stroke-width': 1.5 }, c.svg);
      label(c.svg, c.W - m.r + 6, y(threshold) + 4, threshold + '%', { fill: C.ref, 'font-weight': 600 });
    }
    return y;
  }

  function line(host, data, opts) {
    var c = setup(host, 220);
    var m = { t: 14, r: 40, b: 26, l: 40 };
    var y = axes(c, m, opts.threshold);
    var n = data.length;
    var x = function (i) { return n === 1 ? (m.l + c.W - m.r) / 2 : m.l + i * (c.W - m.l - m.r) / (n - 1); };
    var every = Math.ceil(n / Math.max(1, Math.floor((c.W - m.l - m.r) / 56)));
    data.forEach(function (d, i) {
      if (i % every === 0 || i === n - 1) {
        label(c.svg, x(i), c.H - 6, d.label, { 'text-anchor': 'middle' });
      }
    });

    // Draw each run of weeks that have data; weeks without lectures leave a gap.
    var runs = [], run = [];
    data.forEach(function (d, i) {
      if (d.percent === null || d.percent === undefined) { if (run.length) runs.push(run); run = []; }
      else run.push(i);
    });
    if (run.length) runs.push(run);
    runs.forEach(function (r) {
      var pts = r.map(function (i) { return x(i) + ',' + y(data[i].percent); });
      if (r.length > 1) {
        node('path', { d: 'M' + x(r[0]) + ',' + y(0) + ' L' + pts.join(' L') + ' L' + x(r[r.length - 1]) + ',' + y(0) + ' Z',
                       fill: C.wash, stroke: 'none' }, c.svg);
        node('path', { d: 'M' + pts.join(' L'), fill: 'none', stroke: C.series, 'stroke-width': 2,
                       'stroke-linejoin': 'round', 'stroke-linecap': 'round' }, c.svg);
      }
    });
    var markers = data.map(function (d, i) {
      if (d.percent === null || d.percent === undefined) return null;
      return node('circle', { cx: x(i), cy: y(d.percent), r: 4, fill: C.series, stroke: C.surface, 'stroke-width': 2 }, c.svg);
    });
    var last = -1;
    data.forEach(function (d, i) { if (d.percent !== null && d.percent !== undefined) last = i; });
    if (last >= 0) {
      label(c.svg, x(last), y(data[last].percent) - 10, data[last].percent + '%',
            { 'text-anchor': 'middle', fill: C.ink, 'font-weight': 700, 'font-size': 12 });
    }

    var cross = node('line', { y1: m.t, y2: c.H - m.b, stroke: C.muted, 'stroke-width': 1, visibility: 'hidden' }, c.svg);
    var active = -1;
    function focus(i) {
      active = i;
      var d = data[i];
      cross.setAttribute('x1', x(i));
      cross.setAttribute('x2', x(i));
      cross.setAttribute('visibility', 'visible');
      markers.forEach(function (mk, j) { if (mk) mk.setAttribute('r', j === i ? 6 : 4); });
      var top = d.percent === null || d.percent === undefined ? y(50) : y(d.percent);
      showTip(c, host, x(i), top, d.percent === null || d.percent === undefined ? '-' : d.percent + '%',
              caption(d, opts.prefix));
    }
    function blur() {
      active = -1;
      cross.setAttribute('visibility', 'hidden');
      markers.forEach(function (mk) { if (mk) mk.setAttribute('r', 4); });
      c.tip.hidden = true;
    }
    var hit = node('rect', { x: m.l - 12, y: 0, width: c.W - m.l - m.r + 24, height: c.H, fill: 'transparent' }, c.svg);
    hit.addEventListener('pointermove', function (e) {
      var px = e.clientX - c.svg.getBoundingClientRect().left;
      var best = 0;
      data.forEach(function (d, i) { if (Math.abs(x(i) - px) < Math.abs(x(best) - px)) best = i; });
      focus(best);
    });
    hit.addEventListener('pointerleave', blur);
    keyboard(c.svg, n, function () { return active; }, focus, blur);
  }

  function columns(host, data, opts) {
    var c = setup(host, 220);
    var m = { t: 22, r: 40, b: 26, l: 40 };
    var y = axes(c, m, opts.threshold);
    var n = Math.max(data.length, 1);
    var band = (c.W - m.l - m.r) / n;
    var bw = Math.min(24, band * 0.6);
    var bars = data.map(function (d, i) {
      var cx = m.l + band * (i + 0.5);
      label(c.svg, cx, c.H - 6, d.short || d.label, { 'text-anchor': 'middle' });
      var g = node('g', {}, c.svg);
      if (d.percent !== null && d.percent !== undefined) {
        var top = y(d.percent), base = y(0), h = base - top, r = Math.min(4, h / 2, bw / 2), x0 = cx - bw / 2;
        node('path', { d: 'M' + x0 + ',' + base + ' L' + x0 + ',' + (top + r) + ' Q' + x0 + ',' + top + ' ' + (x0 + r) + ',' + top +
                          ' L' + (x0 + bw - r) + ',' + top + ' Q' + (x0 + bw) + ',' + top + ' ' + (x0 + bw) + ',' + (top + r) +
                          ' L' + (x0 + bw) + ',' + base + ' Z', fill: C.series }, g);
        label(g, cx, top - 6, d.percent + '%', { 'text-anchor': 'middle', fill: C.ink, 'font-weight': 600 });
      }
      node('rect', { x: m.l + band * i, y: m.t, width: band, height: c.H - m.t - m.b, fill: 'transparent' }, g);
      g.addEventListener('pointerenter', function () { focus(i); });
      g.addEventListener('pointerleave', blur);
      return g;
    });
    var active = -1;
    function focus(i) {
      active = i;
      bars.forEach(function (b, j) { b.setAttribute('opacity', j === i || i < 0 ? 1 : 0.55); });
      var d = data[i];
      var top = d.percent === null || d.percent === undefined ? y(50) : y(d.percent);
      showTip(c, host, m.l + band * (i + 0.5), top, d.percent === null ? '-' : d.percent + '%', caption(d, opts.prefix));
    }
    function blur() {
      active = -1;
      bars.forEach(function (b) { b.setAttribute('opacity', 1); });
      c.tip.hidden = true;
    }
    keyboard(c.svg, data.length, function () { return active; }, focus, blur);
  }

  function keyboard(svg, n, current, focus, blur) {
    svg.addEventListener('keydown', function (e) {
      if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
      e.preventDefault();
      var i = current();
      i = i < 0 ? 0 : Math.max(0, Math.min(n - 1, i + (e.key === 'ArrowRight' ? 1 : -1)));
      focus(i);
    });
    svg.addEventListener('blur', blur);
  }

  function render() {
    document.querySelectorAll('[data-chart]').forEach(function (host) {
      var source = document.getElementById(host.getAttribute('data-source'));
      if (!source) return;
      var data = JSON.parse(source.textContent);
      var opts = { threshold: +host.getAttribute('data-threshold') || 0, prefix: host.getAttribute('data-label') || '' };
      (host.getAttribute('data-chart') === 'line' ? line : columns)(host, data, opts);
    });
  }

  var timer;
  window.addEventListener('resize', function () { clearTimeout(timer); timer = setTimeout(render, 150); });
  render();
})();
