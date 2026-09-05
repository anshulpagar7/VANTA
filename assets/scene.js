/* VANTA hero scene.
   A stream of payment events flows toward a card. Most pass through unrecovered
   and dim out; a share are caught and turn amber. The recovered share is the
   project's actual held-out figure, so the animation is a readout, not decor. */
(function () {
  var host = document.getElementById('scene');
  if (!host || typeof THREE === 'undefined') return;

  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  var RECOVERY_RATE = 0.461;   // held-out suite, arm C
  var COUNT = 1400;

  var scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x070A12, 0.055);

  var camera = new THREE.PerspectiveCamera(52, host.clientWidth / host.clientHeight, 0.1, 100);
  camera.position.set(0, 1.6, 13);
  camera.lookAt(0, 0, 0);

  var renderer;
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  } catch (e) { return; }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(host.clientWidth, host.clientHeight);
  host.appendChild(renderer.domElement);

  var root = new THREE.Group();
  scene.add(root);

  /* ---- the card: wireframe, deliberately unglossy ---- */
  var cardGeo = new THREE.BoxGeometry(5.4, 3.4, 0.08);
  var card = new THREE.Mesh(
    cardGeo,
    new THREE.MeshBasicMaterial({ color: 0x0E1422, transparent: true, opacity: 0.82 })
  );
  var cardEdges = new THREE.LineSegments(
    new THREE.EdgesGeometry(cardGeo),
    new THREE.LineBasicMaterial({ color: 0xE2A63F, transparent: true, opacity: 0.55 })
  );
  var cardGroup = new THREE.Group();
  cardGroup.add(card, cardEdges);

  /* chip + stripe, as line work rather than texture */
  var chipGeo = new THREE.BoxGeometry(0.8, 0.62, 0.02);
  var chip = new THREE.LineSegments(
    new THREE.EdgesGeometry(chipGeo),
    new THREE.LineBasicMaterial({ color: 0x5BC9A6, transparent: true, opacity: 0.7 })
  );
  chip.position.set(-1.7, 0.55, 0.06);
  cardGroup.add(chip);

  for (var s = 0; s < 3; s++) {
    var lineGeo = new THREE.BufferGeometry().setFromPoints([
      new THREE.Vector3(-1.9, -0.75 - s * 0.28, 0.06),
      new THREE.Vector3(-1.9 + (s === 2 ? 1.6 : 2.9), -0.75 - s * 0.28, 0.06)
    ]);
    cardGroup.add(new THREE.Line(lineGeo,
      new THREE.LineBasicMaterial({ color: 0x1F2A42, transparent: true, opacity: 0.9 })));
  }
  cardGroup.rotation.set(-0.12, -0.42, 0.04);
  cardGroup.position.set(1.6, 0.1, 0);
  root.add(cardGroup);

  /* ---- event stream ---- */
  var pos = new Float32Array(COUNT * 3);
  var col = new Float32Array(COUNT * 3);
  var speed = new Float32Array(COUNT);
  var recovered = new Uint8Array(COUNT);

  var cLost = new THREE.Color(0x33405C);
  var cGot = new THREE.Color(0xE2A63F);

  function place(i, fresh) {
    var i3 = i * 3;
    pos[i3] = -16 - Math.random() * (fresh ? 22 : 6);
    pos[i3 + 1] = (Math.random() - 0.5) * 7.5;
    pos[i3 + 2] = (Math.random() - 0.5) * 7;
    speed[i] = 0.035 + Math.random() * 0.055;
    recovered[i] = Math.random() < RECOVERY_RATE ? 1 : 0;
    var c = recovered[i] ? cGot : cLost;
    col[i3] = c.r; col[i3 + 1] = c.g; col[i3 + 2] = c.b;
  }
  for (var i = 0; i < COUNT; i++) place(i, true);

  var geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.setAttribute('color', new THREE.BufferAttribute(col, 3));
  var points = new THREE.Points(geo, new THREE.PointsMaterial({
    size: 0.075, vertexColors: true, transparent: true, opacity: 0.92,
    sizeAttenuation: true, depthWrite: false
  }));
  root.add(points);

  /* ---- interaction: gentle parallax, no orbit controls needed ---- */
  var targetX = 0, targetY = 0;
  if (!reduce) {
    window.addEventListener('pointermove', function (e) {
      targetX = (e.clientX / window.innerWidth - 0.5) * 0.34;
      targetY = (e.clientY / window.innerHeight - 0.5) * 0.20;
    }, { passive: true });
  }

  var t = 0;
  function frame() {
    requestAnimationFrame(frame);
    t += 0.01;

    var p = geo.attributes.position.array;
    for (var i = 0; i < COUNT; i++) {
      var i3 = i * 3;
      p[i3] += speed[i];
      /* recovered events are pulled toward the card plane; the rest drift past */
      if (recovered[i] && p[i3] > -2 && p[i3] < 1.6) {
        p[i3 + 1] += (0.1 - p[i3 + 1]) * 0.035;
        p[i3 + 2] += (0 - p[i3 + 2]) * 0.035;
      }
      if (p[i3] > 17) place(i, false);
    }
    geo.attributes.position.needsUpdate = true;

    root.rotation.y += (targetX - root.rotation.y) * 0.045;
    root.rotation.x += (targetY - root.rotation.x) * 0.045;
    cardGroup.position.y = 0.1 + Math.sin(t * 0.7) * 0.12;

    renderer.render(scene, camera);
  }
  frame();

  window.addEventListener('resize', function () {
    camera.aspect = host.clientWidth / host.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(host.clientWidth, host.clientHeight);
  });
})();
