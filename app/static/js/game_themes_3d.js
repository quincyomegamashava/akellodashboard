/**
 * Live Three.js scenes for tug-of-war (races) and swimming (solo).
 * Requires global THREE (three.min.js). Falls back silently if missing.
 */
(function (global) {
  "use strict";

  const REDUCE =
    typeof window !== "undefined" &&
    window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function hasThree() {
    return typeof global.THREE !== "undefined";
  }

  function makeKid(colorHex) {
    const THREE = global.THREE;
    const g = new THREE.Group();
    const skin = new THREE.MeshStandardMaterial({ color: 0xfcd9b0, roughness: 0.35 });
    const cloth = new THREE.MeshStandardMaterial({ color: colorHex, roughness: 0.55 });
    const dark = new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.7 });

    const head = new THREE.Mesh(new THREE.SphereGeometry(0.28, 12, 12), skin);
    head.position.y = 1.15;
    g.add(head);

    const body = new THREE.Mesh(new THREE.BoxGeometry(0.45, 0.55, 0.3), cloth);
    body.position.y = 0.65;
    g.add(body);

    const armL = new THREE.Mesh(new THREE.BoxGeometry(0.14, 0.45, 0.14), cloth);
    armL.position.set(-0.32, 0.7, 0);
    armL.rotation.z = 0.9;
    g.add(armL);
    const armR = armL.clone();
    armR.position.x = 0.32;
    armR.rotation.z = -0.9;
    g.add(armR);

    const legL = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.45, 0.16), dark);
    legL.position.set(-0.12, 0.2, 0);
    g.add(legL);
    const legR = legL.clone();
    legR.position.x = 0.12;
    g.add(legR);

    g.userData.arms = [armL, armR];
    g.userData.legs = [legL, legR];
    return g;
  }

  function capsuleOrBox(r, len, segs) {
    const THREE = global.THREE;
    if (THREE && typeof THREE.CapsuleGeometry === "function") {
      return new THREE.CapsuleGeometry(r, len, Math.max(2, segs || 4), 8);
    }
    return new THREE.BoxGeometry(r * 2, len + r * 2, r * 2);
  }

  function makeSwimmer() {
    const THREE = global.THREE;
    const g = new THREE.Group();
    const skin = new THREE.MeshStandardMaterial({ color: 0xfcd9b0, roughness: 0.3 });
    const suit = new THREE.MeshStandardMaterial({ color: 0x2563eb, roughness: 0.45 });

    const head = new THREE.Mesh(new THREE.SphereGeometry(0.22, 12, 12), skin);
    head.position.set(0.35, 0.05, 0);
    g.add(head);

    const torso = new THREE.Mesh(capsuleOrBox(0.16, 0.45, 4), suit);
    torso.rotation.z = Math.PI / 2;
    torso.position.set(0, 0, 0);
    g.add(torso);

    const arm = new THREE.Mesh(capsuleOrBox(0.06, 0.35, 3), skin);
    arm.position.set(0.05, 0.18, 0.12);
    g.add(arm);

    const leg = new THREE.Mesh(capsuleOrBox(0.07, 0.4, 3), suit);
    leg.position.set(-0.35, -0.05, 0);
    leg.rotation.z = 0.4;
    g.add(leg);

    g.userData.arm = arm;
    g.userData.leg = leg;
    g.userData.head = head;
    return g;
  }

  function baseScene(container, opts) {
    const THREE = global.THREE;
    const width = Math.max(120, container.clientWidth || 320);
    const height = opts.height || 200;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(opts.bg || 0xb8e0f0);

    const camera = new THREE.PerspectiveCamera(42, width / height, 0.1, 100);
    camera.position.set(opts.camX || 0, opts.camY || 3.2, opts.camZ || 7.5);
    camera.lookAt(0, 0.8, 0);

    const renderer = new THREE.WebGLRenderer({ antialias: !REDUCE, alpha: false, powerPreference: "low-power" });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, REDUCE ? 1 : 1.75));
    renderer.setSize(width, height, false);
    renderer.domElement.className = "theme-3d-canvas";
    renderer.domElement.setAttribute("aria-hidden", "true");
    container.appendChild(renderer.domElement);

    const hemi = new THREE.HemisphereLight(0xffffff, 0x88aa77, 0.95);
    scene.add(hemi);
    const dir = new THREE.DirectionalLight(0xffffff, 0.75);
    dir.position.set(4, 8, 5);
    scene.add(dir);

    const state = {
      scene,
      camera,
      renderer,
      container,
      width,
      height,
      running: true,
      t: 0,
      onFrame: null,
      bias: 0,
      targetBias: 0,
      progress: 0,
      targetProgress: 0,
      outcome: "playing",
    };

    function resize() {
      const w = Math.max(120, container.clientWidth || width);
      const h = opts.height || height;
      state.width = w;
      state.height = h;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h, false);
    }

    function frame(now) {
      if (!state.running) return;
      requestAnimationFrame(frame);
      const dt = Math.min(0.05, (now - (state._last || now)) / 1000);
      state._last = now;
      state.t += dt;
      state.bias += (state.targetBias - state.bias) * Math.min(1, dt * 4);
      state.progress += (state.targetProgress - state.progress) * Math.min(1, dt * 3);
      if (state.onFrame) state.onFrame(state, dt);
      renderer.render(scene, camera);
    }
    requestAnimationFrame(frame);

    const onResize = () => resize();
    window.addEventListener("resize", onResize);

    return {
      state,
      resize,
      dispose() {
        state.running = false;
        window.removeEventListener("resize", onResize);
        try {
          renderer.dispose();
          if (renderer.domElement && renderer.domElement.parentNode) {
            renderer.domElement.parentNode.removeChild(renderer.domElement);
          }
        } catch (_) { /* ignore */ }
      },
    };
  }

  function mountTug(container) {
    if (!hasThree() || !container) return null;
    container.innerHTML = "";
    const host = document.createElement("div");
    host.className = "theme-3d-host";
    container.appendChild(host);

    const api = baseScene(host, { height: 210, bg: 0xc7e8f5, camY: 2.8, camZ: 8.2 });
    const THREE = global.THREE;
    const { state } = api;
    const scene = state.scene;

    // Ground
    const ground = new THREE.Mesh(
      new THREE.PlaneGeometry(16, 8),
      new THREE.MeshStandardMaterial({ color: 0x86b86b, roughness: 0.9 })
    );
    ground.rotation.x = -Math.PI / 2;
    ground.position.y = 0;
    scene.add(ground);

    // Midline flag pole
    const pole = new THREE.Mesh(
      new THREE.CylinderGeometry(0.04, 0.04, 2.2, 8),
      new THREE.MeshStandardMaterial({ color: 0x64748b })
    );
    pole.position.set(0, 1.1, -0.8);
    scene.add(pole);

    const team1 = new THREE.Group();
    const team2 = new THREE.Group();
    for (let i = 0; i < 3; i++) {
      const k1 = makeKid(0x2563eb);
      k1.position.set(-2.4 - i * 0.55, 0, (i - 1) * 0.35);
      k1.rotation.y = Math.PI / 2;
      team1.add(k1);
      const k2 = makeKid(0xea580c);
      k2.position.set(2.4 + i * 0.55, 0, (i - 1) * 0.35);
      k2.rotation.y = -Math.PI / 2;
      team2.add(k2);
    }
    scene.add(team1);
    scene.add(team2);

    const ropeMat = new THREE.MeshStandardMaterial({ color: 0xb45309, roughness: 0.55 });
    const rope = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, 7.2, 8), ropeMat);
    rope.rotation.z = Math.PI / 2;
    rope.position.y = 0.85;
    scene.add(rope);

    const knot = new THREE.Mesh(
      new THREE.SphereGeometry(0.18, 12, 12),
      new THREE.MeshStandardMaterial({ color: 0xfbbf24, metalness: 0.2 })
    );
    knot.position.y = 0.85;
    scene.add(knot);

    state.onFrame = (s) => {
      const pull = s.bias; // -1 .. 1
      const x = pull * 1.8;
      team1.position.x = x;
      team2.position.x = x;
      rope.position.x = x;
      knot.position.x = x;
      if (!REDUCE) {
        const wiggle = Math.sin(s.t * 8) * 0.08;
        team1.children.forEach((kid, i) => {
          const arms = kid.userData.arms || [];
          arms.forEach((a, ai) => {
            a.rotation.z = (ai === 0 ? 0.9 : -0.9) + wiggle * (i % 2 ? 1 : -1);
          });
        });
        team2.children.forEach((kid, i) => {
          const arms = kid.userData.arms || [];
          arms.forEach((a, ai) => {
            a.rotation.z = (ai === 0 ? 0.9 : -0.9) + wiggle * (i % 2 ? -1 : 1);
          });
        });
      }
    };

    return {
      setBias(biasPct) {
        // biasPct from CSS version was -40..40; normalize to -1..1
        state.targetBias = Math.max(-1, Math.min(1, (Number(biasPct) || 0) / 40));
      },
      setScores() { /* scores shown in HTML banners */ },
      resize: api.resize,
      dispose: api.dispose,
    };
  }

  function mountSwim(container) {
    if (!hasThree() || !container) return null;
    // Keep CSS fallback actor hidden; replace stage content with 3D host
    container.innerHTML = "";
    const host = document.createElement("div");
    host.className = "theme-3d-host";
    container.appendChild(host);

    const api = baseScene(host, { height: 220, bg: 0x38bdf8, camX: 0.5, camY: 2.4, camZ: 6.5 });
    const THREE = global.THREE;
    const { state } = api;
    const scene = state.scene;

    // Water plane
    const water = new THREE.Mesh(
      new THREE.PlaneGeometry(14, 8),
      new THREE.MeshStandardMaterial({ color: 0x0284c7, roughness: 0.35, metalness: 0.1 })
    );
    water.rotation.x = -Math.PI / 2;
    water.position.y = 0.15;
    scene.add(water);

    // Deep water backdrop
    const deep = new THREE.Mesh(
      new THREE.PlaneGeometry(14, 4),
      new THREE.MeshStandardMaterial({ color: 0x0369a1, roughness: 0.8 })
    );
    deep.position.set(0, -1.2, -2);
    scene.add(deep);

    // Shore (right)
    const shore = new THREE.Mesh(
      new THREE.BoxGeometry(3.2, 0.5, 5),
      new THREE.MeshStandardMaterial({ color: 0xfbbf24, roughness: 0.85 })
    );
    shore.position.set(4.2, 0.35, 0);
    scene.add(shore);

    const palm = new THREE.Mesh(
      new THREE.CylinderGeometry(0.08, 0.12, 1.6, 6),
      new THREE.MeshStandardMaterial({ color: 0x92400e })
    );
    palm.position.set(4.5, 1.1, -0.8);
    scene.add(palm);

    const swimmer = makeSwimmer();
    swimmer.position.set(-3.2, 0.45, 0.2);
    scene.add(swimmer);

    // Bubbles
    const bubbles = [];
    if (!REDUCE) {
      const bmat = new THREE.MeshStandardMaterial({ color: 0xffffff, transparent: true, opacity: 0.45 });
      for (let i = 0; i < 8; i++) {
        const b = new THREE.Mesh(new THREE.SphereGeometry(0.05 + Math.random() * 0.04, 6, 6), bmat);
        b.position.set(-2 + Math.random() * 4, 0.3 + Math.random(), (Math.random() - 0.5) * 2);
        scene.add(b);
        bubbles.push(b);
      }
    }

    state.onFrame = (s) => {
      const pos = s.progress; // 0..1 toward shore
      const baseX = -3.2 + pos * 6.2;
      let y = 0.45;
      let rotZ = 0;
      if (s.outcome === "fail") {
        y = 0.05 + Math.sin(s.t * 3) * 0.04;
        rotZ = -0.6;
        swimmer.rotation.x = 0.5;
      } else if (s.outcome === "win") {
        y = 0.85;
        swimmer.position.x = 3.4;
        swimmer.rotation.set(0, 0, 0);
      } else {
        swimmer.rotation.x = 0;
        if (!REDUCE) {
          const kick = Math.sin(s.t * 7);
          if (swimmer.userData.arm) swimmer.userData.arm.rotation.z = kick * 0.5;
          if (swimmer.userData.leg) swimmer.userData.leg.rotation.z = 0.4 + kick * 0.35;
          y = 0.42 + Math.sin(s.t * 2.2) * 0.06;
        }
      }
      if (s.outcome !== "win") {
        swimmer.position.x = baseX;
        swimmer.position.y = y;
        swimmer.rotation.z = rotZ;
      }
      bubbles.forEach((b, i) => {
        b.position.y += 0.01 + (i % 3) * 0.004;
        if (b.position.y > 2.2) b.position.y = 0.2;
      });
      // Gentle camera follow
      s.camera.position.x = 0.3 + pos * 0.8;
      s.camera.lookAt(swimmer.position.x * 0.4, 0.6, 0);
    };

    return {
      setProgress(frac) {
        state.targetProgress = Math.max(0, Math.min(1, Number(frac) || 0));
      },
      setOutcome(outcome) {
        state.outcome = outcome || "playing";
        if (outcome === "win") state.targetProgress = 1;
      },
      resize: api.resize,
      dispose: api.dispose,
    };
  }

  global.GameThemes3D = {
    available: hasThree,
    mountTug,
    mountSwim,
  };
})(typeof window !== "undefined" ? window : globalThis);
