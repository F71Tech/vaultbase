// =========================================================================
// ui.js · Piezas visuales reutilizables: íconos, avisos, animaciones,
// tema claro/oscuro y hojas (modales).
// =========================================================================

import { ApiError } from "./api.js";
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
 * Se cierra tocando el fondo, con Escape, con cualquier [data-close] o, en el
 * celular, deslizándola hacia abajo. Al cerrarse avisa con el evento "vb:sheet-close".
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
    root.dispatchEvent(new CustomEvent("vb:sheet-close", { bubbles: true }));
  }
  root.addEventListener("click", (e) => { if (e.target.closest("[data-close]")) close(); });
  enableSwipeToClose(root, close);
  icons();
  return { el: root, open, close };
}

const SWIPE_CLOSE_PX = 110;  // cuánto hay que bajarla para que se cierre...
const SWIPE_FLICK = 0.6;     // ...o con qué velocidad (px por milisegundo), si fue un "tirón" rápido

/** Deslizar la hoja hacia abajo para cerrarla (solo en celular: en escritorio es un modal). */
function enableSwipeToClose(root, close) {
  const sheet = root.querySelector(".sheet");
  const backdrop = root.querySelector(".sheet-backdrop");
  let start = null;
  let dragging = false;
  let dy = 0;

  sheet.addEventListener("touchstart", (e) => {
    dragging = false;
    dy = 0;
    // Solo si el contenido está arriba de todo (si no, deslizar es scrollear) y no sobre algo que
    // ya usa el dedo: una barra deslizable, un gráfico o una fila que scrollea de costado.
    const busyTarget = e.target.closest('input[type="range"], canvas, .no-scrollbar');
    start = sheet.scrollTop <= 0 && !busyTarget && e.touches.length === 1 && matchMedia("(max-width: 767px)").matches
      ? { x: e.touches[0].clientX, y: e.touches[0].clientY, t: Date.now() } : null;
  }, { passive: true });

  // passive: false para poder frenar el scroll del navegador mientras la arrastramos
  sheet.addEventListener("touchmove", (e) => {
    if (!start) return;
    const dx = e.touches[0].clientX - start.x;
    dy = e.touches[0].clientY - start.y;
    if (!dragging) {
      // El primer movimiento decide: hacia arriba o de costado no es arrastrar la hoja
      if (dy <= 0 || Math.abs(dx) > dy) { start = null; return; }
      dragging = true;
      sheet.style.transition = backdrop.style.transition = "none";  // que siga al dedo sin retraso
    }
    e.preventDefault();
    const pull = Math.max(0, dy);
    sheet.style.transform = `translateY(${pull}px)`;
    backdrop.style.opacity = String(Math.max(0, 1 - pull / (sheet.offsetHeight || 1)));
  }, { passive: false });

  const release = () => {
    if (!dragging) { start = null; return; }
    const speed = dy / Math.max(1, Date.now() - start.t);
    dragging = false;
    start = null;
    // Sacamos los estilos de arrastre: la hoja vuelve (o se va) con su animación normal
    sheet.style.transition = sheet.style.transform = "";
    backdrop.style.transition = backdrop.style.opacity = "";
    if (dy >= SWIPE_CLOSE_PX || (dy > 30 && speed >= SWIPE_FLICK)) {
      document.activeElement?.blur();  // que también se baje el teclado
      close();
    }
  };
  sheet.addEventListener("touchend", release);
  sheet.addEventListener("touchcancel", release);
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
    // "capture": anotamos la respuesta ANTES de que el clic cierre la hoja
    let answer = null;
    sheet.el.addEventListener("click", (e) => {
      answer = e.target.closest("[data-answer]")?.dataset.answer ?? answer;
    }, true);
    // Cerrarla de cualquier otra forma (fondo, Escape, deslizar) cuenta como "no"
    sheet.el.addEventListener("vb:sheet-close", () => {
      resolve(answer === "yes");
      setTimeout(() => sheet.el.remove(), 400);
    });
    sheet.open();
  });
}

// --- Red de seguridad para errores ---
// Si algún pedido a la API falla y nadie lo atrapó (ej: se cayó la conexión),
// en vez de que no pase nada en pantalla, mostramos el mensaje en un aviso rojo.
// SOLO errores de nuestra API (ApiError): el navegador también lanza errores
// internos que no le importan al usuario (ej: "Transition was skipped" cuando
// se saltea la animación entre páginas) y no queremos asustar a nadie con eso.
window.addEventListener("unhandledrejection", (event) => {
  const error = event.reason;
  if (error instanceof ApiError && error.status !== 401) toast(error.message, "error");
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
