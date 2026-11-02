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

/** Avisa a toda la página que cambiaron los datos (para que se refresque). */
export const notifyDataChanged = () => document.dispatchEvent(new CustomEvent("vb:data-changed"));
export const onDataChanged = (fn) => document.addEventListener("vb:data-changed", fn);
