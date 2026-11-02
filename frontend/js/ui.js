// =========================================================================
// ui.js · Piezas visuales reutilizables: íconos, avisos, animaciones,
// tema claro/oscuro y hojas (modales).
// =========================================================================

import { money } from "./format.js";

/** Dibuja los íconos Lucide (<i data-lucide="nombre">) que haya en la página. */
export const icons = () => window.lucide?.createIcons();

/** Escapa texto del usuario antes de meterlo en HTML (evita inyección de código). */
export const esc = (text) =>
  String(text ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

/** Lee el valor de un token de color, ej: css("--primary") -> "#4FB3E8" */
export const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

// --- Avisos flotantes ("toast") ---
export function toast(message, type = "success") {
  let wrap = document.querySelector(".toast-wrap");
  if (!wrap) {
    wrap = document.createElement("div");
    wrap.className = "toast-wrap";
    wrap.setAttribute("role", "status");  // lectores de pantalla lo anuncian
    document.body.append(wrap);
  }
  const icon = type === "error" ? "circle-alert" : "circle-check";
  const color = type === "error" ? "var(--danger)" : "var(--success)";
  const el = document.createElement("div");
  el.className = "toast";
  el.innerHTML = `<i data-lucide="${icon}" style="color:${color}"></i><span>${esc(message)}</span>`;
  wrap.append(el);
  icons();
  setTimeout(() => { el.style.transition = "opacity .3s"; el.style.opacity = "0"; }, 2800);
  setTimeout(() => el.remove(), 3200);
}

// --- Números que cuentan desde 0 (o desde el valor anterior) ---
export function countUp(el, cents, format = money) {
  const from = Number(el.dataset.value || 0);
  el.dataset.value = cents;
  if (reducedMotion()) { el.textContent = format(cents); return; }
  // Reinicia el efecto de "desenfoque que se aclara" (clase .counting en app.css)
  el.classList.remove("counting");
  void el.offsetWidth;  // truco: fuerza al navegador a "olvidar" la animación anterior
  el.classList.add("counting");
  const duration = 1100;
  const start = performance.now();
  const tick = (now) => {
    const t = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - t, 3);  // arranca rápido y frena al final
    el.textContent = format(from + (cents - from) * eased);
    if (t < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

// --- Barras de progreso: se llenan después de dibujarse ---
export function fillBars(root = document) {
  root.querySelectorAll("[data-fill]").forEach((bar) => {
    requestAnimationFrame(() => setTimeout(() => (bar.style.width = `${bar.dataset.fill}%`), 120));
  });
}

// --- Tema claro / oscuro ---
const THEME_KEY = "vb-theme";
export function currentTheme() {
  return document.documentElement.dataset.theme;
}
export function toggleTheme() {
  const next = currentTheme() === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem(THEME_KEY, next); } catch { /* sin almacenamiento: no pasa nada */ }
  document.dispatchEvent(new CustomEvent("vb:theme"));  // los gráficos se redibujan
}

// --- Hojas inferiores (en celular) / modales (en escritorio) ---
/**
 * Crea una hoja con el HTML dado. Devuelve { el, open, close }.
 * Se cierra tocando el fondo, con Escape o con cualquier [data-close].
 */
export function createSheet(innerHTML, { label = "Ventana" } = {}) {
  const root = document.createElement("div");
  root.innerHTML = `
    <div class="sheet-backdrop" data-close></div>
    <div class="sheet card p-5 md:p-6" role="dialog" aria-modal="true" aria-label="${esc(label)}">
      <div class="sheet-handle"></div>${innerHTML}
    </div>`;
  document.body.append(root);
  const onKey = (e) => e.key === "Escape" && close();
  function open() {
    root.classList.add("sheet-open");
    document.addEventListener("keydown", onKey);
    setTimeout(() => root.querySelector("[autofocus]")?.focus(), 250);
  }
  function close() {
    root.classList.remove("sheet-open");
    document.removeEventListener("keydown", onKey);
  }
  root.addEventListener("click", (e) => { if (e.target.closest("[data-close]")) close(); });
  icons();
  return { el: root, open, close };
}

/** Confirmación simple ("¿Borrar este gasto?") que devuelve true/false. */
export function confirmDialog(message, { confirmText = "Borrar" } = {}) {
  return new Promise((resolve) => {
    const sheet = createSheet(`
      <p class="text-lg font-medium mb-5">${esc(message)}</p>
      <div class="flex gap-3 justify-end">
        <button class="btn btn-ghost" data-close data-answer="no">Cancelar</button>
        <button class="btn btn-danger" data-close data-answer="yes">${esc(confirmText)}</button>
      </div>`, { label: "Confirmar" });
    sheet.el.addEventListener("click", (e) => {
      const answer = e.target.closest("[data-answer]")?.dataset.answer;
      if (answer || e.target.classList.contains("sheet-backdrop")) {
        resolve(answer === "yes");
        setTimeout(() => sheet.el.remove(), 400);
      }
    });
    sheet.open();
  });
}

// --- Red de seguridad para errores ---
// Si algún pedido falla y nadie lo atrapó (ej: se cayó la conexión), en vez de
// que no pase nada en pantalla, mostramos el mensaje en un aviso rojo.
window.addEventListener("unhandledrejection", (event) => {
  const message = event.reason?.message;
  if (message && event.reason?.status !== 401) toast(message, "error");
});

// --- Brillo que sigue al mouse en las tarjetas ---
// Guardamos la posición del mouse dentro de la tarjeta en variables CSS
// (--mx, --my) y el CSS dibuja ahí un degradado suave.
document.addEventListener("pointermove", (e) => {
  const card = e.target.closest?.("main .card");
  if (!card) return;
  const r = card.getBoundingClientRect();
  card.style.setProperty("--mx", `${e.clientX - r.left}px`);
  card.style.setProperty("--my", `${e.clientY - r.top}px`);
}, { passive: true });

// --- Celebración: una pequeña lluvia de papelitos (meta cumplida) ---
export function celebrate(originEl) {
  if (reducedMotion()) return;
  const canvas = document.createElement("canvas");
  canvas.style.cssText = "position:fixed;inset:0;pointer-events:none;z-index:70";
  canvas.width = innerWidth * devicePixelRatio;
  canvas.height = innerHeight * devicePixelRatio;
  document.body.append(canvas);
  const ctx = canvas.getContext("2d");
  ctx.scale(devicePixelRatio, devicePixelRatio);

  const box = originEl?.getBoundingClientRect() ?? { left: innerWidth / 2, top: innerHeight / 2, width: 0, height: 0 };
  const x0 = box.left + box.width / 2;
  const y0 = box.top + box.height / 2;
  const colors = [css("--primary"), css("--accent"), "#FFFFFF"];
  // Cada papelito tiene posición, velocidad, giro y color al azar
  const bits = Array.from({ length: 70 }, () => ({
    x: x0, y: y0, vx: (Math.random() - 0.5) * 9, vy: -Math.random() * 9 - 3,
    size: 4 + Math.random() * 5, rot: Math.random() * 6, vr: (Math.random() - 0.5) * 0.3,
    color: colors[Math.floor(Math.random() * colors.length)],
  }));
  const start = performance.now();
  (function frame(now) {
    const t = (now - start) / 1000;
    ctx.clearRect(0, 0, innerWidth, innerHeight);
    for (const b of bits) {
      b.vy += 0.25;            // gravedad
      b.x += b.vx; b.y += b.vy; b.rot += b.vr;
      ctx.save();
      ctx.globalAlpha = Math.max(1 - t / 1.8, 0);  // se desvanecen
      ctx.translate(b.x, b.y); ctx.rotate(b.rot);
      ctx.fillStyle = b.color;
      ctx.fillRect(-b.size / 2, -b.size / 4, b.size, b.size / 2);
      ctx.restore();
    }
    if (t < 1.8) requestAnimationFrame(frame); else canvas.remove();
  })(start);
}

/** Avisa a toda la página que cambiaron los datos (para que se refresque). */
export const notifyDataChanged = () => document.dispatchEvent(new CustomEvent("vb:data-changed"));
export const onDataChanged = (fn) => document.addEventListener("vb:data-changed", fn);
