/* VANTA — Lenis + GSAP ScrollTrigger + Three.js, single ticker loop.
   Techniques: preloader counter, curtain transition, masked line reveals,
   lerped custom cursor, film grain, pinned scrub for the results build,
   and a particle system that morphs through the project's narrative —
   ending in the real held-out figures. */
(function () {
  var reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  var hasGSAP = typeof gsap !== 'undefined' && typeof ScrollTrigger !== 'undefined';
  if (hasGSAP) gsap.registerPlugin(ScrollTrigger);

  /* ============ 1. smooth scroll, one loop ============ */
  var lenis = null;
  if (typeof Lenis !== 'undefined' && !reduce) {
    lenis = new Lenis({ lerp: 0.085, wheelMultiplier: 0.95 });
    if (hasGSAP) {
      lenis.on('scroll', ScrollTrigger.update);
      gsap.ticker.add(function (t) { lenis.raf(t * 1000); });
      gsap.ticker.lagSmoothing(0);
    } else {
      requestAnimationFrame(function r(t) { lenis.raf(t); requestAnimationFrame(r); });
    }
  }

  /* ============ 2. preloader ============ */
  var pre = document.getElementById('pre');
  var pnum = document.getElementById('pnum');
  var pbar = document.getElementById('pbar');
  document.body.classList.add('lock');

  function revealSite() {
    document.body.classList.remove('lock');
    if (lenis) lenis.start();
    if (!hasGSAP) { if (pre) pre.style.display = 'none'; showHero(); return; }
    var tl = gsap.timeline();
    tl.to('#pre', { yPercent: -100, duration: 1.0, ease: 'expo.inOut' })
      .fromTo('.curtain', { yPercent: 0 }, { yPercent: -100, duration: 1.0, ease: 'expo.inOut' }, 0.08)
      .add(showHero, '-=0.45')
      .set(['#pre', '.curtain'], { display: 'none' });
  }
  function forceShow() {
    document.querySelectorAll('.line > span').forEach(function (el) {
      el.style.transform = 'translateY(0%)';
    });
    document.querySelectorAll('.fade').forEach(function (el) {
      el.style.opacity = 1; el.style.transform = 'none';
    });
  }
  /* failsafe: whatever happens above, the page is readable within 6s */
  setTimeout(function () {
    document.body.classList.remove('lock');
    var pre = document.getElementById('pre');
    if (pre && pre.style.display !== 'none') { pre.style.display = 'none'; }
    var c = document.querySelector('.curtain');
    if (c) c.style.display = 'none';
    document.querySelectorAll('.hero .line > span').forEach(function (el) {
      if (getComputedStyle(el).transform.indexOf('matrix') === 0) {
        var m = getComputedStyle(el).transform;
        if (m !== 'none' && Math.abs(parseFloat(m.split(',')[5] || 0)) > 4) el.style.transform = 'translateY(0%)';
      }
    });
  }, 6000);

  function showHero() {
    var lines = document.querySelectorAll('.hero .line > span');
    if (!hasGSAP) { forceShow(); return; }
    gsap.fromTo(lines, { yPercent: 108 }, {
      yPercent: 0, duration: 1.2, ease: 'expo.out', stagger: 0.08, overwrite: true
    });
    gsap.to('.hero .fade', { opacity: 1, y: 0, duration: 0.9, ease: 'power3.out', stagger: 0.09, delay: 0.3 });
  }

  if (pre) {
    if (lenis) lenis.stop();
    var v = 0, tgt = 0, done = false;
    var fake = setInterval(function () { tgt = Math.min(tgt + Math.random() * 16, 92); }, 190);
    addEventListener('load', function () { clearInterval(fake); tgt = 100; });
    setTimeout(function () { clearInterval(fake); tgt = 100; }, 4200);
    (function tick() {
      v += (tgt - v) * 0.09;
      if (pnum) pnum.textContent = String(Math.round(v)).padStart(3, '0');
      if (pbar) pbar.style.transform = 'scaleX(' + (v / 100).toFixed(3) + ')';
      if (v > 99.4 && !done) { done = true; setTimeout(revealSite, 260); }
      else requestAnimationFrame(tick);
    })();
  } else { showHero(); }

  /* ============ 3. custom cursor ============ */
  if (matchMedia('(hover:hover)').matches && !reduce) {
    var ring = document.querySelector('.cur'), dot = document.querySelector('.curDot');
    var tx = innerWidth / 2, ty = innerHeight / 2, rx = tx, ry = ty, seen = false;
    if (ring) ring.style.opacity = 0;
    if (dot) dot.style.opacity = 0;
    addEventListener('pointermove', function (e) {
      tx = e.clientX; ty = e.clientY;
      if (!seen) { seen = true; rx = tx; ry = ty;
        if (ring) ring.style.opacity = 1; if (dot) dot.style.opacity = 1; }
      if (dot) dot.style.transform = 'translate(' + tx + 'px,' + ty + 'px)';
    }, { passive: true });
    (function cur() {
      rx += (tx - rx) * 0.16; ry += (ty - ry) * 0.16;
      if (ring) ring.style.transform = 'translate(' + rx + 'px,' + ry + 'px)';
      requestAnimationFrame(cur);
    })();
    document.querySelectorAll('a,button,.framewrap,.ledger').forEach(function (el) {
      el.addEventListener('pointerenter', function () { ring && ring.classList.add('big'); });
      el.addEventListener('pointerleave', function () { ring && ring.classList.remove('big'); });
    });
  }

  /* ============ 4. scroll-driven reveals ============ */
  if (hasGSAP) {
    document.querySelectorAll('section:not(.hero) .line > span').forEach(function (el) {
      gsap.fromTo(el, { yPercent: 108 }, {
        yPercent: 0, duration: 1.1, ease: 'expo.out', overwrite: true,
        scrollTrigger: { trigger: el.closest('.line'), start: 'top 90%' }
      });
    });
    gsap.utils.toArray('.fade').forEach(function (el) {
      if (el.closest('.hero')) return;
      gsap.to(el, {
        opacity: 1, y: 0, duration: 0.9, ease: 'power3.out',
        scrollTrigger: { trigger: el, start: 'top 88%' }
      });
    });
    gsap.to('.sprog', {
      scaleX: 1, ease: 'none',
      scrollTrigger: { trigger: document.body, start: 'top top', end: 'bottom bottom', scrub: true }
    });
    /* marquee */
    gsap.to('.marq-in span', {
      xPercent: -100, repeat: -1, duration: 26, ease: 'none'
    });
    /* Both charts: the markup already holds each bar's correct FINAL y /
       height / width as plain SVG attributes. GSAP's documented pattern for
       tweening raw SVG geometry is `attr:{}` -- animating `transform` via
       transform-box:fill-box was the previous attempt, and its
       transform-origin did not resolve to each rect's own box in every
       browser, so bars collapsed toward the SVG's top-left corner instead of
       their own baseline. attr-tweening has no such ambiguity: it moves the
       real attribute, nothing else, so a bar is either at its start state or
       its real final state -- never anywhere else. */
    gsap.utils.toArray('.chartwrap').forEach(function (wrap) {
      var bars = wrap.querySelectorAll('.bar');
      bars.forEach(function (rect, i) {
        var finalY = parseFloat(rect.getAttribute('y'));
        var finalH = parseFloat(rect.getAttribute('height'));
        gsap.fromTo(rect,
          { attr: { y: 252, height: 0 } },
          { attr: { y: finalY, height: finalH }, duration: 0.9, ease: 'power2.out',
            delay: i * 0.05,
            scrollTrigger: { trigger: wrap, start: 'top 78%' } });
      });
      var hbars = wrap.querySelectorAll('.hbar');
      hbars.forEach(function (rect, i) {
        var finalW = parseFloat(rect.getAttribute('width'));
        gsap.fromTo(rect,
          { attr: { width: 0 } },
          { attr: { width: finalW }, duration: 0.8, ease: 'power2.out',
            delay: i * 0.045,
            scrollTrigger: { trigger: wrap, start: 'top 78%' } });
      });
    });

    /* counters */
    gsap.utils.toArray('[data-count]').forEach(function (el) {
      var to = parseFloat(el.getAttribute('data-count'));
      var o = { v: 0 };
      gsap.to(o, {
        v: to, duration: 1.6, ease: 'power2.out',
        scrollTrigger: { trigger: el, start: 'top 90%' },
        onUpdate: function () { el.textContent = Math.round(o.v).toLocaleString('en-IN'); }
      });
    });
  }

  /* ============ 5. pinned results build ============ */
  var arms = document.querySelectorAll('.armrow');
  if (hasGSAP && arms.length) {
    /* No pin: pinning inside a fixed-height section failed to reserve space
       and let the next section scroll over it. A scrubbed build on enter gives
       the same reveal with none of the layout risk. */
    var tl = gsap.timeline({
      scrollTrigger: { trigger: '#results', start: 'top 72%', end: 'bottom 85%', scrub: 0.8 }
    });
    arms.forEach(function (row, i) {
      tl.to(row, { opacity: 1, duration: 0.3 }, i * 0.8)
        .to(row.querySelector('.fill'),
            { width: row.getAttribute('data-pct') + '%', duration: 0.9, ease: 'power2.out' }, i * 0.8);
    });
  }

  /* layout settles late (webfonts, the report iframe): recompute triggers */
  if (hasGSAP) {
    addEventListener('load', function () { ScrollTrigger.refresh(); });
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(function () { ScrollTrigger.refresh(); });
    }
    setTimeout(function () { ScrollTrigger.refresh(); }, 1200);
  }

  /* ============ 6. webgl narrative ============ */
  (function webgl() {
    var canvas = document.getElementById('gl');
    if (!canvas || typeof THREE === 'undefined') return;
    var N = 6400, ANCHOR = 12.5;

    var scene = new THREE.Scene();
    var camera = new THREE.PerspectiveCamera(42, innerWidth / innerHeight, 0.1, 400);
    var renderer;
    try { renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true }); }
    catch (e) { return; }
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    renderer.setSize(innerWidth, innerHeight);

    var world = new THREE.Group(); scene.add(world);
    var GOLD = new THREE.Color(0x9C6A12), ULTRA = new THREE.Color(0x1B2CA0);
    var SLATE = new THREE.Color(0x69707F), INK = new THREE.Color(0x161B29);

    function A() { return new Float32Array(N * 3); }
    var F = {}, barIdx = new Uint8Array(N);

    F.card = (function () {
      var a = A(), w = 21, h = 13.2, r = 1.8;
      for (var i = 0; i < N; i++) {
        var x, y, ok = false, g = 0;
        while (!ok && g++ < 22) {
          x = (Math.random() - .5) * w; y = (Math.random() - .5) * h;
          var cx = Math.max(Math.abs(x) - (w / 2 - r), 0), cy = Math.max(Math.abs(y) - (h / 2 - r), 0);
          ok = cx * cx + cy * cy <= r * r;
        }
        a[i * 3] = x; a[i * 3 + 1] = y; a[i * 3 + 2] = (Math.random() - .5) * .7;
      } return a;
    })();
    F.leak = (function () {
      var a = A();
      for (var i = 0; i < N; i++) {
        a[i * 3] = (Math.random() - .5) * 42;
        a[i * 3 + 1] = 12 - Math.pow(Math.random(), .55) * 42;
        a[i * 3 + 2] = (Math.random() - .5) * 28;
      } return a;
    })();
    F.stack = (function () {
      var a = A();
      for (var i = 0; i < N; i++) {
        var L = i % 4;
        a[i * 3] = (Math.random() - .5) * 27;
        a[i * 3 + 1] = 11.8 - L * 7.8 + (Math.random() - .5) * .7;
        a[i * 3 + 2] = (Math.random() - .5) * 15;
      } return a;
    })();
    F.gate = (function () {
      var a = A();
      for (var i = 0; i < N; i++) {
        var t = Math.random(), ang = Math.random() * Math.PI * 2;
        var rad = (1 - Math.pow(t, .4)) * 18 + .5;
        a[i * 3] = (t - .5) * 45;
        a[i * 3 + 1] = Math.cos(ang) * rad;
        a[i * 3 + 2] = Math.sin(ang) * rad;
      } return a;
    })();
    F.lattice = (function () {
      var a = A(), cols = 80, rows = Math.ceil(N / cols);
      for (var i = 0; i < N; i++) {
        var c = i % cols, r = Math.floor(i / cols);
        a[i * 3] = (c / (cols - 1) - .5) * 42;
        a[i * 3 + 1] = (r / (rows - 1) - .5) * 22;
        a[i * 3 + 2] = Math.sin(c * .3) * 1.5 + Math.cos(r * .42) * 1.5;
      } return a;
    })();
    /* the real held-out numbers */
    var ARMS = [{ h: .4237 }, { h: .7492 }, { h: .9651 }, { h: 1 }];
    F.bars = (function () {
      var a = A(), maxH = 26, bw = 5.6, gap = 2.6;
      var total = ARMS.length * bw + (ARMS.length - 1) * gap;
      var wsum = ARMS.reduce(function (p, m) { return p + m.h; }, 0), idx = 0;
      for (var b = 0; b < ARMS.length; b++) {
        var count = b === ARMS.length - 1 ? N - idx : Math.round(N * ARMS[b].h / wsum);
        var x0 = -total / 2 + b * (bw + gap);
        for (var j = 0; j < count && idx < N; j++, idx++) {
          a[idx * 3] = x0 + Math.random() * bw;
          a[idx * 3 + 1] = -13 + Math.random() * (ARMS[b].h * maxH);
          a[idx * 3 + 2] = (Math.random() - .5) * 2.6;
          barIdx[idx] = b;
        }
      } return a;
    })();

    var seed = new Float32Array(N);
    for (var i = 0; i < N; i++) seed[i] = Math.random();

    /* Edge softness: how far each point sits from its formation's own centre,
       normalised 0 (core) .. 1 (outermost). Used to fade outliers toward the
       page colour so no formation reads as a hard-edged tile floating in
       space -- the failure mode a screenshot caught directly. */
    var PAPER = new THREE.Color(0xF4F1EA);
    function computeEdge(arr) {
      var out = new Float32Array(N), cx = 0, cy = 0, cz = 0;
      for (var i = 0; i < N; i++) { cx += arr[i*3]; cy += arr[i*3+1]; cz += arr[i*3+2]; }
      cx /= N; cy /= N; cz /= N;
      var d = new Float32Array(N), maxD = 0.0001;
      for (var i = 0; i < N; i++) {
        var dx = arr[i*3]-cx, dy = arr[i*3+1]-cy, dz = arr[i*3+2]-cz;
        d[i] = Math.sqrt(dx*dx+dy*dy+dz*dz);
        if (d[i] > maxD) maxD = d[i];
      }
      for (var i = 0; i < N; i++) out[i] = Math.pow(Math.min(d[i]/maxD, 1), 1.7);
      return out;
    }
    var EDGE = {};
    Object.keys(F).forEach(function (k) { EDGE[k] = computeEdge(F[k]); });
    var geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(F.card), 3));
    geo.setAttribute('color', new THREE.BufferAttribute(new Float32Array(N * 3), 3));
    world.add(new THREE.Points(geo, new THREE.PointsMaterial({
      size: .17, vertexColors: true, transparent: true, opacity: 1,
      sizeAttenuation: true, depthWrite: false
    })));

    var ACTS = [
      { f: 'card',    cam: [0, 0, 40], rot: [-.10, .26], tint: 'mix',    label: 'payment instrument' },
      { f: 'leak',    cam: [0, 1, 48], rot: [.14, -.14], tint: 'lost',   label: 'revenue leaking' },
      { f: 'stack',   cam: [0, 0, 42], rot: [.40, .38],  tint: 'ink',    label: 'four layers' },
      { f: 'gate',    cam: [0, 0, 34], rot: [.06, .50],  tint: 'ultra',  label: 'authority gate' },
      { f: 'lattice', cam: [0, 0, 41], rot: [.34, .12],  tint: 'mix',    label: 'the dataset' },
      { f: 'bars',    cam: [0, 1, 44], rot: [.03, .05],  tint: 'result', label: 'held-out result' },
      { f: 'card',    cam: [0, 0, 43], rot: [-.08, -.22], tint: 'mix',   label: 'payment instrument' }
    ];
    var ca = new THREE.Color(), cb = new THREE.Color();
    function tint(m, i, o) {
      var s = seed[i];
      if (m === 'lost') return o.copy(s < .14 ? GOLD : SLATE);
      if (m === 'ink') return o.copy(s < .28 ? ULTRA : INK);
      if (m === 'ultra') return o.copy(s < .461 ? ULTRA : SLATE);
      if (m === 'result') return o.copy(barIdx[i] === 3 ? ULTRA : (s < .6 ? GOLD : SLATE));
      return o.copy(s < .461 ? GOLD : SLATE);
    }

    (function ambientField() {
      var M = 6000, ap = new Float32Array(M * 3), ac = new Float32Array(M * 3);
      var slate = new THREE.Color(0x9AA0AF), gold = new THREE.Color(0xB8925A);
      for (var i = 0; i < M; i++) {
        /* Box re-fit to what the camera actually sees, and re-centred on
           where it's actually looking (the anchor point sits right of scene
           origin on wide screens), not on world (0,0,0). Without this, most
           points were rendering off the edge of the frame or bunched on the
           side away from the camera -- which is exactly the empty gap in the
           last screenshot. */
        ap[i*3]   = Math.random() * 90 - 35;       // -35 .. 55, centred near the anchor
        ap[i*3+1] = (Math.random() - .5) * 38;
        ap[i*3+2] = (Math.random() - .5) * 34 - 4;
        var c = Math.random() < 0.3 ? gold : slate;
        ac[i*3] = c.r; ac[i*3+1] = c.g; ac[i*3+2] = c.b;
      }
      var ag = new THREE.BufferGeometry();
      ag.setAttribute('position', new THREE.BufferAttribute(ap, 3));
      ag.setAttribute('color', new THREE.BufferAttribute(ac, 3));
      var ambientGroup = new THREE.Group();
      ambientGroup.add(new THREE.Points(ag, new THREE.PointsMaterial({
        size: .15, vertexColors: true, transparent: true, opacity: .68,
        sizeAttenuation: true, depthWrite: false
      })));
      scene.add(ambientGroup);
      (function driftAmbient() {
        requestAnimationFrame(driftAmbient);
        var t = performance.now() * 0.00006;
        ambientGroup.rotation.y = Math.sin(t) * 0.04;
        ambientGroup.position.y = Math.sin(t * 1.3) * 0.6;
      })();
    })();

    var prog = 0, target = 0, mx = 0, my = 0, clock = 0;
    var hudForm = document.getElementById('hudForm'), hudBar = document.getElementById('hudBar');

    function anchor() {
      /* push the formation into the right third, further out on wide screens */
      world.position.x = innerWidth < 1000 ? 0 : ANCHOR * Math.min(innerWidth / 1440, 1.55);
    }
    anchor();

    if (!reduce) addEventListener('pointermove', function (e) {
      mx = e.clientX / innerWidth - .5; my = -(e.clientY / innerHeight - .5);
    }, { passive: true });

    function setTarget() {
      var max = document.body.scrollHeight - innerHeight;
      target = (max > 0 ? scrollY / max : 0) * (ACTS.length - 1);
    }
    if (hasGSAP) {
      ScrollTrigger.create({
        trigger: document.body, start: 'top top', end: 'bottom bottom', scrub: true,
        onUpdate: function (self) { target = self.progress * (ACTS.length - 1); }
      });
    } else { addEventListener('scroll', setTarget, { passive: true }); setTarget(); }

    addEventListener('resize', function () {
      camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix();
      renderer.setSize(innerWidth, innerHeight); anchor();
    });

    function render() {
      clock += .016;
      prog += (target - prog) * (reduce ? 1 : .075);
      var i0 = Math.max(0, Math.min(Math.floor(prog), ACTS.length - 1));
      var i1 = Math.min(i0 + 1, ACTS.length - 1);
      var f = prog - i0, e = f * f * (3 - 2 * f);
      var Pa = F[ACTS[i0].f], Pb = F[ACTS[i1].f];
      var P = geo.attributes.position.array, C = geo.attributes.color.array;
      var Ea = EDGE[ACTS[i0].f], Eb = EDGE[ACTS[i1].f];
      for (var i = 0; i < N; i++) {
        var k = i * 3, d = Math.sin(clock * .7 + seed[i] * 11) * .13;
        P[k] = Pa[k] + (Pb[k] - Pa[k]) * e;
        P[k + 1] = Pa[k + 1] + (Pb[k + 1] - Pa[k + 1]) * e + d;
        P[k + 2] = Pa[k + 2] + (Pb[k + 2] - Pa[k + 2]) * e;
        tint(ACTS[i0].tint, i, ca); tint(ACTS[i1].tint, i, cb);
        var rr = ca.r + (cb.r - ca.r) * e, gg = ca.g + (cb.g - ca.g) * e, bb = ca.b + (cb.b - ca.b) * e;
        var edge = (Ea[i] + (Eb[i] - Ea[i]) * e) * 0.7;   /* camouflage the fringe, keep the core */
        C[k]     = rr + (PAPER.r - rr) * edge;
        C[k + 1] = gg + (PAPER.g - gg) * edge;
        C[k + 2] = bb + (PAPER.b - bb) * edge;
      }
      geo.attributes.position.needsUpdate = true;
      geo.attributes.color.needsUpdate = true;
      var c0 = ACTS[i0].cam, c1 = ACTS[i1].cam, ax = world.position.x;
      camera.position.set(
        ax + c0[0] + (c1[0] - c0[0]) * e + mx * 1.8,
        c0[1] + (c1[1] - c0[1]) * e + my * 1.1,
        c0[2] + (c1[2] - c0[2]) * e);
      camera.lookAt(ax, 0, 0);
      var r0 = ACTS[i0].rot, r1 = ACTS[i1].rot;
      world.rotation.x = r0[0] + (r1[0] - r0[0]) * e + Math.sin(clock * .28) * .035;
      world.rotation.y = r0[1] + (r1[1] - r0[1]) * e + Math.sin(clock * .21) * .055;
      if (hudForm) hudForm.textContent = ACTS[e > .5 ? i1 : i0].label;
      if (hudBar) hudBar.style.transform = 'scaleX(' + (prog / (ACTS.length - 1)).toFixed(3) + ')';
      renderer.render(scene, camera);
    }
    if (hasGSAP) gsap.ticker.add(render);
    else (function l() { requestAnimationFrame(l); render(); })();
  })();

  /* nav highlight */
  new IntersectionObserver(function (es) {
    es.forEach(function (en) {
      if (!en.isIntersecting) return;
      document.querySelectorAll('.links a').forEach(function (a) {
        if (a.getAttribute('href') === '#' + en.target.id) a.setAttribute('aria-current', 'true');
        else a.removeAttribute('aria-current');
      });
    });
  }, { threshold: .3 }).observe && document.querySelectorAll('section[id]').forEach(function (s) {
    new IntersectionObserver(function (es) {
      es.forEach(function (en) {
        if (!en.isIntersecting) return;
        document.querySelectorAll('.links a').forEach(function (a) {
          if (a.getAttribute('href') === '#' + s.id) a.setAttribute('aria-current', 'true');
          else a.removeAttribute('aria-current');
        });
      });
    }, { threshold: .3 }).observe(s);
  });
})();
