// =========================================================================
// tour.js · Recorridos guiados.
//
// Oscurece la pantalla y "ilumina" una parte por vez con una explicación
// corta. El truco del foco: un recuadro con una sombra GIGANTE alrededor
// (box-shadow de 9999px) que tapa todo menos lo que queremos mostrar.
//
// Hay dos recorridos:
// - "short": lo principal en 30 segundos, para quien crea su cuenta.
// - "full": pasa por TODAS las pantallas y explica qué es cada cosa. Sale solo
//   en la demo (ahí hay datos para mostrar) y siempre desde "Ver el tutorial".
// Como "full" cambia de página, el paso actual se guarda en sessionStorage y
// la pantalla siguiente lo retoma (resumeTour).
// =========================================================================

import { api, isDemoEmail } from "./api.js";
import { getMe } from "./shell.js";
import { icons } from "./ui.js";

const DONE_KEY = "vb-tour-done";
const RESUME_KEY = "vb-tour-resume";
const HOME = "/dashboard.html";
const stopScroll = (e) => e.preventDefault();  // bloquea deslizar el dedo / la rueda sobre el tutorial

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

// Cada paso: qué iluminar (puede no estar: se saltea) y qué decir.
// "up" = iluminar el contenedor de ese elemento. "page" = en qué pantalla está (por defecto, Inicio).
const TOURS = {
  short: [
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
      text: "Si querés ver todo con más detalle, en el menú está \"Ver el tutorial\"." },
  ],
  full: [
    { title: "Te muestro toda la app 👋",
      text: "Vamos a pasar por cada pantalla y te explico para qué sirve cada cosa. Podés saltearlo cuando quieras.",
      demoText: "Esta es una cuenta de ejemplo, con los datos de una persona inventada. Vamos a pasar por cada pantalla y te explico para qué sirve cada cosa." },
    { target: "#money",
      title: "Tu plata hoy",
      text: "Lo que entró menos lo que gastaste: es la plata que tenés ahora. Abajo: cuánto podés gastar por día y cuánto ahorrar hasta tu próximo cobro." },
    { target: "#stat-income", up: "section",
      title: "El resumen del mes",
      text: "Cuánto entró y cuánto salió este mes. El balance es solo de este mes; tu plata total es la de arriba." },
    { target: "#donut", up: ".card",
      title: "En qué se te va la plata",
      text: "Tus gastos del mes separados por categoría, para ver de un vistazo dónde se te va más." },
    { target: "#bars", up: ".card",
      title: "Mes a mes",
      text: "Lo que entró y salió cada mes del año. Los meses que todavía no llegaron son una estimación." },
    { target: "#food-remaining", up: ".card",
      title: "Comida",
      text: "Cuánto te queda para comer este mes. Tocá el porcentaje para cambiar cuánto le dedicás." },
    { target: ".fab",
      title: "Anotar un gasto",
      text: "El botón + está en todas las pantallas: monto, categoría y listo. Es lo que más vas a usar." },
    { page: "/movimientos.html", target: '[role="tablist"]',
      title: "Movimientos",
      text: "Todo lo que entra y sale, mes por mes. Acá cambiás entre gastos e ingresos, y arriba elegís el mes." },
    { page: "/movimientos.html", target: "#fixed-list", up: ".card",
      title: "Gastos fijos",
      text: "Los que se repiten cada mes, como el alquiler o la UTE. Los cargás una vez y se cuentan solos." },
    { page: "/movimientos.html", target: "#variable-list", up: ".card",
      title: "Gastos del día a día",
      text: "Lo que anotás con el +. Tocá cualquiera para editarlo o marcarlo como algo puntual." },
    { page: "/metas.html", target: "#sum-capacity", up: "section",
      title: "Metas",
      text: "Cuánto podrías ahorrar por mes, cuánto de eso va a tus metas y cuánto llevás juntado." },
    { page: "/metas.html", target: "#goals",
      title: "Cada meta",
      text: "Un viaje, un fondo de emergencia… Ves cuánto te falta y cuándo llegás. Tocá \"Plan\": te dice cuánto apartar y cuánto podés gastar hasta esa fecha." },
    { page: "/simulador.html", target: "#sim-form",
      title: "Simulador de compras",
      text: "¿Querés comprar algo? Poné el precio y compará contado o en cuotas: te dice cómo afecta tu mes, tu año y tus metas." },
    { page: "/simulador.html", target: "#wish-list", up: ".card",
      title: "Lista de deseos",
      text: "Guardá lo que querés comprar más adelante, para simularlo cuando quieras." },
    { page: "/suscripciones.html", target: "#sum-month", up: "section",
      title: "Suscripciones",
      text: "Netflix, Spotify y compañía: cuánto pagás por mes y por año, y cuándo es el próximo cobro. Las que son en dólares se convierten solas. En el celular, esta pantalla está en \"Más\"." },
    { page: "/sueldo.html", target: "#salary-form",
      title: "Sueldo y aguinaldo",
      text: "Pasá de nominal a líquido con los descuentos de Uruguay y mirá cuánto te toca de aguinaldo. También está en \"Más\"." },
    { target: ['[data-action="account"]', '.bottom-nav [data-action="more"]'],
      title: "Tu cuenta y más",
      text: "Acá podés instalar la app en el celular, cambiar tu contraseña y mandarnos un comentario si algo no se entiende." },
    { title: "¡Listo! 🎉",
      text: "Si querés volver a verlo, está en el menú: \"Ver el tutorial\".",
      demoTarget: "#demo-banner",
      demoText: "Ya viste todo. Tocá y probá lo que quieras: esta demo se borra sola en unas horas. Para usarla con tu plata, tocá \"Crear mi cuenta\"." },
  ],
};

let state = null;  // { name, steps, i, demo, root, spot, card, observer }

const stepPage = (step) => step.page || HOME;
const stepText = (step) => (state.demo && step.demoText) || step.text;

/** Qué iluminar en este paso (null = nada, tarjeta centrada). */
function targetOf(step) {
  const selector = (state.demo && step.demoTarget) || step.target;
  const el = selector ? visible(selector) : null;
  return step.up ? el?.closest(step.up) || el : el;
}

function place() {
  if (!state) return;
  const { i, steps, spot, card } = state;
  const el = targetOf(steps[i]);
  const pad = 8;
  state.root.classList.toggle("dim", !el);  // sin elemento que iluminar: todo oscuro
  if (el) {
    const box = el.getBoundingClientRect();
    // Si es más alto que media pantalla (ej. "Tu plata hoy" en el celular), iluminamos solo
    // la parte de arriba: así queda lugar para la tarjeta y no se tapa todo
    const maxH = innerHeight * 0.45;
    const r = { left: box.left, width: box.width, top: box.top, height: Math.min(box.height, maxH) };
    r.bottom = r.top + r.height;
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

/** Trae el elemento a la vista y acomoda el foco. Lo alto se muestra desde su comienzo; lo chico, centrado. */
function focusStep() {
  if (!state) return;
  const el = targetOf(state.steps[state.i]);
  const tall = el && el.getBoundingClientRect().height > innerHeight * 0.45;
  el?.scrollIntoView({ block: tall ? "start" : "center", behavior: "instant" });
  place();
}

function render() {
  const { i, steps, card, root } = state;
  const step = steps[i];
  const last = i === steps.length - 1;
  card.innerHTML = `
    <div class="flex items-center justify-between mb-2">
      <span class="muted text-xs">${i + 1} de ${steps.length}</span>
      ${last ? "" : `<button class="muted text-xs underline" data-tour="skip">Saltar</button>`}
    </div>
    <h3 class="font-display text-lg font-bold mb-1">${step.title}</h3>
    <p class="text-sm muted mb-4">${stepText(step)}</p>
    <div class="flex gap-2 justify-end">
      ${i > 0 && !last ? `<button class="btn btn-ghost text-sm py-2" data-tour="back">Atrás</button>` : ""}
      <button class="btn btn-primary text-sm py-2" data-tour="${last ? "end" : "next"}">${last ? "¡Empezar!" : "Siguiente"}</button>
    </div>`;
  root.setAttribute("aria-label", step.title);
  focusStep();
  setTimeout(place, 700);  // las tarjetas entran con una animación: medimos de nuevo cuando termina
  icons();
}

function go(delta) {
  const { steps } = state;
  let i = state.i + delta;
  // Saltear pasos cuyo elemento no está en pantalla (ej: "Primeros pasos" ya completos, o sin datos todavía)
  while (i > 0 && i < steps.length - 1 && stepPage(steps[i]) === location.pathname
         && steps[i].target && !targetOf(steps[i])) i += delta;
  i = Math.min(Math.max(i, 0), steps.length - 1);
  if (stepPage(steps[i]) !== location.pathname) {
    // El paso es en otra pantalla: guardamos por dónde vamos y la pantalla nueva lo retoma
    try { sessionStorage.setItem(RESUME_KEY, JSON.stringify({ name: state.name, i, dir: delta })); }
    catch { endTour(); return; }
    location.href = stepPage(steps[i]);
    return;
  }
  state.i = i;
  render();
}

export function endTour() {
  if (!state) return;
  try { sessionStorage.removeItem(RESUME_KEY); } catch { /* sin almacenamiento */ }
  state.observer.disconnect();
  state.root.remove();
  document.documentElement.classList.remove("tour-open");
  removeEventListener("resize", focusStep);
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
  document.body.append(root);
  document.documentElement.classList.add("tour-open");
  root.addEventListener("touchmove", stopScroll, { passive: false });
  root.addEventListener("wheel", stopScroll, { passive: false });
  // Si llegan datos y la pantalla cambia de alto, el foco se vuelve a acomodar
  const observer = new ResizeObserver(() => focusStep());
  observer.observe(document.querySelector("main"));
  state = { name, steps: TOURS[name], i, demo, root, observer,
            spot: root.querySelector(".tour-spot"), card: root.querySelector(".tour-card") };
  root.addEventListener("click", (e) => {
    const action = e.target.closest("[data-tour]")?.dataset.tour;
    if (action === "next") go(1);
    if (action === "back") go(-1);
    if (action === "skip" || action === "end") endTour();
  });
  addEventListener("resize", focusStep);
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
  // La demo tiene datos para mostrar: ahí conviene el recorrido completo
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
  for (let t = 0; t < 30 && step.target && !targetOf(step); t++) {
    await new Promise((r) => setTimeout(r, 100));
  }
  if (!state) return;
  if (step.target && !targetOf(step)) go(saved.dir || 1);  // no está (ej: no hay datos): pasamos al siguiente
  else render();
}
