/* 中西方美术史 · 交互层（零依赖） */
(function () {
  'use strict';
  var SVGNS = 'http://www.w3.org/2000/svg';
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var el = function (n, a) {
    var e = document.createElement(n);
    for (var k in (a || {})) e.setAttribute(k, a[k]);
    return e;
  };
  /* SVG 元素必须用 createElementNS，否则创建出的是 HTMLUnknownElement（不渲染） */
  var svgEl = function (n, a) {
    var e = document.createElementNS(SVGNS, n);
    for (var k in (a || {})) e.setAttribute(k, a[k]);
    return e;
  };

  var D = DATA || {};
  var SITE = D.site || {};
  var NODES = D.nodes || [];
  var EDGES = D.edges || [];
  var ERAS = D.eras || { china: [], west: [] };
  var ESSAYS = D.essays || [];
  var TERMS = D.terms || [];
  var DAILY = D.daily || [];
  var IMG = D.images || {};
  var POR = D.portraits || {};
  var COPY = D.copy || { nodes: {}, works: {}, eras: {} };
  var TYPE_LABEL = { lineage: '师承', influence: '影响', rival: '对立', milieu: '同代' };

  var byId = {};
  NODES.forEach(function (n) {
    n.year = (n.works && n.works[0] && n.works[0].sortYear) || n.born || ((n.born || 0) + (n.died || 0)) / 2;
    n.yearLabel = yearText(n.works && n.works[0] ? n.works[0].year : n.born);
    byId[n.id] = n;
  });
  var deg = {};
  EDGES.forEach(function (e) {
    if (!byId[e.source] || !byId[e.target]) return;
    deg[e.source] = (deg[e.source] || 0) + 1;
    deg[e.target] = (deg[e.target] || 0) + 1;
  });
  var eraById = {};
  ERAS.china.concat(ERAS.west).forEach(function (e) { eraById[e.id] = e; });

  function yearText(y) {
    if (y === null || y === undefined) return '';
    var s = String(y).replace(/[^\d\-]/g, '');
    return s || String(y);
  }
  function centuryOf(y) {
    if (!y && y !== 0) return null;
    var v = Math.floor((y - 1) / 100) + 1;
    return v;
  }
  function centuryLabel(c) {
    if (!c) return '';
    return c <= 0 ? '公元前 ' + Math.abs(c - 1) + ' 世纪起' : c + ' 世纪';
  }

  /* ---------- 图片：本地优先，失败回退 Commons ---------- */
  function paintFigure(holder, nodeId, opts) {
    opts = opts || {};
    var meta = IMG[nodeId];
    var ph = holder.querySelector('.ph') || holder;
    var skel = ph.querySelector('.skel');
    var img = ph.querySelector('img');
    if (!img) {
      img = el('img', { alt: opts.alt || '', loading: 'lazy', decoding: 'async' });
      ph.appendChild(img);
    }
    img.alt = opts.alt || '';
    if (!meta || (!meta.file && !meta.remote)) {
      if (skel) skel.textContent = '暂无可用图像';
      ph.classList.add('bad');
      return;
    }
    var tried = 0;
    function trySrc() {
      if (tried === 0) return meta.file || meta.remote;
      if (tried === 1) return meta.remote && meta.remote !== (meta.file) ? meta.remote : null;
      return null;
    }
    function load() {
      var src = trySrc();
      if (!src) {
        if (skel) skel.textContent = '图像暂时无法加载';
        ph.classList.add('bad');
        return;
      }
      img.onload = function () {
        img.classList.add('ok');
        if (skel) skel.style.display = 'none';
      };
      img.onerror = function () { tried++; load(); };
      img.src = src;
    }
    load();
    var cap = holder.querySelector('figcaption');
    if (cap && opts.caption !== false) {
      var n = byId[nodeId];
      var w = n && n.works && n.works[0];
      cap.innerHTML =
        '<span>' + esc((w ? w.title : '') + (n ? ' · ' + n.name : '')) + (w ? ' <span style="opacity:.7">' + esc(w.year || '') + '</span>' : '') + '</span>' +
        '<span class="cr">' + esc(meta && meta.credit ? meta.credit : 'Wikimedia Commons') +
        (meta && meta.license ? ' · ' + esc(meta.license) : '') + '</span>';
    }
  }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function cardHTML(n) {
    var w = n.works && n.works[0];
    var cp = COPY.works[n.id] || {};
    return '<div class="card" data-id="' + n.id + '">' +
      '<div class="ph"><div class="skel">' + esc(w ? w.title : '') + '</div></div>' +
      '<div class="meta">' +
      '<div class="y">' + esc(w ? w.year : '') + '</div>' +
      '<div class="t">' + esc(w ? w.title : n.name) + '</div>' +
      '<div class="a"><span class="dot ' + n.tradition + '"></span>' + esc(n.name) + ' · ' + esc(n.school || '') + '</div>' +
      (cp.note ? '<div class="no">' + esc(cp.note) + '</div>' : '') +
      '</div></div>';
  }

  /* ============ 视图路由 ============ */
  var VIEWS = ['graph', 'time', 'compare', 'read'];
  var state = { view: 'graph', tradition: 'all', per: null, essay: null, types: null, tlFilter: 'all' };

  function parseHash() {
    var h = (location.hash || '').replace(/^#/, '');
    var qs = new URLSearchParams(location.search || '');
    var t = qs.get('tradition');
    state.tradition = (t === 'china' || t === 'west') ? t : 'all';
    state.per = qs.get('per') || null;
    if (!h) return 'graph';
    var m = h.match(/^read\/(.+)$/);
    if (m) { state.essay = m[1]; return 'read'; }
    if (h.indexOf('read') === 0) { state.essay = null; return 'read'; }
    if (VIEWS.indexOf(h) >= 0) return h;
    return 'graph';
  }
  function go(view, extra) {
    extra = extra || {};
    var q = [];
    if (state.tradition !== 'all') q.push('tradition=' + state.tradition);
    if (extra.per) q.push('per=' + encodeURIComponent(extra.per));
    var hash = view === 'read' && state.essay ? '#read/' + state.essay : '#' + view;
    var url = location.pathname + (q.length ? '?' + q.join('&') : '') + hash;
    history.pushState(null, '', url);
    state.view = view;
    render();
  }
  window.addEventListener('popstate', function () { syncFromURL(true); });

  function syncFromURL(skipPush) {
    var v = parseHash();
    state.view = v;
    render();
  }

  function setTradition(t) {
    state.tradition = t;
    var badge = $('#tradBadge');
    badge.textContent = t === 'china' ? '中国' : t === 'west' ? '西方' : '全部';
    badge.className = 'trad ' + (t === 'all' ? '' : t);
    var url = new URL(location.href);
    if (t === 'all') url.searchParams.delete('tradition'); else url.searchParams.set('tradition', t);
    url.searchParams.delete('per');
    history.replaceState(null, '', url.toString());
    if (state.view === 'graph') { layout(true); drawGraph(); }
    renderTime(); renderCompare();
  }

  function render() {
    VIEWS.forEach(function (v) {
      $('#v-' + v).classList.toggle('on', v === state.view);
    });
    $$('#views button').forEach(function (b) {
      b.setAttribute('aria-current', b.dataset.v === state.view ? 'true' : 'false');
    });
    if (state.view === 'graph') { ensureGraph(); }
    if (state.view === 'time') renderTime();
    if (state.view === 'compare') renderCompare();
    if (state.view === 'read') renderRead();
  }

  /* ============ 关系图 ============ */
  var svg = $('#graph'), stage = $('#stage');
  var vp = null, gAxis = null, gEdge = null, gNode = null;
  var W = 0, H = 0;
  var view = { k: 1, x: 0, y: 0 };
  var sim = { alpha: 0, timer: null };
  var axisMode = true;
  var hoverId = null, selId = null;
  var typeFilter = null;

  /* 有头像的节点更大一些，太小看不出人脸 */
  function sizeOf(n) { return 8.5 + Math.min(8.5, (deg[n.id] || 0) * 0.8); }

  var defs = null;
  function clipFor(id) {
    if (!defs) { defs = svgEl('defs'); svg.appendChild(defs); }
    /* objectBoundingBox：裁切圆跟着元素包围盒走，拖动时不用重算坐标 */
    var cp = svgEl('clipPath', { id: 'avc-' + id, clipPathUnits: 'objectBoundingBox' });
    cp.appendChild(svgEl('circle', { cx: 0.5, cy: 0.5, r: 0.5 }));
    defs.appendChild(cp);
    return cp;
  }

  function ensureGraph() {
    if (vp) { resize(); return; }
    vp = svgEl('g'); gAxis = svgEl('g', { 'class': 'axis' }); gEdge = svgEl('g'); gNode = svgEl('g');
    vp.appendChild(gAxis); vp.appendChild(gEdge); vp.appendChild(gNode);
    svg.appendChild(vp);
    resize();
    layout(true);
    bindGraph();
    runSim();
  }
  function resize() {
    var r = stage.getBoundingClientRect();
    W = Math.max(320, r.width); H = Math.max(320, r.height);
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    svg.setAttribute('width', W); svg.setAttribute('height', H);
  }

  function visibleNodes() {
    return NODES.filter(function (n) { return state.tradition === 'all' || n.tradition === state.tradition; });
  }
  function visibleEdges() {
    var set = {};
    visibleNodes().forEach(function (n) { set[n.id] = 1; });
    return EDGES.filter(function (e) {
      return byId[e.source] && byId[e.target] && set[e.source] && set[e.target] &&
        (!typeFilter || e.type === typeFilter);
    });
  }

  function layout(reset) {
    var ns = visibleNodes();
    var yrs = NODES.map(function (n) { return n.year; });
    var yMin = Math.min.apply(null, yrs), yMax = Math.max.apply(null, yrs);
    var padX = 70, padY = 60;
    ns.forEach(function (n, i) {
      if (reset || n.x === undefined) {
        n.x = padX + ((n.year - yMin) / (yMax - yMin)) * (W - padX * 2) + (Math.random() - 0.5) * 20;
        n.y = (n.tradition === 'china' ? 0.35 : 0.66) * H + (Math.random() - 0.5) * H * 0.34;
        n.vx = 0; n.vy = 0;
      }
      n.tx = padX + ((n.year - yMin) / (yMax - yMin)) * (W - padX * 2);
      n.ty = (n.tradition === 'china' ? 0.33 : 0.68) * H;
    });
    drawAxis(yMin, yMax, padX);
  }

  function drawAxis(yMin, yMax, padX) {
    gAxis.innerHTML = '';
    var ticks = [];
    for (var y = 400; y <= 2000; y += 200) if (y >= yMin - 100 && y <= yMax + 100) ticks.push(y);
    var X = function (yr) { return padX + ((yr - yMin) / (yMax - yMin)) * (W - padX * 2); };
    ticks.forEach(function (t) {
      var x = X(t);
      gAxis.appendChild(svgEl('line', { x1: x, y1: 34, x2: x, y2: H - 10, 'stroke-dasharray': '2 6' }));
      var tx = svgEl('text', { x: x, y: 24, 'text-anchor': 'middle' });
      tx.textContent = t;
      gAxis.appendChild(tx);
    });
  }

  function step() {
    var ns = visibleNodes(), es = visibleEdges();
    var i, j, a, b, dx, dy, d2, d, f;
    for (i = 0; i < ns.length; i++) {
      a = ns[i];
      for (j = i + 1; j < ns.length; j++) {
        b = ns[j];
        dx = b.x - a.x; dy = b.y - a.y;
        d2 = dx * dx + dy * dy;
        if (d2 < 1) { dx = Math.random() - 0.5; dy = Math.random() - 0.5; d2 = 1; }
        d = Math.sqrt(d2);
        var minD = sizeOf(a) + sizeOf(b) + 26;
        f = Math.min(2600 / d2, 6);
        if (d < minD) f += (minD - d) * 0.28;
        var ux = dx / d, uy = dy / d;
        a.vx -= ux * f; a.vy -= uy * f;
        b.vx += ux * f; b.vy += uy * f;
      }
    }
    es.forEach(function (e) {
      a = byId[e.source]; b = byId[e.target];
      if (!a || !b) return;
      dx = b.x - a.x; dy = b.y - a.y;
      d = Math.sqrt(dx * dx + dy * dy) || 1;
      var rest = e.type === 'lineage' ? 90 : e.type === 'milieu' ? 130 : 115;
      f = (d - rest) * 0.014;
      var ux = dx / d, uy = dy / d;
      a.vx += ux * f; a.vy += uy * f;
      b.vx -= ux * f; b.vy -= uy * f;
    });
    var kx = axisMode ? 0.055 : 0.004;
    var ky = axisMode ? 0.006 : 0.004;
    ns.forEach(function (n) {
      n.vx += (n.tx - n.x) * kx;
      n.vy += (n.ty - n.y) * ky;
      n.vx *= 0.82; n.vy *= 0.82;
      n.x += n.vx; n.y += n.vy;
      var m = 26 + sizeOf(n);
      n.x = Math.max(m, Math.min(W - m, n.x));
      n.y = Math.max(48, Math.min(H - 28, n.y));
    });
  }

  function runSim() {
    sim.alpha = 1;
    if (sim.timer) return;
    var n = 0;
    sim.timer = setInterval(function () {
      for (var i = 0; i < 2; i++) step();
      drawGraph();
      if (++n > 260) { clearInterval(sim.timer); sim.timer = null; }
    }, 16);
  }

  var nodeEls = {}, edgeEls = {};

  function drawGraph() {
    if (!vp) return;
    var es = visibleEdges();
    var focus = selId || hoverId;
    var neigh = {};
    if (focus) {
      neigh[focus] = 1;
      es.forEach(function (e) {
        if (e.source === focus) neigh[e.target] = 1;
        if (e.target === focus) neigh[e.source] = 1;
      });
    }
    /* 边：复用 DOM，避免整块重建打断指针事件 */
    var seenE = {};
    es.forEach(function (e) {
      var s = byId[e.source], t = byId[e.target];
      if (!s || !t) return;
      var key = e.source + '>' + e.target + '>' + e.type;
      seenE[key] = 1;
      var l = edgeEls[key];
      if (!l) {
        l = svgEl('line', { 'class': 'edge t-' + e.type });
        gEdge.appendChild(l);
        edgeEls[key] = l;
      }
      l.setAttribute('x1', s.x); l.setAttribute('y1', s.y);
      l.setAttribute('x2', t.x); l.setAttribute('y2', t.y);
      var lit = focus && (e.source === focus || e.target === focus);
      l.setAttribute('class', 'edge t-' + e.type + (focus ? (lit ? ' hi' : ' dim') : ''));
    });
    Object.keys(edgeEls).forEach(function (k) {
      if (!seenE[k]) { edgeEls[k].remove(); delete edgeEls[k]; }
    });
    /* 节点：同样复用 */
    var ns = visibleNodes();
    var shown = {};
    ns.forEach(function (n) {
      shown[n.id] = 1;
      var r = sizeOf(n);
      var isFocus = focus === n.id;
      var o = nodeEls[n.id];
      if (!o) {
        var g = svgEl('g', { 'class': 'node', 'data-id': n.id });
        var hit = svgEl('circle', { r: 16, fill: 'transparent', 'pointer-events': 'all' });
        var tint = n.tradition === 'china' ? 'var(--china)' : 'var(--west)';
        var c = svgEl('circle', { r: 5, 'pointer-events': 'none', fill: tint });
        var av = null, ring = null;
        var p = POR[n.id];
        if (p && p.file) {
          av = svgEl('image', {
            'class': 'av', 'pointer-events': 'none',
            'preserveAspectRatio': 'xMidYMid slice',
            'clip-path': 'url(#avc-' + n.id + ')'
          });
          av.setAttributeNS('http://www.w3.org/1999/xlink', 'href', p.file);
          av.setAttribute('href', p.file);
          /* 图挂了就退回色点 */
          av.onerror = function () { if (av) av.style.display = 'none'; if (o && o.ring) o.ring.setAttribute('fill', tint); };
          clipFor(n.id);
          ring = svgEl('circle', { 'class': 'ring', r: 5, 'pointer-events': 'none', stroke: tint });
          g.appendChild(av); g.appendChild(ring);
        }
        var tx = svgEl('text', { 'text-anchor': 'middle', 'pointer-events': 'none' });
        tx.textContent = n.name;
        g.appendChild(hit); g.appendChild(c); g.appendChild(tx);
        gNode.appendChild(g);
        nodeEls[n.id] = { g: g, c: c, t: tx, hit: hit, av: av, ring: ring };
        o = nodeEls[n.id];
      }
      var rr = isFocus ? r + 3 : r;
      o.hit.setAttribute('cx', n.x); o.hit.setAttribute('cy', n.y);
      o.c.setAttribute('cx', n.x); o.c.setAttribute('cy', n.y);
      o.c.setAttribute('r', rr);
      if (o.av) {
        /* 有头像时色点只留一圈描边，中间透出画像 */
        o.c.setAttribute('fill', 'none');
        o.c.setAttribute('stroke', isFocus ? 'var(--ink)' : 'var(--paper)');
        o.c.setAttribute('stroke-width', isFocus ? 2 : 1.4);
        o.av.setAttribute('x', n.x - rr); o.av.setAttribute('y', n.y - rr);
        o.av.setAttribute('width', rr * 2); o.av.setAttribute('height', rr * 2);
        o.ring.setAttribute('cx', n.x); o.ring.setAttribute('cy', n.y);
        o.ring.setAttribute('r', rr + 1.6);
        o.ring.setAttribute('stroke-width', isFocus ? 2.4 : 1.6);
      } else {
        o.c.setAttribute('fill', n.tradition === 'china' ? 'var(--china)' : 'var(--west)');
        o.c.setAttribute('stroke', isFocus ? 'var(--ink)' : 'var(--paper)');
        o.c.setAttribute('stroke-width', isFocus ? 2 : 1.4);
      }
      o.t.setAttribute('x', n.x); o.t.setAttribute('y', n.y + rr + 14);
      var showLabel = !focus || neigh[n.id] || view.k > 1.15;
      o.t.setAttribute('opacity', showLabel ? 1 : 0);
      o.g.setAttribute('class', 'node' + (focus && !neigh[n.id] ? ' dim' : '') + (selId === n.id ? ' sel' : ''));
    });
    Object.keys(nodeEls).forEach(function (k) {
      if (!shown[k]) { nodeEls[k].g.remove(); delete nodeEls[k]; }
    });
    vp.setAttribute('transform', 'translate(' + view.x + ',' + view.y + ') scale(' + view.k + ')');
  }

  function bindGraph() {
    var dragging = null, panning = null, moved = false;
    svg.addEventListener('pointerdown', function (ev) {
      var t = ev.target.closest ? ev.target.closest('.node') : null;
      moved = false;
      if (t) {
        dragging = byId[t.dataset.id];
        svg.classList.add('grabbing');
      } else {
        panning = { x: ev.clientX, y: ev.clientY, vx: view.x, vy: view.y };
        svg.classList.add('grabbing');
      }
      svg.setPointerCapture && svg.setPointerCapture(ev.pointerId);
    });
    svg.addEventListener('pointermove', function (ev) {
      var r = svg.getBoundingClientRect();
      var mx = (ev.clientX - r.left - view.x) / view.k;
      var my = (ev.clientY - r.top - view.y) / view.k;
      if (dragging) {
        moved = true;
        dragging.x = mx; dragging.y = my; dragging.vx = 0; dragging.vy = 0;
        if (!sim.timer) runSim();
        drawGraph();
      } else if (panning) {
        moved = true;
        view.x = panning.vx + (ev.clientX - panning.x);
        view.y = panning.vy + (ev.clientY - panning.y);
        drawGraph();
      } else {
        var hit = null, best = 1e9;
        visibleNodes().forEach(function (n) {
          var d = (n.x - mx) * (n.x - mx) + (n.y - my) * (n.y - my);
          if (d < best && d < (sizeOf(n) + 8) * (sizeOf(n) + 8)) { best = d; hit = n; }
        });
        var id = hit ? hit.id : null;
        if (id !== hoverId) { hoverId = id; drawGraph(); }
        svg.style.cursor = id ? 'pointer' : '';
      }
    });
    svg.addEventListener('pointerup', function (ev) {
      var wasDrag = moved;
      if (dragging && !wasDrag) { openNode(dragging.id); }
      dragging = null; panning = null;
      svg.classList.remove('grabbing');
      if (wasDrag) runSim();
    });
    svg.addEventListener('pointerleave', function () { if (hoverId) { hoverId = null; drawGraph(); } });
    svg.addEventListener('wheel', function (ev) {
      ev.preventDefault();
      var r = svg.getBoundingClientRect();
      var mx = ev.clientX - r.left, my = ev.clientY - r.top;
      var k2 = Math.max(0.45, Math.min(3.2, view.k * (ev.deltaY < 0 ? 1.12 : 0.89)));
      view.x = mx - (mx - view.x) * (k2 / view.k);
      view.y = my - (my - view.y) * (k2 / view.k);
      view.k = k2;
      drawGraph();
    }, { passive: false });
    window.addEventListener('resize', function () {
      if (state.view !== 'graph') return;
      resize(); layout(false); runSim();
    });
    $('#zin').onclick = function () { zoomBy(1.2); };
    $('#zout').onclick = function () { zoomBy(1 / 1.2); };
    $('#zfit').onclick = function () { view = { k: 1, x: 0, y: 0 }; layout(true); runSim(); };
  }
  function zoomBy(f) {
    var k2 = Math.max(0.45, Math.min(3.2, view.k * f));
    var cx = W / 2, cy = H / 2;
    view.x = cx - (cx - view.x) * (k2 / view.k);
    view.y = cy - (cy - view.y) * (k2 / view.k);
    view.k = k2;
    drawGraph();
  }

  /* 关系图控制条 */
  var bar = $('#v-graph .bar');
  var axisBtn = document.createElement('button');
  axisBtn.className = 'chip on';
  axisBtn.textContent = '年代轴';
  axisBtn.style.marginLeft = '2px';
  axisBtn.onclick = function () {
    axisMode = !axisMode;
    axisBtn.classList.toggle('on', axisMode);
    axisBtn.textContent = axisMode ? '年代轴' : '自由布局';
    layout(false); runSim();
  };
  bar.insertBefore(axisBtn, bar.querySelector('.sep'));

  $$('#v-graph .chip[data-f]').forEach(function (b) {
    b.onclick = function () { setTradition(b.dataset.f); };
  });
  $$('#v-graph .chip[data-t]').forEach(function (b) {
    b.onclick = function () {
      var t = b.dataset.t;
      typeFilter = (typeFilter === t) ? null : t;
      $$('#v-graph .chip[data-t]').forEach(function (x) { x.classList.toggle('on', x.dataset.t === typeFilter); });
      runSim();
    };
  });

  /* ============ 详情抽屉 ============ */
  var drawer = $('#drawer');
  function openNode(id) {
    var n = byId[id];
    if (!n) return;
    selId = id;
    drawGraph();
    var cp = COPY.nodes[id] || {};
    var wc = COPY.works[id] || {};
    var w = n.works && n.works[0];
    var era = eraById[n.era];
    $('#d-name').textContent = n.name;
    var p = POR[id];
    var pav = $('#d-av');
    if (p && p.file) {
      var kindTxt = { selfportrait: '自画像', photo: '照片', portrait: '画像' }[p.kind] || '画像';
      pav.innerHTML = '<img src="' + esc(p.file) + '" alt="' + esc(n.name) + '·' + kindTxt + '" loading="lazy">';
      pav.title = kindTxt + ' · ' + esc(p.credit || 'Wikimedia Commons');
    } else {
      pav.innerHTML = '<span class="ini">' + esc(n.name.slice(0, 1)) + '</span>';
      pav.title = '无可用画像';
    }
    $('#d-sub').innerHTML = esc(n.nameEn || '') + ' · ' + esc(n.born || '?') + '–' + esc(n.died || '?') +
      (n.uncertain ? ' · 生卒年/归属存疑' : '');
    var rels = EDGES.filter(function (e) { return e.source === id || e.target === id; });
    var html = '';
    html += '<span class="tag ' + n.tradition + '">' + (n.tradition === 'china' ? '中国' : '西方') + ' · ' + esc(n.school || '') + '</span>';
    if (n.region) html += '<div class="sub" style="font-size:12px;color:var(--ink-2);margin:-4px 0 12px">' + esc(n.region) + (era ? ' · ' + esc(era.name) : '') + '</div>';
    if (cp.tagline) html += '<p style="font-size:17px;color:var(--ink)">' + esc(cp.tagline) + '</p>';
    if (n.dateNote) html += '<div class="sub" style="font-size:12px;color:var(--ink-2);margin:-6px 0 12px">※ ' + esc(n.dateNote) + '</div>';
    if (cp.bio) html += '<p>' + esc(cp.bio) + '</p>';
    if (w) {
      html += '<div class="fig"><div class="ph"><div class="skel">' + esc(w.title) + '</div></div><figcaption></figcaption></div>';
    }
    if (wc.note) html += '<p>' + esc(wc.note) + '</p>';
    if (rels.length) {
      html += '<div class="rel"><h4>关系 · ' + rels.length + ' 条</h4>';
      rels.forEach(function (e) {
        var other = e.source === id ? e.target : e.source;
        var o = byId[other];
        if (!o) return;
        var dir = e.source === id ? '→' : '←';
        html += '<div class="e"><span class="k">' + TYPE_LABEL[e.type] + '</span>' +
          '<span class="who" data-go="' + other + '">' + dir + ' ' + esc(o.name) + '</span>' +
          '<span class="lbl">' + esc(e.label || '') + '</span></div>';
      });
      html += '</div>';
    }
    $('#d-body').innerHTML = html;
    if (w) paintFigure($('#d-body .fig'), id, { alt: w.title + ' · ' + n.name });
    $$('#d-body [data-go]').forEach(function (s) { s.onclick = function () { openNode(s.dataset.go); }; });
    drawer.classList.add('on');
  }
  $('#d-x').onclick = function () { drawer.classList.remove('on'); selId = null; drawGraph(); };

  /* ============ 时间轴 ============ */
  var tlFilter = 'all';
  function renderTime() {
    var host = $('#tl');
    var list = NODES.filter(function (n) { return tlFilter === 'all' || n.tradition === tlFilter; });
    $('#tl-count').textContent = list.length + ' 件作品 · 按年代排列';
    var groups = [];
    var order = { china: ERAS.china.map(function (e) { return e.id; }), west: ERAS.west.map(function (e) { return e.id; }) };
    var seen = {};
    ERAS.china.concat(ERAS.west).forEach(function (e) {
      var items = list.filter(function (n) { return n.era === e.id; })
        .sort(function (a, b) { return a.year - b.year; });
      if (!items.length) return;
      seen[e.id] = 1;
      groups.push({ era: e, items: items });
    });
    list.filter(function (n) { return !seen[n.era]; }).forEach(function (n) { });
    var html = '';
    groups.forEach(function (g) {
      var e = g.era;
      var cp = COPY.eras[e.id] || {};
      html += '<section class="tl-era">' +
        '<div class="eh"><div class="n">' + esc(e.name) + '</div>' +
        '<div class="s">' + esc(e.span || '') + '</div>' +
        '<div class="d">' + esc(cp.lead || e.desc || '') + '</div>' +
        '<div class="side ' + (e.tradition || (ERAS.china.indexOf(e) >= 0 ? 'china' : 'west')) + '">' +
        (ERAS.china.indexOf(e) >= 0 ? '中国' : '西方') + '</div>' +
        '</div><div class="cards">';
      g.items.forEach(function (n) { html += cardHTML(n); });
      html += '</div></section>';
    });
    if (!groups.length) html = '<div class="empty-state">没有符合条件的作品</div>';
    host.innerHTML = html;
    $$('.card', host).forEach(function (c) {
      paintFigure(c, c.dataset.id, { alt: '', caption: false });
      c.onclick = function () { openWork(c.dataset.id); };
    });
  }
  $$('#v-time .chip[data-tf]').forEach(function (b) {
    b.onclick = function () {
      tlFilter = b.dataset.tf;
      $$('#v-time .chip[data-tf]').forEach(function (x) { x.classList.toggle('on', x.dataset.tf === tlFilter); });
      renderTime();
    };
  });
  function openWork(id) {
    state.tradition = 'all';
    go('graph', { per: id });
    setTimeout(function () { ensureGraph(); openNode(id); }, 60);
  }

  /* ============ 中西对照 ============ */
  function renderCompare() {
    var host = $('#cmp');
    var map = {};
    NODES.forEach(function (n) {
      var c = centuryOf(n.year);
      if (!c) return;
      (map[c] = map[c] || { china: [], west: [] })[n.tradition].push(n);
    });
    var cents = Object.keys(map).map(Number).sort(function (a, b) { return a - b; });
    var html = '<div class="cmp-head"><div class="h-c">中国 · CHINA</div><div class="h-m">世纪</div><div class="h-w">WEST · 西方</div></div>';
    cents.forEach(function (c) {
      var g = map[c];
      g.china.sort(function (a, b) { return a.year - b.year; });
      g.west.sort(function (a, b) { return a.year - b.year; });
      html += '<div class="cen"><div class="side c">';
      html += g.china.length ? g.china.map(pill('c')).join('') : '<div class="none">—</div>';
      html += '</div><div class="mid"><div class="c">' + centuryLabel(c).replace('世纪', '') + '</div>' +
        '<div class="y">' + esc(c <= 0 ? '前 ' + Math.abs(c - 1) + '00' : ((c - 1) * 100 + 1) + '–' + c * 100) + '</div></div>';
      html += '<div class="side w">';
      html += g.west.length ? g.west.map(pill('w')).join('') : '<div class="none">—</div>';
      html += '</div></div>';
    });
    host.innerHTML = html;
    $$('.pill', host).forEach(function (p) { p.onclick = function () { openWork(p.dataset.id); }; });
  }
  function pill(side) {
    return function (n) {
      var w = n.works && n.works[0];
      return '<div class="pill ' + side + '" data-id="' + n.id + '">' +
        '<div class="w">' + esc(w ? w.title : n.name) + '</div>' +
        '<div class="a">' + esc(n.name) + ' · ' + esc(n.school || '') + '</div>' +
        '<div class="y2">' + esc(w ? w.year : '') + '</div></div>';
    };
  }

  /* ============ 阅读室 ============ */
  function renderRead() {
    var host = $('#rd');
    if (state.essay) {
      var e = ESSAYS.filter(function (x) { return x.id === state.essay; })[0];
      if (!e) { state.essay = null; return renderRead(); }
      $('#rd-bar').innerHTML = '<button class="back" id="rd-back">← 全部导读</button>' +
        '<span style="margin-left:10px">' + esc(e.no) + ' / ' + ESSAYS.length + ' · 约 ' + (e.minutes || 6) + ' 分钟</span>';
      $('#rd-back').onclick = function () { state.essay = null; go('read'); };
      var h = '<article class="art">' +
        '<div class="kicker">' + esc(e.kicker || '') + '</div>' +
        '<h1>' + esc(e.title) + '</h1>' +
        '<p class="sf">' + esc(e.standfirst || '') + '</p>';
      (e.sections || []).forEach(function (s) {
        h += '<h2>' + esc(s.h) + '</h2>';
        (s.p || []).forEach(function (p) { h += '<p>' + esc(p) + '</p>'; });
      });
      if (e.sources && e.sources.length) {
        h += '<div class="srcs"><b>来源与延伸阅读</b>' + e.sources.map(function (s) { return esc(s); }).join('<br/>') + '</div>';
      }
      if (e.caveat) h += '<div class="cav"><b style="font-family:var(--sans);font-size:12px">读法提醒 · </b>' + esc(e.caveat) + '</div>';
      h += '<div style="margin-top:34px"><button class="back" id="rd-back2">← 返回导读目录</button></div>';
      h += '</article>';
      host.innerHTML = h;
      var b2 = $('#rd-back2'); if (b2) b2.onclick = function () { state.essay = null; go('read'); };
      host.scrollTop = 0;
      return;
    }
    $('#rd-bar').innerHTML = '<span>入门导读 · ' + ESSAYS.length + ' 篇 · 有出处，也有解释的边界</span>';
    var h = '<div class="rd-inner">' +
      '<div class="eyebrow">READING ROOM</div>' +
      '<h1 class="big">先读懂一张画，<br/>再走进一整段历史。</h1>' +
      '<p class="lead">' + esc(SITE.heroLead || '') + '</p>' +
      '<div class="essays">';
    ESSAYS.forEach(function (e) {
      h += '<div class="ess" data-id="' + e.id + '">' +
        '<div><div class="no">' + esc(e.no) + '</div><div class="kk">' + esc(e.kicker || '') + '</div></div>' +
        '<div><div class="ti">' + esc(e.title) + '</div><div class="st">' + esc(e.standfirst || '') + '</div></div>' +
        '<div class="ar">→</div></div>';
    });
    h += '</div>';
    if (TERMS.length) {
      h += '<div class="terms"><h3>术语表 · ' + TERMS.length + ' 条</h3><div class="g">';
      TERMS.forEach(function (t) {
        var side = t.tradition === 'china' ? '中国' : t.tradition === 'west' ? '西方' : '通用';
        h += '<div class="it"><b>' + esc(t.term) + '</b><span class="s ' + (t.tradition === 'china' ? 'c' : t.tradition === 'west' ? 'w' : '') + '">' + side + '</span><p>' + esc(t.def) + '</p></div>';
      });
      h += '</div></div>';
    }
    h += '<div style="margin-top:40px;padding-top:18px;border-top:1px solid var(--rule);font-family:var(--sans);font-size:12px;color:var(--ink-3);line-height:1.9">' +
      esc(SITE.sourceNote || '') + '</div>';
    h += '</div>';
    host.innerHTML = h;
    $$('.ess', host).forEach(function (x) {
      x.onclick = function () { state.essay = x.dataset.id; go('read'); };
    });
    host.scrollTop = 0;
  }

  /* ============ 搜索 ============ */
  var q = $('#q'), res = $('#res');
  var index = [];
  NODES.forEach(function (n) {
    index.push({ type: 'node', id: n.id, t: n.name, m: (n.nameEn || '') + ' · ' + (n.school || ''), s: (n.nameEn || '') + ' ' + (COPY.nodes[n.id] || {}).tagline });
    if (n.works && n.works[0]) index.push({ type: 'node', id: n.id, t: n.works[0].title, m: n.name + ' · 名作', s: (n.works[0].titleEn || '') });
  });
  ESSAYS.forEach(function (e) { index.push({ type: 'essay', id: e.id, t: e.title, m: '导读 ' + (e.no || ''), s: e.standfirst || '' }); });
  TERMS.forEach(function (t, i) { index.push({ type: 'term', id: 'term-' + i, t: t.term, m: '术语', s: t.def }); });

  var sel = -1, hits = [];
  function doSearch() {
    var v = q.value.trim().toLowerCase();
    if (!v) { res.classList.remove('on'); hits = []; return; }
    hits = index.filter(function (it) {
      return (it.t + ' ' + it.m + ' ' + (it.s || '')).toLowerCase().indexOf(v) >= 0;
    }).slice(0, 24);
    sel = hits.length ? 0 : -1;
    res.innerHTML = hits.length ? hits.map(function (it, i) {
      var side = it.type === 'node' ? (byId[it.id] ? byId[it.id].tradition : '') : '';
      return '<div class="r' + (i === 0 ? ' sel' : '') + '" data-i="' + i + '">' +
        (side ? '<span class="dot ' + side + '"></span>' : '<span class="dot" style="background:var(--ink-3)"></span>') +
        '<span class="t">' + esc(it.t) + '</span><span class="m">' + esc(it.m) + '</span></div>';
    }).join('') : '<div class="empty">没有找到相关条目</div>';
    res.classList.add('on');
  }
  q.addEventListener('input', doSearch);
  q.addEventListener('focus', function () { if (q.value.trim()) doSearch(); });
  q.addEventListener('keydown', function (ev) {
    if (ev.key === 'Escape') { q.value = ''; res.classList.remove('on'); q.blur(); return; }
    if (!hits.length) return;
    if (ev.key === 'ArrowDown') { sel = (sel + 1) % hits.length; paintSel(); ev.preventDefault(); }
    if (ev.key === 'ArrowUp') { sel = (sel - 1 + hits.length) % hits.length; paintSel(); ev.preventDefault(); }
    if (ev.key === 'Enter') { pick(hits[sel]); ev.preventDefault(); }
  });
  function paintSel() {
    $$('.r', res).forEach(function (r) { r.classList.toggle('sel', +r.dataset.i === sel); });
    var s = res.querySelector('.r.sel'); if (s) s.scrollIntoView({ block: 'nearest' });
  }
  res.addEventListener('click', function (ev) {
    var r = ev.target.closest('.r'); if (!r) return;
    pick(hits[+r.dataset.i]);
  });
  function pick(it) {
    if (!it) return;
    res.classList.remove('on'); q.value = ''; q.blur();
    if (it.type === 'node') { state.tradition = 'all'; go('graph', { per: it.id }); setTimeout(function () { ensureGraph(); openNode(it.id); focusNode(it.id); }, 60); }
    if (it.type === 'essay') { state.essay = it.id; go('read'); }
    if (it.type === 'term') { state.tradition = 'all'; go('read'); setTimeout(function () { var t = $('#v-read .terms'); if (t) t.scrollIntoView({ behavior: 'smooth', block: 'start' }); }, 120); }
  }
  document.addEventListener('click', function (ev) {
    if (!ev.target.closest('.search')) res.classList.remove('on');
  });
  document.addEventListener('keydown', function (ev) {
    if (ev.key === '/' && document.activeElement !== q) { ev.preventDefault(); q.focus(); }
    if (ev.key === 'Escape' && drawer.classList.contains('on')) { drawer.classList.remove('on'); selId = null; drawGraph(); }
  });
  function focusNode(id) {
    var n = byId[id]; if (!n) return;
    view.k = 1.5;
    view.x = W / 2 - n.x * view.k;
    view.y = H / 2 - n.y * view.k;
    drawGraph();
  }

  /* ============ 每日一画 ============ */
  var dailyEl = $('#daily');
  function openDaily() {
    if (!DAILY.length) return;
    var d0 = new Date(2026, 0, 1);
    var idx = Math.floor((Date.now() - d0.getTime()) / 86400000) % DAILY.length;
    var d = DAILY[idx];
    var n = byId[d.workId];
    if (!n) return;
    var w = n.works && n.works[0];
    $('.dcard h3', dailyEl).textContent = d.title || (w ? w.title : n.name);
    $('.dcard .who', dailyEl).textContent = n.name + ' · ' + (w ? w.title + ' · ' + w.year : '');
    $('.dcard p', dailyEl).textContent = d.text || '';
    var ph = $('.dcard .ph', dailyEl);
    ph.innerHTML = '<div class="skel">载入图像</div>';
    paintFigure($('.dcard', dailyEl), n.id, { alt: (w ? w.title : ''), caption: false });
    $('.dcard .go', dailyEl).onclick = function () {
      dailyEl.classList.remove('on');
      go('graph', { per: n.id });
      setTimeout(function () { ensureGraph(); openNode(n.id); focusNode(n.id); }, 60);
    };
    dailyEl.classList.add('on');
  }
  $('#fab').onclick = openDaily;
  $('#d-close').onclick = function () { dailyEl.classList.remove('on'); };
  dailyEl.addEventListener('click', function (ev) { if (ev.target === dailyEl) dailyEl.classList.remove('on'); });

  /* ============ 首屏 ============ */
  var gate = $('#gate');
  $$('.gate .gs button').forEach(function (b) {
    b.onclick = function () {
      gate.classList.add('off');
      setTimeout(function () { gate.style.display = 'none'; }, 500);
      var v = b.dataset.go;
      go(v === 'read' ? 'read' : v);
      state.view = v;
      render();
    };
  });

  /* ============ 启动 ============ */
  $('#views').addEventListener('click', function (ev) {
    var b = ev.target.closest('button[data-v]'); if (!b) return;
    if (b.dataset.v === 'read') state.essay = null;
    go(b.dataset.v);
  });

  function boot() {
    $('#stamp').textContent = 'ART · ' + (D.meta && D.meta.version ? D.meta.version : '0000');
    document.title = SITE.title || document.title;
    var v = parseHash();
    state.view = v;
    if (location.hash && location.hash.length > 1) { gate.style.display = 'none'; }
    render();
    if (state.per) setTimeout(function () { ensureGraph(); openNode(state.per); focusNode(state.per); }, 120);
    var badge = $('#tradBadge');
    badge.textContent = state.tradition === 'china' ? '中国' : state.tradition === 'west' ? '西方' : '全部';
    badge.className = 'trad ' + (state.tradition === 'all' ? '' : state.tradition);
    setTimeout(function () { if (state.view === 'graph') { resize(); layout(false); runSim(); } }, 30);
  }
  boot();
})();
