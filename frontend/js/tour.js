// =========================================================================
// tour.js · Recorrido guiado (~30 segundos) para quien entra por primera vez.
//
// Oscurece la pantalla y "ilumina" una parte por vez con una explicación
// corta. El truco del foco: un recuadro con una sombra GIGANTE alrededor
// (box-shadow de 9999px) que tapa todo menos lo que queremos mostrar.
// Sale solo la primera vez; después se puede ver desde el menú.
// =========================================================================

import { icons } from "./ui.js";

const DONE_KEY = "vb-tour-done";

/** El primer elemento VISIBLE de una lista de selectores (menú lateral en compu, barra abajo en celular). */
function visible(selectors) {
  for (const sel of [].concat(selectors)) {
    for (const el of document.querySelectorAll(sel)) {
      const r = el.getBoundingClientRect();
      if (r.width > 0 && r.height > 0 && !el.closest("[hidden]")) return el;
    }
  }
  return null;
}

// Cada paso: qué iluminar (puede no estar: se saltea) y qué decir
const STEPS = [
  { title: "¡Bienvenido a VaultBase! 👋",
    text: "Te muestro lo principal en 30 segundos. Podés saltearlo cuando quieras." },
  { target: "#getting-started",
    title: "Empezá por acá",
    text: "Estos pasos dejan la app lista. Se tachan solos a medida que los hacés." },
  { target: "#money",
    title: "Tu plata hoy",
    text: "Lo que tenés, cuánto podés gastar por día y cuánto ahorrar hasta tu próximo cobro. Se calcula solo." },
  { target: ".fab",
    title: "Anotá un gasto en 2 toques",
    text: "Tocá el + cada vez que gastes algo: el monto y la categoría. Con eso los números se ajustan." },
  { target: ['.sidebar-link[href="/movimientos.html"]', '.bottom-nav a[href="/movimientos.html"]'],
    title: "Movimientos",
    text: "Todo lo que entra y sale: tu sueldo, tus gastos fijos (alquiler, UTE…) y los del día a día." },
  { target: ['.sidebar-link[href="/metas.html"]', '.bottom-nav a[href="/metas.html"]'],
    title: "Metas",
    text: "¿Un viaje? ¿Un fondo de emergencia? Creá la meta y tocá \"Plan\": te dice cuánto apartar y cuánto podés gastar." },
  { target: ['[data-action="account"]', '.bottom-nav [data-action="more"]'],
    title: "Tu cuenta y más",
    text: "Acá podés instalar la app en el celular, cambiar tu contraseña y mandarnos un comentario si algo no se entiende." },
  { title: "¡Listo! 🎉",
    text: "Si querés ver este recorrido de nuevo, está en el menú: \"Ver el tutorial\"." },
];

let state = null;  // { i, root, spot, card }

function place() {
  const { i, spot, card } = state;
  const step = STEPS[i];
  const el = step.target ? visible(step.target) : null;
  const pad = 8;
  state.root.classList.toggle("dim", !el);  // sin elemento que iluminar: todo oscuro
  if (el) {
    const r = el.getBoundingClientRect();
    Object.assign(spot.style, {
      display: "block", left: `${r.left - pad}px`, top: `${r.top - pad}px`,
      width: `${r.width + pad * 2}px`, height: `${r.height + pad * 2}px`,
    });
    // La tarjeta va del lado con más lugar libre (abajo o arriba del elemento),
    // sin salirse de la pantalla
    const cardH = card.offsetHeight;
    const spaceBelow = innerHeight - (r.bottom + pad);
    const spaceAbove = r.top - pad;
    const top = spaceBelow >= spaceAbove
      ? Math.min(r.bottom + pad + 12, innerHeight - cardH - 12)
      : Math.max(12, r.top - pad - 12 - cardH);
    const left = Math.min(Math.max(12, r.left + r.width / 2 - card.offsetWidth / 2), innerWidth - card.offsetWidth - 12);
    Object.assign(card.style, { top: `${top}px`, left: `${left}px` });
  } else {
    // Sin elemento: tarjeta centrada y todo oscuro. (Centramos en píxeles y no con
    // transform: la animación de entrada de la tarjeta usa transform y lo pisaría.)
    spot.style.display = "none";
    Object.assign(card.style, {
      top: `${(innerHeight - card.offsetHeight) / 2}px`, left: `${(innerWidth - card.offsetWidth) / 2}px`,
    });
  }
}

function render() {
  const { i, card, root } = state;
  const step = STEPS[i];
  const last = i === STEPS.length - 1;
  card.innerHTML = `
    <div class="flex items-center justify-between mb-2">
      <span class="muted text-xs">${i + 1} de ${STEPS.length}</span>
      ${last ? "" : `<button class="muted text-xs underline" data-tour="skip">Saltar</button>`}
    </div>
    <h3 class="font-display text-lg font-bold mb-1">${step.title}</h3>
    <p class="text-sm muted mb-4">${step.text}</p>
    <div class="flex gap-2 justify-end">
      ${i > 0 && !last ? `<button class="btn btn-ghost text-sm py-2" data-tour="back">Atrás</button>` : ""}
      <button class="btn btn-primary text-sm py-2" data-tour="${last ? "end" : "next"}">${last ? "¡Empezar!" : "Siguiente"}</button>
    </div>`;
  root.setAttribute("aria-label", step.title);
  const el = step.target ? visible(step.target) : null;
  el?.scrollIntoView({ block: "center", behavior: "instant" });
  requestAnimationFrame(place);
  icons();
}

function go(delta) {
  let i = state.i + delta;
  // Saltear pasos cuyo elemento no está en pantalla (ej: "Primeros pasos" ya completos)
  while (i > 0 && i < STEPS.length - 1 && STEPS[i].target && !visible(STEPS[i].target)) i += delta;
  state.i = Math.min(Math.max(i, 0), STEPS.length - 1);
  render();
}

export function endTour() {
  if (!state) return;
  try { localStorage.setItem(DONE_KEY, "1"); } catch { /* sin almacenamiento */ }
  state.root.remove();
  removeEventListener("resize", place);
  removeEventListener("scroll", place, true);
  state = null;
}

/** Arranca el recorrido (desde el menú, o la primera vez). */
export function startTour() {
  if (state) return;
  const root = document.createElement("div");
  root.className = "tour";
  root.setAttribute("role", "dialog");
  root.setAttribute("aria-modal", "true");
  root.innerHTML = `<div class="tour-spot"></div><div class="tour-card card p-4"></div>`;
  document.body.append(root);
  state = { i: 0, root, spot: root.querySelector(".tour-spot"), card: root.querySelector(".tour-card") };
  root.addEventListener("click", (e) => {
    const action = e.target.closest("[data-tour]")?.dataset.tour;
    if (action === "next") go(1);
    if (action === "back") go(-1);
    if (action === "skip" || action === "end") endTour();
  });
  addEventListener("resize", place);
  addEventListener("scroll", place, true);
  render();
}

/** La primera vez que alguien entra, el recorrido sale solo. */
export function maybeStartTour() {
  let done = false;
  try { done = localStorage.getItem(DONE_KEY) === "1"; } catch { /* sin almacenamiento */ }
  if (!done) setTimeout(startTour, 900);  // un ratito, para que se dibuje la pantalla
}
