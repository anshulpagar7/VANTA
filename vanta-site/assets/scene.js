/* VANTA hero scene — contained inside .stage, so it can never overlap type.
   Payment events stream toward the authority gate. The gate admits a share of
   them: 46.1%, arm C's held-out recovery rate. Admitted events turn gold and
   settle; the rest pass through and fade. The animation is a readout. */
(function () {
  var host = document.getElementById('scene');
  if (!host || typeof THREE === 'undefined') return;
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  var RATE = 0.461, COUNT = 900;
  var W = function () { return host.clientWidth; }, H = function () { return host.clientHeight; };

  var scene = new THREE.Scene();
  var camera = new THREE.PerspectiveCamera(46, W() / H(), 0.1, 120);
  camera.position.set(0.4, 2.4, 15.5);
  camera.lookAt(0, 0.2, 0);

  var renderer;
  try { renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true }); }
  catch (e) { return; }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(W(), H());
  host.appendChild(renderer.domElement);

  scene.add(new THREE.AmbientLight(0xffffff, 0.62));
  var key = new THREE.DirectionalLight(0xfff0d8, 1.05); key.position.set(5, 8, 7); scene.add(key);
  var rim = new THREE.DirectionalLight(0x6f8dff, 0.55); rim.position.set(-7, 2, -5); scene.add(rim);

  var root = new THREE.Group(); scene.add(root);

  /* ---- the card: a real rounded solid, not a wireframe ---- */
  function roundedRect(w, h, r) {
    var s = new THREE.Shape();
    s.moveTo(-w / 2 + r, -h / 2);
    s.lineTo(w / 2 - r, -h / 2); s.quadraticCurveTo(w / 2, -h / 2, w / 2, -h / 2 + r);
    s.lineTo(w / 2, h / 2 - r); s.quadraticCurveTo(w / 2, h / 2, w / 2 - r, h / 2);
    s.lineTo(-w / 2 + r, h / 2); s.quadraticCurveTo(-w / 2, h / 2, -w / 2, h / 2 - r);
    s.lineTo(-w / 2, -h / 2 + r); s.quadraticCurveTo(-w / 2, -h / 2, -w / 2 + r, -h / 2);
    return s;
  }
  var cardGeo = new THREE.ExtrudeGeometry(roundedRect(6.0, 3.8, 0.34), {
    depth: 0.16, bevelEnabled: true, bevelThickness: 0.03, bevelSize: 0.03, bevelSegments: 3, curveSegments: 14
  });
  cardGeo.center();
  var card = new THREE.Mesh(cardGeo, new THREE.MeshStandardMaterial({
    color: 0x1B2130, roughness: 0.42, metalness: 0.68
  }));
  var cardGroup = new THREE.Group();
  cardGroup.add(card);

  var chip = new THREE.Mesh(
    new THREE.BoxGeometry(0.78, 0.6, 0.05),
    new THREE.MeshStandardMaterial({ color: 0xE0A33C, roughness: 0.3, metalness: 0.85 })
  );
  chip.position.set(-1.85, 0.62, 0.13); cardGroup.add(chip);

  for (var s = 0; s < 3; s++) {
    var bar = new THREE.Mesh(
      new THREE.BoxGeometry(s === 2 ? 1.5 : 2.7, 0.11, 0.02),
      new THREE.MeshStandardMaterial({ color: 0x39425C, roughness: 0.85 })
    );
    bar.position.set(s === 2 ? -1.25 : -0.65, -0.72 - s * 0.32, 0.12);
    cardGroup.add(bar);
  }
  cardGroup.rotation.set(-0.34, 0.52, 0.06);
  cardGroup.position.set(0.2, 0.1, 0);
  root.add(cardGroup);

  /* ---- the gate plane the stream must pass ---- */
  var gate = new THREE.Mesh(
    new THREE.PlaneGeometry(0.05, 9),
    new THREE.MeshBasicMaterial({ color: 0x4C63D8, transparent: true, opacity: 0.28 })
  );
  gate.position.set(-4.2, 0, 0); root.add(gate);

  /* ---- event stream ---- */
  var pos = new Float32Array(COUNT * 3), col = new Float32Array(COUNT * 3);
  var spd = new Float32Array(COUNT), got = new Uint8Array(COUNT);
  var gold = new THREE.Color(0xE0A33C), lost = new THREE.Color(0x3C4560);

  function place(i, spread) {
    var k = i * 3;
    pos[k] = -13 - Math.random() * (spread ? 20 : 5);
    pos[k + 1] = (Math.random() - 0.5) * 8.2;
    pos[k + 2] = (Math.random() - 0.5) * 8;
    spd[i] = 0.045 + Math.random() * 0.06;
    got[i] = Math.random() < RATE ? 1 : 0;
    var c = got[i] ? gold : lost;
    col[k] = c.r; col[k + 1] = c.g; col[k + 2] = c.b;
  }
  for (var i = 0; i < COUNT; i++) place(i, true);

  var geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
  root.add(new THREE.Points(geo, new THREE.PointsMaterial({
    size: 0.085, vertexColors: true, transparent: true, opacity: 0.95,
    sizeAttenuation: true, depthWrite: false
  })));

  var tx = 0, ty = 0;
  if (!reduce) {
    host.addEventListener('pointermove', function (e) {
      var r = host.getBoundingClientRect();
      tx = ((e.clientX - r.left) / r.width - 0.5) * 0.5;
      ty = ((e.clientY - r.top) / r.height - 0.5) * 0.26;
    }, { passive: true });
    host.addEventListener('pointerleave', function () { tx = 0; ty = 0; });
  }

  var t = 0;
  function frame() {
    requestAnimationFrame(frame);
    t += 0.01;
    var p = geo.attributes.position.array;
    for (var i = 0; i < COUNT; i++) {
      var k = i * 3;
      p[k] += spd[i];
      if (got[i] && p[k] > -4.2) {           /* admitted: drawn onto the card */
        p[k + 1] += (0.1 - p[k + 1]) * 0.055;
        p[k + 2] += (0 - p[k + 2]) * 0.055;
      } else if (!got[i] && p[k] > -4.2) {   /* refused: falls away */
        p[k + 1] -= 0.022;
      }
      if (p[k] > 15) place(i, false);
    }
    geo.attributes.position.needsUpdate = true;
    root.rotation.y += (tx - root.rotation.y) * 0.05;
    root.rotation.x += (ty - root.rotation.x) * 0.05;
    cardGroup.position.y = 0.1 + Math.sin(t * 0.65) * 0.13;
    cardGroup.rotation.z = 0.06 + Math.sin(t * 0.45) * 0.02;
    renderer.render(scene, camera);
  }
  frame();

  new ResizeObserver(function () {
    if (!W() || !H()) return;
    camera.aspect = W() / H(); camera.updateProjectionMatrix(); renderer.setSize(W(), H());
  }).observe(host);
})();
