// ShopShare marketing site — nav behavior, scroll reveals, waitlist form,
// and a small Three.js scene that builds the tote-bag mark in 3D.

document.getElementById('year').textContent = new Date().getFullYear();

/* ---------------- nav ---------------- */
const nav = document.getElementById('nav');
const burger = document.getElementById('navBurger');
const mobileMenu = document.getElementById('navMobile');

window.addEventListener('scroll', () => {
  nav.classList.toggle('scrolled', window.scrollY > 12);
}, { passive: true });

burger.addEventListener('click', () => {
  const open = mobileMenu.classList.toggle('open');
  burger.setAttribute('aria-expanded', String(open));
  burger.classList.toggle('is-open', open);
});
mobileMenu.querySelectorAll('a').forEach((link) => {
  link.addEventListener('click', () => {
    mobileMenu.classList.remove('open');
    burger.setAttribute('aria-expanded', 'false');
  });
});

/* ---------------- scroll reveal ---------------- */
const revealTargets = document.querySelectorAll('.reveal');
if ('IntersectionObserver' in window) {
  const io = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        io.unobserve(entry.target);
      }
    });
  }, { threshold: 0.15, rootMargin: '0px 0px -60px 0px' });
  revealTargets.forEach((el, i) => {
    el.style.transitionDelay = `${Math.min(i % 6, 5) * 60}ms`;
    io.observe(el);
  });
} else {
  revealTargets.forEach((el) => el.classList.add('is-visible'));
}

/* ---------------- waitlist form (front-end only demo) ---------------- */
const form = document.getElementById('waitlistForm');
const note = document.getElementById('waitlistNote');
form.addEventListener('submit', (e) => {
  e.preventDefault();
  const input = form.querySelector('input');
  if (!input.value) return;
  note.textContent = `You're on the list! We'll email ${input.value} when ShopShare launches at your school.`;
  form.reset();
  input.blur();
});

/* ---------------- 3D hero scene ---------------- */
(function initHeroScene() {
  const stage = document.getElementById('heroStage');
  const canvas = document.getElementById('heroCanvas');
  if (!stage || !canvas || typeof THREE === 'undefined') return;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  const COLORS = {
    bag: 0x2d6a4f,
    bagDark: 0x1f4d38,
    handle: 0x95d5b2,
    leaf: 0xb7e4c7,
    leafDark: 0x95d5b2,
  };

  let width = stage.clientWidth;
  let height = stage.clientHeight;

  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setSize(width, height);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(38, width / height, 0.1, 100);
  camera.position.set(0, 0.4, 7.2);

  // lighting — soft studio setup. Kept deliberately dim: MeshStandardMaterial
  // + this renderer's default (no tone mapping) clips to white fast, so a
  // "reasonable" ambient/key intensity here reads as washed-out pastel
  // instead of the actual brand green.
  scene.add(new THREE.AmbientLight(0xffffff, 0.42));
  const key = new THREE.DirectionalLight(0xffffff, 0.5);
  key.position.set(4, 6, 5);
  scene.add(key);
  const rim = new THREE.DirectionalLight(0x95d5b2, 0.3);
  rim.position.set(-5, -2, -4);
  scene.add(rim);

  const group = new THREE.Group();
  scene.add(group);

  // ---- tote bag body: tapered box built from an extruded trapezoid ----
  const bagShape = new THREE.Shape();
  bagShape.moveTo(-1.05, 0.85);
  bagShape.lineTo(1.05, 0.85);
  bagShape.lineTo(0.82, -0.95);
  bagShape.quadraticCurveTo(0.78, -1.1, 0.62, -1.1);
  bagShape.lineTo(-0.62, -1.1);
  bagShape.quadraticCurveTo(-0.78, -1.1, -0.82, -0.95);
  bagShape.lineTo(-1.05, 0.85);

  // NOTE: every part below is placed in the same shape-space coordinates
  // the bagShape was drawn in (y: -1.1 bottom to 0.85 top edge; extrude
  // depth 0.62 + ~0.04 bevel puts z roughly 0 to 0.7, front-facing).
  // Deliberately NOT calling .geometry.center() on individual meshes —
  // that recenters each mesh independently and throws off their relative
  // alignment. Instead the whole composed group is shifted once at the
  // end so it's centered in view.
  const bagGeo = new THREE.ExtrudeGeometry(bagShape, {
    depth: 0.62,
    bevelEnabled: true,
    bevelThickness: 0.04,
    bevelSize: 0.04,
    bevelSegments: 3,
    curveSegments: 12,
  });
  const bagMat = new THREE.MeshStandardMaterial({ color: COLORS.bag, roughness: 0.55, metalness: 0.06 });
  const bag = new THREE.Mesh(bagGeo, bagMat);
  group.add(bag);

  // seam line, just under the top edge, sitting just proud of the front face
  const seamGeo = new THREE.BoxGeometry(1.2, 0.05, 0.02);
  const seamMat = new THREE.MeshStandardMaterial({ color: 0xffffff, transparent: true, opacity: 0.32 });
  const seam = new THREE.Mesh(seamGeo, seamMat);
  seam.position.set(0, 0.66, 0.68);
  group.add(seam);

  // ---- handle: half-torus arch rising from the top edge ----
  // Default TorusGeometry arc sweeps from angle 0 (+X) through PI/2 (+Y) to
  // PI (-X), which is already the upper "⌒" dome shape we want — no extra
  // rotation needed, that would flip it into a "⌣" dipping into the bag.
  const handleGeo = new THREE.TorusGeometry(0.56, 0.075, 16, 48, Math.PI);
  const handleMat = new THREE.MeshStandardMaterial({ color: COLORS.handle, roughness: 0.5 });
  const handle = new THREE.Mesh(handleGeo, handleMat);
  handle.position.set(0, 0.85, 0.31);
  group.add(handle);

  // ---- sprouting leaf ----
  const leafShape = new THREE.Shape();
  leafShape.moveTo(0, 0.5);
  leafShape.quadraticCurveTo(-0.32, 0.42, -0.32, 0.12);
  leafShape.quadraticCurveTo(-0.32, -0.18, 0, -0.18);
  leafShape.quadraticCurveTo(0.32, -0.18, 0.32, 0.12);
  leafShape.quadraticCurveTo(0.32, 0.42, 0, 0.5);
  const leafGeo = new THREE.ExtrudeGeometry(leafShape, { depth: 0.06, bevelEnabled: false, curveSegments: 10 });
  leafGeo.center();
  const leafMat = new THREE.MeshStandardMaterial({ color: COLORS.leaf, roughness: 0.4 });
  const leaf = new THREE.Mesh(leafGeo, leafMat);
  leaf.scale.setScalar(0.85);
  leaf.rotation.z = -0.32;
  leaf.rotation.x = -0.1;
  leaf.position.set(0, 1.69, 0.33);
  group.add(leaf);

  // ---- floating accent chips (little depth-of-field detail, on brand) ----
  const chipGeo = new THREE.IcosahedronGeometry(0.14, 0);
  const chipColors = [COLORS.handle, COLORS.leaf, COLORS.bag];
  const chips = [];
  for (let i = 0; i < 5; i++) {
    const mat = new THREE.MeshStandardMaterial({ color: chipColors[i % chipColors.length], roughness: 0.4 });
    const chip = new THREE.Mesh(chipGeo, mat);
    const angle = (i / 5) * Math.PI * 2;
    chip.userData.baseAngle = angle;
    chip.userData.radius = 2.5 + (i % 2) * 0.4;
    chip.userData.speed = 0.15 + i * 0.03;
    chip.userData.yOff = (i - 2) * 0.35;
    chip.scale.setScalar(0.7 + (i % 3) * 0.25);
    scene.add(chip);
    chips.push(chip);
  }

  // Center the composed bag+handle+leaf group in view: bag bottom sits at
  // y=-1.1, leaf top at roughly y=1.9, so the vertical midpoint is ~0.4;
  // the bag's extrude depth (plus bevel) spans roughly z=0 to 0.66.
  group.position.set(0, -0.4, -0.33);
  group.rotation.set(0.12, -0.5, 0);
  group.scale.setScalar(1.05);

  // parallax targets
  let targetRotY = -0.5;
  let targetRotX = 0.12;
  stage.addEventListener('pointermove', (e) => {
    const rect = stage.getBoundingClientRect();
    const px = (e.clientX - rect.left) / rect.width - 0.5;
    const py = (e.clientY - rect.top) / rect.height - 0.5;
    targetRotY = -0.5 + px * 0.6;
    targetRotX = 0.12 - py * 0.35;
  });
  stage.addEventListener('pointerleave', () => {
    targetRotY = -0.5;
    targetRotX = 0.12;
  });

  const clock = new THREE.Clock();
  function animate() {
    const t = clock.getElapsedTime();

    group.rotation.y += (targetRotY + Math.sin(t * 0.25) * 0.08 - group.rotation.y) * 0.04;
    group.rotation.x += (targetRotX - group.rotation.x) * 0.04;
    group.position.y = Math.sin(t * 0.8) * 0.08;

    chips.forEach((chip) => {
      const a = chip.userData.baseAngle + t * chip.userData.speed;
      chip.position.set(
        Math.cos(a) * chip.userData.radius,
        chip.userData.yOff + Math.sin(t * 0.6 + chip.userData.baseAngle) * 0.25,
        Math.sin(a) * chip.userData.radius - 2
      );
      chip.rotation.x += 0.006;
      chip.rotation.y += 0.008;
    });

    renderer.render(scene, camera);
    requestAnimationFrame(animate);
  }
  animate();

  function handleResize() {
    width = stage.clientWidth;
    height = stage.clientHeight;
    if (!width || !height) return;
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    renderer.setSize(width, height);
  }
  window.addEventListener('resize', handleResize);
})();
