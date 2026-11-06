// landing.js · Portada: barra fija, recorrido por la app y animaciones.
// En la compu la app se explica con paneles grandes; en el celular, con un
// teléfono que se desliza con el dedo.

import { startDemo } from "../api.js";
import { money } from "../format.js";
import { countUp, reducedMotion } from "../ui.js";

// Ya la abrió desde el ícono: no tiene sentido explicarle cómo instalarla
if (matchMedia("(display-mode: standalone)").matches || navigator.standalone === true) {
  document.getElementById("instalar")?.remove();
}

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const isDesktop = () => matchMedia("(min-width: 768px)").matches;
const calm = reducedMotion();

// --- Probar la demo (hay un botón arriba y otro al final) ---
$$("[data-demo]").forEach((btn) => {
  const label = btn.lastChild.textContent;
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    btn.lastChild.textContent = "Preparando la demo…";
    try { await startDemo(); } catch { btn.disabled = false; btn.lastChild.textContent = label; }
  });
});

$("#year").textContent = new Date().getFullYear();

// --- Barra de arriba ---
const bar = $(".site-bar");
const progress = $(".bar-progress");
const heroPhone = $("[data-hero-phone]");
let scrollQueued = false;
function onScroll() {
  scrollQueued = false;
  const max = document.documentElement.scrollHeight - innerHeight;
  bar.classList.toggle("scrolled", scrollY > 12);
  progress.style.transform = `scaleX(${max > 0 ? Math.min(scrollY / max, 1) : 0})`;
  // En el celular, el teléfono de arriba sube un poco mientras bajás
  if (!isDesktop() && !calm && scrollY < innerHeight) heroPhone.style.translate = `0 ${-scrollY * 0.12}px`;
}
addEventListener("scroll", () => {
  if (!scrollQueued) { scrollQueued = true; requestAnimationFrame(onScroll); }
}, { passive: true });
onScroll();

// "Crear cuenta" entra en la barra cuando el botón grande de la portada ya no se ve
new IntersectionObserver(([entry]) => bar.classList.toggle("cta-on", !entry.isIntersecting), {
  rootMargin: "-70px 0px 0px 0px",
}).observe($("[data-hero-cta]"));

// --- Primera pantalla ---
function countAll(root) {
  $$("[data-count]", root).forEach((el) => {
    el.dataset.value = 0;
    countUp(el, Number(el.dataset.count) * 100);
  });
}
countAll($("[data-hero]"));

// Compu: las tarjetas se mueven apenas con el mouse, cada una a su profundidad
if (!calm && matchMedia("(hover: hover)").matches) {
  const layers = $$("[data-depth]");
  addEventListener("pointermove", (e) => {
    if (!isDesktop()) return;
    const x = e.clientX / innerWidth - 0.5;
    const y = e.clientY / innerHeight - 0.5;
    layers.forEach((el) => { el.style.translate = `${-x * el.dataset.depth}px ${-y * el.dataset.depth}px`; });
  }, { passive: true });
  // La ventana de navegador se inclina hacia donde está el mouse
  const browser = $(".browser");
  browser?.addEventListener("pointermove", (e) => {
    const r = browser.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - 0.5;
    const y = (e.clientY - r.top) / r.height - 0.5;
    browser.style.transform = `perspective(1400px) rotateX(${-y * 4}deg) rotateY(${x * 5}deg)`;
  });
  browser?.addEventListener("pointerleave", () => { browser.style.transform = ""; });
}

// --- Recorrido por la app: un teléfono, varias pantallas ---
const screens = $$("[data-screen]");
const texts = $$(".tour-text");
const chips = $$("[data-chip]");
const nav = $$("[data-tour-nav] > span");
const chipRow = $(".tour-chips");
let current = -1;
let playId = 0;  // si cambiás de pantalla a la mitad, la animación anterior se corta

/** Gasto rápido: se "escribe" el monto, se elige la categoría y se guarda. */
async function playExpense(root, id) {
  const amount = $("[data-typing]", root);
  const plata = $("[data-plata]", root);
  const cat = $("[data-pick]", root);
  root.classList.remove("saved", "pressing");
  cat.classList.remove("on");
  amount.textContent = "$ 0";
  plata.textContent = money(1634000);
  if (calm) {
    amount.textContent = "$ 180";
    cat.classList.add("on");
    plata.textContent = money(1616000);
    root.classList.add("saved");
    return;
  }
  await wait(800);
  for (const text of ["$ 1", "$ 18", "$ 180"]) {
    if (id !== playId) return;
    amount.textContent = text;
    await wait(300);
  }
  if (id !== playId) return;
  cat.classList.add("on");
  await wait(550);
  if (id !== playId) return;
  root.classList.add("pressing");
  await wait(170);
  root.classList.remove("pressing");
  root.classList.add("saved");
  plata.dataset.value = 1634000;
  countUp(plata, 1616000);
}

function show(i) {
  if (i === current) return;
  current = i;
  playId += 1;
  screens.forEach((s, n) => s.classList.toggle("in", n === i));
  texts.forEach((t, n) => t.classList.toggle("on", n === i));
  chips.forEach((c, n) => {
    c.setAttribute("aria-pressed", String(n === i));
    if (n === i && chipRow.scrollWidth > chipRow.clientWidth) {
      chipRow.scrollTo({ left: c.offsetLeft - chipRow.clientWidth / 2 + c.offsetWidth / 2, behavior: "smooth" });
    }
  });
  const active = Number(screens[i].dataset.nav);
  nav.forEach((n, k) => n.classList.toggle("on", k === active));
  countAll(screens[i]);
  if (screens[i].dataset.screen === "expense") playExpense(screens[i], playId);
}

// Celular: chips, deslizar con el dedo, y avanza solo mientras no lo toques
let autoplayFrom = 0;
const holdAutoplay = () => { autoplayFrom = Date.now() + 15000; };
chips.forEach((chip, i) => chip.addEventListener("click", () => { holdAutoplay(); show(i); }));

const stage = $(".tour-stage");
let touchX = null;
stage.addEventListener("touchstart", (e) => { touchX = e.touches[0].clientX; holdAutoplay(); }, { passive: true });
stage.addEventListener("touchend", (e) => {
  if (touchX === null) return;
  const dx = e.changedTouches[0].clientX - touchX;
  touchX = null;
  if (Math.abs(dx) > 40) show((current + (dx < 0 ? 1 : -1) + screens.length) % screens.length);
});

let stageVisible = false;
new IntersectionObserver(([entry]) => {
  stageVisible = entry.isIntersecting;
  if (stageVisible && current < 0) show(0);
}, { threshold: 0.3 }).observe(stage);
if (!calm) {
  setInterval(() => {
    if (!isDesktop() && stageVisible && !document.hidden && Date.now() > autoplayFrom) {
      show((current + 1) % screens.length);
    }
  }, 6500);
}

// Los paneles de la compu también se animan, al llegar con el scroll
const STORIES = {
  count: countAll,
  expense: (root) => playExpense(root, playId),
};

// Hacer zoom o achicar la ventana puede pasar de la versión compu a la de celular
// (o al revés): sacamos los desplazamientos que quedaron de la otra versión.
matchMedia("(min-width: 768px)").addEventListener("change", () => {
  $$("[data-depth]").forEach((el) => { el.style.translate = ""; });
  const browser = $(".browser");
  if (browser) browser.style.transform = "";
  onScroll();
});

// --- Aparecer al llegar con el scroll ---
const targets = $$(".reveal, .step-line");
if (calm || !("IntersectionObserver" in window)) {
  targets.forEach((el) => {
    el.classList.add("in");
    STORIES[el.dataset.story]?.(el);
  });
  show(0);
} else {
  // Recién acá escondemos: sin JavaScript la página se ve completa igual
  document.documentElement.classList.add("js-reveal");
  const seen = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add("in");
      STORIES[entry.target.dataset.story]?.(entry.target);
      seen.unobserve(entry.target);
    });
  }, { threshold: 0.15, rootMargin: "0px 0px -6% 0px" });
  targets.forEach((el) => seen.observe(el));
}
