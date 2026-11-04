// =========================================================================
// tour.js · Recorridos guiados.
//
// Oscurece la pantalla y "ilumina" UNA cosa puntual por vez, con una frase
// corta. El truco del foco: un recuadro con una sombra GIGANTE alrededor
// (box-shadow de 9999px) que tapa todo menos lo que queremos mostrar.
//
// Hay dos recorridos:
// - "short": lo principal en 30 segundos, para quien crea su cuenta.
// - "full": para probar la app tocando. Sale solo en la demo (ahí hay datos
//   para mostrar) y siempre desde "Ver el tutorial".
// Como "full" cambia de página, el paso actual se guarda en sessionStorage y
// la pantalla siguiente lo retoma (resumeTour).
// =========================================================================

import { api, isDemoEmail } from "./api.js";
import { getMe } from "./shell.js";
import { celebrate, esc, icons } from "./ui.js";

const DONE_KEY = "vb-tour-done";
const RESUME_KEY = "vb-tour-resume";
const HOME = "/dashboard.html";
const MAX_SPOT = 0.6;  // lo iluminado nunca ocupa más de esta parte de la pantalla
const navLink = (href) => [`.sidebar-link[href="${href}"]`, `.bottom-nav a[href="${href}"]`];
const stopScroll = (e) => e.preventDefault();  // bloquea deslizar el dedo / la rueda sobre el tutorial
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** El primer elemento VISIBLE de una lista de selectores (menú lateral en compu, barra abajo en celular). */
function visible(selectors) {
  for (const sel of [].concat(selectors)) {
    for (const el of document.querySelectorAll(sel)) {
      const r = el.getBoundingClientRect();
      // (lo que está dentro de una hoja cerrada mide algo, pero está fuera de la pantalla)
      if (r.width > 0 && r.height > 0 && !el.closest("[hidden], .sheet")) return el;
    }
  }
  return null;
}

// Cada paso: qué iluminar (si no está, se saltea) y una frase corta. Además:
//   up     = iluminar el contenedor de ese elemento
//   page   = en qué pantalla está (por defecto, Inicio)
//   tap    = hay que tocarlo: "next" solo avanza, "click" lo aprieta y avanza,
//            "sheet" lo aprieta y espera a que cierres la ventana que abre
//   hint   = lo que se dice mientras esa ventana está abierta
//   fill   = valores para dejar cargados en el formulario
//   wait   = es algo que aparece un rato después: esperarlo
//   ifChanged = mostrarlo solo si se cargó algo en el paso anterior
const TOURS = {
  short: [
    { title: "¡Bienvenido a VaultBase! 👋",
      text: "Te muestro lo principal en 30 segundos." },
    { target: "#getting-started",
      title: "Empezá por acá",
      text: "Estos pasos dejan la app lista. Se tachan solos." },
    { target: "#money-current", up: "div:has(> #money-current)",
      title: "💰 Tu plata hoy",
      text: "Lo que entró menos lo que gastaste. Se calcula solo." },
    { target: ".fab",
      title: "➕ Anotá tus gastos",
      text: "Tocá el + cada vez que gastes algo. Son 2 toques." },
    { target: navLink("/movimientos.html"),
      title: "📋 Movimientos",
      text: "Tu sueldo, tus gastos fijos y los del día a día." },
    { target: navLink("/metas.html"),
      title: "🎯 Metas",
      text: "Creá una meta y tocá \"Plan\": te dice cómo llegar." },
    { target: ['[data-action="account"]', '.bottom-nav [data-action="more"]'],
      title: "☰ Y hay más",
      text: "Instalar la app, tu cuenta y mandarnos un comentario." },
    { title: "¡Listo! 🎉",
      text: "Para probar todo tocando, en el menú está \"Ver el tutorial\"." },
  ],
  full: [
    { title: "Te muestro cómo funciona 👋",
      text: "Un minuto, y vas a probar las cosas vos.",
      demoText: "Es una cuenta de ejemplo: podés tocar todo. En un minuto te muestro lo clave." },
    { target: "#money-current", up: "div:has(> #money-current)",
      title: "💰 Tu plata hoy",
      text: "Lo que entró menos lo que gastaste. Se calcula solo." },
    { target: "#money-daily", up: ".grid",
      title: "📅 Tu margen",
      text: "Cuánto gastar por día y cuánto te puede sobrar hasta tu próximo cobro." },
    { target: ".fab", tap: "sheet",
      title: "➕ Probá anotar un gasto",
      text: "Tocá el +.",
      hint: "Anotá un gasto, o deslizá hacia abajo para cerrar.",
      demoHint: "Anotá uno de prueba, o deslizá hacia abajo para cerrar." },
    { target: "#money-current", up: "div:has(> #money-current)", ifChanged: true,
      title: "✨ ¡Mirá!",
      text: "Tu plata ya se actualizó sola." },
    { target: navLink("/movimientos.html"),
      title: "📋 Movimientos",
      text: "Acá queda todo lo que entra y sale, mes por mes." },
    { target: navLink("/metas.html"), tap: "next",
      title: "🎯 ¿Estás juntando para algo?",
      text: "Tocá Metas." },
    { page: "/metas.html", target: "[data-plan]", tap: "sheet",
      title: "🗺️ El plan",
      text: "Tocá Plan: te dice cuánto apartar y cuánto gastar para llegar.",
      hint: "Este es tu plan. Deslizá hacia abajo para cerrarlo." },
    { page: "/metas.html", target: navLink("/simulador.html"), tap: "next",
      title: "🧮 ¿Te da para comprarlo?",
      text: "Tocá Simulador." },
    { page: "/simulador.html", target: "#sim-run", tap: "click",
      fill: { "#sim-name": "Celular", "#sim-price": "45.000" },
      title: "🛒 Probalo",
      text: "Ya cargué un celular de $ 45.000. Tocá Simular." },
    { page: "/simulador.html", target: "#results .glow-border", wait: true,
      title: "💡 Tu respuesta",
      text: "La mejor forma de pagarlo sin romper tus metas." },
    { page: "/simulador.html", target: ['[data-action="account"]', '.bottom-nav [data-action="more"]'],
      title: "☰ Y hay más",
      text: "Suscripciones, sueldo y aguinaldo, y tu cuenta." },
    { title: "¡Listo! 🎉",
      text: "Seguí tocando lo que quieras. Podés volver a verlo en \"Ver el tutorial\".",
      demoTarget: "#demo-banner",
      demoText: "Esta demo se borra sola. Para usarla con tu plata, tocá \"Crear mi cuenta\"." },
  ],
};

let state = null;  // { name, steps, i, demo, root, spot, card, hint, observer, rect, paused, changed }

const stepPage = (step) => step.page || HOME;
const stepText = (step) => (state.demo && step.demoText) || step.text;

/** Qué iluminar en este paso (null = nada, tarjeta centrada). */
function targetOf(step) {
  const selector = (state.demo && step.demoTarget) || step.target;
  const el = selector ? visible(selector) : null;
  return step.up ? el?.closest(step.up) || el : el;
}

function place() {
  if (!state || state.paused) return;
  const { i, steps, spot, card } = state;
  const step = steps[i];
  const el = targetOf(step);
  const pad = 8;
  const edge = 6;  // el foco nunca toca los bordes de la pantalla
  state.root.classList.toggle("dim", !el);  // sin elemento que iluminar: todo oscuro
  spot.classList.toggle("tap", Boolean(el && step.tap));
  if (el) {
    const box = el.getBoundingClientRect();
    const left = Math.max(edge, box.left - pad);
    const right = Math.min(innerWidth - edge, box.right + pad);
    const top = Math.max(edge, box.top - pad);
    const bottom = Math.min(innerHeight - edge, top + Math.min(box.height + pad * 2, innerHeight * MAX_SPOT));
    state.rect = { left, right, top, bottom };
    Object.assign(spot.style, {
      display: "block", left: `${left}px`, top: `${top}px`, width: `${right - left}px`, height: `${bottom - top}px`,
    });
    // La tarjeta va del lado con más lugar libre (abajo o arriba del elemento),
    // sin salirse de la pantalla
    const cardH = card.offsetHeight;
    const cardTop = innerHeight - bottom >= top
      ? Math.min(bottom + 12, innerHeight - cardH - 12)
      : Math.max(12, top - 12 - cardH);
    const center = (left + right) / 2;
    const cardLeft = Math.min(Math.max(12, center - card.offsetWidth / 2), innerWidth - card.offsetWidth - 12);
    Object.assign(card.style, { top: `${cardTop}px`, left: `${cardLeft}px` });
  } else {
    // Sin elemento: tarjeta centrada y todo oscuro. (Centramos en píxeles y no con
    // transform: la animación de entrada de la tarjeta usa transform y lo pisaría.)
    state.rect = null;
    spot.style.display = "none";
    Object.assign(card.style, {
      top: `${(innerHeight - card.offsetHeight) / 2}px`, left: `${(innerWidth - card.offsetWidth) / 2}px`,
    });
  }
}

/** Trae el elemento al centro de la pantalla y acomoda el foco. */
function focusStep() {
  if (!state || state.paused) return;
  targetOf(state.steps[state.i])?.scrollIntoView({ block: "center", behavior: "instant" });
  place();
}

function render() {
  const { i, steps, card, root } = state;
  const step = steps[i];
  const last = i === steps.length - 1;
  for (const [sel, value] of Object.entries(step.fill || {})) {
    const input = document.querySelector(sel);
    if (input) input.value = value;
  }
  card.innerHTML = `
    <div class="flex items-center gap-3 mb-3">
      <div class="tour-progress"><span style="width:${((i + 1) / steps.length) * 100}%"></span></div>
      ${last ? "" : `<button class="muted text-xs underline" data-tour="skip">Saltar</button>`}
    </div>
    <h3 class="font-display text-lg font-bold mb-1">${step.title}</h3>
    <p class="text-sm muted ${step.tap ? "mb-2" : "mb-4"}">${stepText(step)}</p>
    ${step.tap ? `<p class="tour-tap mb-3">👆 Tocá lo iluminado</p>` : ""}
    <div class="flex gap-2 justify-end">
      ${i > 0 && !last ? `<button class="btn btn-ghost text-sm py-2" data-tour="back">Atrás</button>` : ""}
      ${step.tap
        ? `<button class="btn btn-ghost text-sm py-2" data-tour="next">Seguir sin probar</button>`
        : `<button class="btn btn-primary text-sm py-2" data-tour="${last ? "end" : "next"}">${last ? "¡Empezar!" : "Siguiente"}</button>`}
    </div>`;
  // Reiniciamos la animación de entrada: cada paso "aparece"
  card.style.animation = "none";
  void card.offsetHeight;
  card.style.animation = "";
  root.setAttribute("aria-label", step.title);
  focusStep();
  setTimeout(focusStep, 700);  // las tarjetas entran con una animación: medimos de nuevo cuando termina
  icons();
}

const skipped = (step) => (step.ifChanged && !state.changed)
  || (stepPage(step) === location.pathname && step.target && !step.wait && !targetOf(step));

async function go(delta) {
  const { steps } = state;
  let i = state.i + delta;
  // Saltear pasos cuyo elemento no está en pantalla (ej: "Primeros pasos" ya completos, o sin datos todavía)
  while (i > 0 && i < steps.length - 1 && skipped(steps[i])) i += delta;
  i = Math.min(Math.max(i, 0), steps.length - 1);
  if (stepPage(steps[i]) !== location.pathname) {
    // El paso es en otra pantalla: guardamos por dónde vamos y la pantalla nueva lo retoma
    try { sessionStorage.setItem(RESUME_KEY, JSON.stringify({ name: state.name, i, dir: delta })); }
    catch { endTour(); return; }
    location.href = stepPage(steps[i]);
    return;
  }
  state.i = i;
  if (steps[i].wait) await waitForTarget(steps[i]);
  if (state) render();
}

async function waitForTarget(step) {
  for (let t = 0; t < 40 && state && step.target && !targetOf(step); t++) await sleep(100);
}

// --- Pasos que hay que tocar ---

/** Tocaron algo en el oscurecido: si fue lo iluminado, pasa lo que dice el paso. */
function onTap(x, y) {
  const step = state.steps[state.i];
  const r = state.rect;
  if (!step.tap || !r) return;
  if (x < r.left || x > r.right || y < r.top || y > r.bottom) {
    // Tocó en otro lado: el foco "se sacude" para mostrar dónde es
    state.spot.classList.remove("nudge");
    void state.spot.offsetWidth;
    state.spot.classList.add("nudge");
    return;
  }
  if (step.tap === "next") return void go(1);
  const el = targetOf(step);
  if (step.tap === "sheet") pause(step);
  el?.click();
  if (step.tap === "click") go(1);
}

/** Saca el tutorial del medio mientras usás la ventana que se abrió. */
function pause(step) {
  state.paused = true;
  state.root.hidden = true;
  document.documentElement.classList.remove("tour-open");
  state.hint.hidden = false;
  state.hint.innerHTML = `<span>${esc((state.demo && step.demoHint) || step.hint)}</span>
    <button class="font-semibold text-primary" data-tour-resume>Seguir</button>`;
}

async function resumeFromPause() {
  if (!state?.paused) return;
  state.paused = false;
  state.hint.hidden = true;
  state.root.hidden = false;
  document.documentElement.classList.add("tour-open");
  await go(1);
}

// Cerraste la ventana: el tutorial sigue (salvo que se haya abierto otra enseguida)
document.addEventListener("vb:sheet-close", async () => {
  if (!state?.paused) return;
  await sleep(450);  // la ventana termina de bajar y los números se actualizan
  if (!document.querySelector(".sheet-open")) resumeFromPause();
});
document.addEventListener("vb:data-changed", () => { if (state) state.changed = true; });

export function endTour() {
  if (!state) return;
  try { sessionStorage.removeItem(RESUME_KEY); } catch { /* sin almacenamiento */ }
  state.observer.disconnect();
  state.root.remove();
  state.hint.remove();
  document.documentElement.classList.remove("tour-open");
  removeEventListener("resize", focusStep);
  removeEventListener("scroll", place, true);
  state = null;
}

/** Lo marcamos como visto apenas arranca (en este aparato y en la cuenta):
 *  si cerrás la app a la mitad, no vuelve a salir solo. */
function markSeen() {
  try { localStorage.setItem(DONE_KEY, "1"); } catch { /* sin almacenamiento */ }
  api("/api/users/me", { method: "PATCH", body: { tour_done: true } }).catch(() => {});
}

/** Dibuja el oscurecido y deja listo el estado (todavía sin mostrar ningún paso). */
function mount(name, i, demo) {
  const root = document.createElement("div");
  root.className = "tour";
  root.setAttribute("role", "dialog");
  root.setAttribute("aria-modal", "true");
  root.innerHTML = `<div class="tour-spot"></div><div class="tour-card card p-4"></div>`;
  const hint = document.createElement("div");
  hint.className = "tour-hint";
  hint.hidden = true;
  hint.addEventListener("click", (e) => { if (e.target.closest("[data-tour-resume]")) resumeFromPause(); });
  document.body.append(root, hint);
  document.documentElement.classList.add("tour-open");
  root.addEventListener("touchmove", stopScroll, { passive: false });
  root.addEventListener("wheel", stopScroll, { passive: false });
  // Si llegan datos y la pantalla cambia de alto, el foco se vuelve a acomodar
  const observer = new ResizeObserver(() => focusStep());
  observer.observe(document.querySelector("main"));
  state = { name, steps: TOURS[name], i, demo, root, hint, observer, rect: null, paused: false, changed: false,
            spot: root.querySelector(".tour-spot"), card: root.querySelector(".tour-card") };
  root.addEventListener("click", (e) => {
    const action = e.target.closest("[data-tour]")?.dataset.tour;
    if (action === "next") go(1);
    else if (action === "back") go(-1);
    else if (action === "skip") endTour();
    else if (action === "end") { endTour(); celebrate(); }
    else if (!e.target.closest(".tour-card")) onTap(e.clientX, e.clientY);
  });
  addEventListener("resize", focusStep);
  addEventListener("scroll", place, true);  // la página solo se mueve sola (ej: al mostrar un resultado)
}

async function isDemo() {
  const me = await getMe().catch(() => null);
  return Boolean(me && isDemoEmail(me.email));
}

/** Arranca un recorrido. Por defecto el completo (es lo que se pide desde el menú). */
export async function startTour(name = "full") {
  if (state) return;
  const demo = await isDemo();
  if (state) return;
  mount(name, 0, demo);
  markSeen();
  render();
}

/** Sale solo la primera vez que entra una cuenta nueva (lo dice la cuenta, no el aparato). */
export async function maybeStartTour() {
  const me = await getMe().catch(() => null);
  if (!me) return;
  if (me.tour_done) {
    try { localStorage.setItem(DONE_KEY, "1"); } catch { /* sin almacenamiento */ }
    return;
  }
  // La demo tiene datos para mostrar: ahí conviene el recorrido para probar tocando
  setTimeout(() => startTour(isDemoEmail(me.email) ? "full" : "short"), 900);  // un ratito, para que se dibuje la pantalla
}

/** Si veníamos en medio de un recorrido de otra pantalla, lo sigue acá. */
export async function resumeTour() {
  let saved = null;
  try { saved = JSON.parse(sessionStorage.getItem(RESUME_KEY)); } catch { /* sin almacenamiento */ }
  if (!saved || !TOURS[saved.name]?.[saved.i] || state) return;
  const demo = await isDemo();
  mount(saved.name, saved.i, demo);
  // Los datos tardan un poco en llegar: esperamos a que aparezca lo que hay que iluminar
  const step = state.steps[state.i];
  await waitForTarget(step);
  if (!state) return;
  if (step.target && !targetOf(step)) go(saved.dir || 1);  // no está (ej: no hay datos): pasamos al siguiente
  else render();
}
