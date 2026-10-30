// MintRadar — medan blok 3D di pembuka (D43). Data SEBENAR: stats.json `peta` (kontrak paling banyak dimint × 60 minit);
// baris = kontrak, lajur = minit, ketinggian = mint. Sinar = sekarang, menyapu dari minit tertua ke terbaru.
// Perangkap hos: TIADA AdditiveBlending (kanvas lutsinar = piksel legap hitam, D35 peroduasa3d) — kanvas legap + campuran biasa;
// tiada filter/backdrop-filter beranimasi (WebKit crash). Dijeda di luar skrin / tab tersembunyi. Gagal = skop SVG kekal.
import * as THREE from "/vendor/three-0.160.0.module.min.js";

const medan = document.getElementById("medan");
const tip = document.getElementById("medan-tip");
const DIAM = matchMedia("(prefers-reduced-motion: reduce)").matches;
const LAUT = 0x0d2830, KACA = new THREE.Color(0x9fe3d4), LOYANG = new THREE.Color(0xd9b85e), MERAH = new THREE.Color(0xef8b7b);
const ASAS = new THREE.Color(0x173b44), PUDAR = new THREE.Color(0x1f5a63), PUNCAK = new THREE.Color(0xe8c46a);
const LAJUR = 60, SAIZ = 0.17, JARAK = 0.205;
const MS = document.documentElement.lang === "ms";

function mula(data) {
  const peta = (data && data.peta && data.peta.kontrak) || [];
  if (!peta.length) return;
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: "low-power" });
  renderer.setClearColor(LAUT, 1);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.domElement.className = "medan-kanvas";
  renderer.domElement.setAttribute("aria-hidden", "true");

  const scene = new THREE.Scene();
  scene.fog = new THREE.Fog(LAUT, 7, 17);
  const camera = new THREE.PerspectiveCamera(34, 1, 0.1, 60);
  scene.add(new THREE.HemisphereLight(0xe6fbf6, 0x0d2830, 1.25));
  const matahari = new THREE.DirectionalLight(0xffffff, 1.9);
  matahari.position.set(-3, 9, 4);
  const sisi = new THREE.DirectionalLight(0x9fe3d4, 0.55);
  sisi.position.set(6, 3, -4);
  scene.add(sisi);
  scene.add(matahari);

  const kumpulan = new THREE.Group();
  scene.add(kumpulan);
  const barisN = Math.min(peta.length, 8);
  const lebar = LAJUR * JARAK, dalam = barisN * JARAK * 1.6;
  const lantai = new THREE.GridHelper(Math.max(lebar, dalam) * 1.6, 48, 0x24505a, 0x183d46);
  lantai.position.y = -0.002;
  kumpulan.add(lantai);

  const kotak = new THREE.BoxGeometry(1, 1, 1);
  kotak.translate(0, 0.5, 0);
  const bahan = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.55, metalness: 0.08 });
  const blok = new THREE.InstancedMesh(kotak, bahan, barisN * LAJUR);
  blok.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  kumpulan.add(blok);

  // sinar sekarang: satah nipis, campuran biasa (BUKAN tambahan)
  const sinar = new THREE.Mesh(new THREE.BoxGeometry(0.06, 2.2, dalam + 0.8),
    new THREE.MeshBasicMaterial({ color: KACA, transparent: true, opacity: 0.3, depthWrite: false }));
  sinar.position.y = 1.1;
  kumpulan.add(sinar);
  const sinarTepi = new THREE.Mesh(new THREE.BoxGeometry(0.07, 0.035, dalam + 0.8), new THREE.MeshBasicMaterial({ color: LOYANG }));
  sinarTepi.position.y = 2.2;
  kumpulan.add(sinarTepi);
  const garisKini = new THREE.Mesh(new THREE.BoxGeometry(0.025, 0.02, dalam + 0.6), new THREE.MeshBasicMaterial({ color: LOYANG }));
  garisKini.position.set(lebar / 2, 0.01, 0);
  kumpulan.add(garisKini);

  const m4 = new THREE.Matrix4(), warna = new THREE.Color();
  let tinggi = [], asasWarna = [], mx = 1, baris = [];

  function isi(d) {
    baris = ((d && d.peta && d.peta.kontrak) || []).slice(0, barisN);
    mx = 1;
    baris.forEach((k) => k.minit.forEach((v) => { if (v > mx) mx = v; }));
    tinggi = []; asasWarna = [];
    baris.forEach((k, r) => {
      const tint = k.label === "merah" ? MERAH : k.label === "kuning" ? LOYANG : KACA;
      k.minit.slice(-LAJUR).forEach((v, c) => {
        const i = r * LAJUR + c, f = v > 0 ? Math.log1p(v) / Math.log1p(mx) : 0;
        const h = v > 0 ? 0.06 + 1.55 * f : 0.025;
        tinggi[i] = h;
        // warna ikut intensiti: gelap → kaca laut → loyang pada 10 % teratas (yang paling panas kelihatan bercahaya)
        const w = v > 0 ? (f > 0.9 ? KACA.clone().lerp(PUNCAK, (f - 0.9) * 10) : PUDAR.clone().lerp(KACA, Math.pow(f, 1.4))).lerp(tint, 0.12)
                        : ASAS.clone();
        asasWarna[i] = w;
        m4.makeScale(SAIZ, h, SAIZ);
        m4.setPosition(c * JARAK - lebar / 2, 0, (r - (barisN - 1) / 2) * JARAK * 1.6);
        blok.setMatrixAt(i, m4);
        blok.setColorAt(i, w);
      });
    });
    blok.count = baris.length * LAJUR;
    blok.instanceMatrix.needsUpdate = true;
    if (blok.instanceColor) blok.instanceColor.needsUpdate = true;
  }
  isi(data);

  // kamera ikut saiz: desktop = medan di kanan teks; telefon = jalur di atas teks
  let lebarSkrin = 0;
  function saiz() {
    const r = medan.getBoundingClientRect();
    const w = Math.max(1, Math.round(r.width)), h = Math.max(1, Math.round(r.height));
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    lebarSkrin = w;
    const desktop = w >= 860;
    // desktop: medan di kanan teks; telefon: 30 minit terbaru di tengah, kamera lebih dekat (jalur 300 px)
    kumpulan.position.x = desktop ? lebar * 0.3 : -lebar * 0.24;
    camera.position.set(desktop ? -0.2 : 0.4, desktop ? 4.6 : 3.6, desktop ? 8.0 : 6.4);
    camera.lookAt(desktop ? lebar * 0.2 : 0.2, desktop ? 0.35 : 0.55, 0);
    camera.updateProjectionMatrix();
    lukis(performance.now());
  }

  let arah = 0, arahSasar = 0, tSapu = 0, hidup = true, kelihatan = true, akhir = performance.now();
  const PUSING = 7000;  // ms satu sapuan

  function lukis(kini) {
    const dt = Math.min(64, kini - akhir); akhir = kini;
    if (!DIAM) {
      tSapu = (tSapu + dt / PUSING) % 1;
      arah += (arahSasar - arah) * 0.06;
      kumpulan.rotation.y = arah;
    } else {
      tSapu = 1;
    }
    const xs = tSapu * lebar - lebar / 2;
    sinar.position.x = xs;
    sinarTepi.position.x = xs;
    const lajurSapu = tSapu * (LAJUR - 1);
    for (let i = 0; i < baris.length * LAJUR; i++) {
      const c = i % LAJUR, dekat = Math.max(0, 1 - Math.abs(c - lajurSapu) / 2.2);
      if (dekat > 0 && tinggi[i] > 0.03) {
        warna.copy(asasWarna[i]).lerp(KACA, 0.7 * dekat);
        blok.setColorAt(i, warna);
      } else if (asasWarna[i]) {
        blok.setColorAt(i, asasWarna[i]);
      }
    }
    if (blok.instanceColor) blok.instanceColor.needsUpdate = true;
    renderer.render(scene, camera);
  }

  function gelung(kini) {
    if (!hidup) return;
    if (kelihatan && !document.hidden) lukis(kini);
    if (!DIAM) requestAnimationFrame(gelung);
  }

  // tuding: sedikit pusing (desktop) + petua blok
  const ray = new THREE.Raycaster(), tuding = new THREE.Vector2();
  medan.addEventListener("pointermove", (ev) => {
    const r = medan.getBoundingClientRect();
    tuding.set(((ev.clientX - r.left) / r.width) * 2 - 1, -((ev.clientY - r.top) / r.height) * 2 + 1);
    if (!DIAM && ev.pointerType === "mouse") arahSasar = tuding.x * 0.12;
    ray.setFromCamera(tuding, camera);
    const kena = ray.intersectObject(blok)[0];
    if (kena && kena.instanceId !== undefined && baris.length) {
      const r2 = Math.floor(kena.instanceId / LAJUR), c = kena.instanceId % LAJUR, k = baris[r2];
      const v = k.minit.slice(-LAJUR)[c] || 0;
      tip.textContent = (k.nama || "—") + " · " + (LAJUR - c) + (MS ? " min lalu · " : " min ago · ") + v + (MS || v === 1 ? " mint" : " mints");
      tip.style.left = Math.min(r.width - 220, ev.clientX - r.left + 14) + "px";
      tip.style.top = (ev.clientY - r.top + 14) + "px";
      tip.hidden = false;
    } else {
      tip.hidden = true;
    }
  });
  medan.addEventListener("pointerleave", () => { tip.hidden = true; arahSasar = 0; });

  new IntersectionObserver((e) => { kelihatan = e[0].isIntersecting; }).observe(medan);
  new ResizeObserver(saiz).observe(medan);
  document.addEventListener("mr-data", (ev) => { isi(ev.detail); if (DIAM) lukis(performance.now()); });
  renderer.domElement.addEventListener("webglcontextlost", (ev) => { ev.preventDefault(); hidup = false; medan.classList.remove("ada-3d"); });

  medan.prepend(renderer.domElement);
  medan.classList.add("ada-3d");
  document.getElementById("medan-ket").hidden = false;
  saiz();
  if (!DIAM) requestAnimationFrame(gelung);
}

try {
  if (window.MR_DATA) mula(window.MR_DATA);
  else document.addEventListener("mr-data", (ev) => mula(ev.detail), { once: true });
} catch (e) {
  medan.classList.remove("ada-3d");  // skop SVG kekal sebagai sandaran
}
